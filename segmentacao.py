"""Segmentação estrutural de documentos jurídicos.

A interface de segmentação NÃO é uma classe, é um TIPO DE FUNÇÃO
(`Segmentador = Callable[[Documento], list[Segmento]]`). Trocar a implementação
estrutural por uma baseada em LLM/BERT depois é só passar outra função com a
mesma assinatura — o resto do pipeline não muda.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Callable

from modelagem import Documento, Segmento, TipoSegmento

# --- Interface intercambiável (em estilo funcional) ------------------------
Segmentador = Callable[[Documento], list[Segmento]]

# (titulo, inicio, fim) — offsets relativos a Documento.conteudo
Secao = tuple[str, int, int]

_RE_HEADER = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

# título normalizado -> tipo. Fundamentação NÃO é dividida em argumentos aqui;
# isso fica para a fase LLM/BERT. Por ora vira um único segmento FUNDAMENTO.
_MAPA_TIPOS: dict[str, TipoSegmento] = {
    "tese principal": TipoSegmento.TESE_PRINCIPAL,
    "nome": TipoSegmento.NOME_PARTES,
    "data": TipoSegmento.DATA,
    "valores": TipoSegmento.VALORES,
    "fundamentos": TipoSegmento.FUNDAMENTO,
    "fundamentacao": TipoSegmento.FUNDAMENTO,
    "relatorio": TipoSegmento.RELATORIO,
    "dispositivo": TipoSegmento.DISPOSITIVO,
}


# --- Carga: arquivo -> Documento (corpo) -----------------------------------
def separar_frontmatter(texto_bruto: str) -> tuple[str, str]:
    """Devolve (bloco_frontmatter, corpo). Sem frontmatter -> ("", texto)."""
    if not texto_bruto.startswith("---"):
        return "", texto_bruto
    partes = texto_bruto.split("---", 2)
    if len(partes) < 3:
        return "", texto_bruto
    return partes[1].strip("\n"), partes[2].lstrip("\n")


def parse_frontmatter(bloco: str) -> dict[str, str]:
    """Parser mínimo de `chave: valor` por linha (suficiente p/ o dataset)."""
    meta: dict[str, str] = {}
    for linha in bloco.splitlines():
        if ":" not in linha:
            continue
        chave, _, valor = linha.partition(":")
        meta[chave.strip()] = valor.strip().strip('"').strip("'")
    return meta


def carregar_documento(caminho: str | Path) -> Documento:
    """Lê o arquivo, separa frontmatter (-> campos) e mantém só o corpo em
    `conteudo` (fonte única para os offsets dos segmentos)."""
    bruto = Path(caminho).read_text(encoding="utf-8")
    bloco, corpo = separar_frontmatter(bruto)
    meta = parse_frontmatter(bloco)
    return Documento(
        id=meta.get("id", ""),
        conteudo=corpo,
        caso_jur_id=meta.get("caso_id", ""),
        tipo=meta.get("tipo", ""),
        cliente_cpf=meta.get("cliente_cpf"),
        data=meta.get("data"),
    )


# --- Classificação de seção ------------------------------------------------
def normalizar_titulo(titulo: str) -> str:
    """'Nome (das Partes)' -> 'nome'; remove parênteses, acentos e caixa."""
    sem_paren = re.sub(r"\(.*?\)", "", titulo)
    decomposto = unicodedata.normalize("NFKD", sem_paren)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.strip().lower()


def classificar_secao(titulo: str) -> TipoSegmento:
    return _MAPA_TIPOS.get(normalizar_titulo(titulo), TipoSegmento.OUTRO)


# --- Localização de seções (offsets) ---------------------------------------
def encontrar_secoes(corpo: str) -> list[Secao]:
    """Cada seção `## Header` vira (titulo, inicio, fim), com inicio logo após
    a linha do header e fim no próximo header (ou fim do corpo)."""
    headers = list(_RE_HEADER.finditer(corpo))
    secoes: list[Secao] = []
    for i, m in enumerate(headers):
        inicio = m.end()
        fim = headers[i + 1].start() if i + 1 < len(headers) else len(corpo)
        secoes.append((m.group(1), inicio, fim))
    return secoes


def _aparar(corpo: str, inicio: int, fim: int) -> tuple[int, int]:
    """Recolhe espaços nas bordas mantendo os offsets coerentes com o slice."""
    while inicio < fim and corpo[inicio].isspace():
        inicio += 1
    while fim > inicio and corpo[fim - 1].isspace():
        fim -= 1
    return inicio, fim


# --- Construção de Segmento (com invariante de âncora) ---------------------
def criar_segmento(
    documento: Documento, titulo: str, inicio: int, fim: int, ordem: int
) -> Segmento:
    ini, f = _aparar(documento.conteudo, inicio, fim)
    texto = documento.conteudo[ini:f]
    # Invariante anti-alucinação: o texto do segmento DEVE existir literalmente
    # no conteúdo, recuperável pelos offsets. O segmentador LLM honra o mesmo
    # contrato (lá, recalculando offsets via str.find do trecho devolvido).
    assert texto == documento.conteudo[ini:f], "offsets incoerentes com o texto"
    return Segmento(
        id=f"{documento.id}#{ordem}",
        documento_id=documento.id,
        tipo=classificar_secao(titulo),
        texto=texto,
        inicio=ini,
        fim=f,
        ordem=ordem,
    )


# --- Ancoragem anti-alucinação (reusada pelo segmentador LLM e pela Q2) ----
def ancorar_trecho(conteudo: str, trecho: str) -> tuple[int, int] | None:
    """Localiza um trecho LITERAL no conteudo e devolve (inicio, fim).
    Tolera diferenças de espaço em branco (quebras de linha vs espaço). Retorna
    None se o trecho não existir — âncora ausente = alucinação, deve ser descartado.

    É o contrato que torna seguro um extrator LLM: o modelo devolve o texto, mas
    quem manda são os offsets recuperados aqui contra a fonte única (conteudo)."""
    limpo = trecho.strip()
    if not limpo:
        return None
    # 1) tentativa direta (exata e barata)
    idx = conteudo.find(limpo)
    if idx >= 0:
        return idx, idx + len(limpo)
    # 2) tolerante: casa a sequência de PALAVRAS do trecho, absorvendo qualquer
    #    caractere não-alfanumérico entre elas (espaços, quebras de linha e
    #    marcação como ** que o LLM costuma descartar ao copiar).
    palavras = re.findall(r"\w+", limpo, flags=re.UNICODE)
    if not palavras:
        return None
    escapadas: list[str] = []
    for palavra in palavras:
        escapadas.append(re.escape(palavra))
    padrao = r"[\W_]+".join(escapadas)
    achado = re.search(padrao, conteudo, flags=re.UNICODE)
    if achado is None:
        return None
    return achado.start(), achado.end()


# --- Implementação concreta do Segmentador ---------------------------------
def segmentar_estrutural(documento: Documento) -> list[Segmento]:
    """Implementação estrutural por cabeçalhos markdown. Conforma a `Segmentador`."""
    secoes = encontrar_secoes(documento.conteudo)
    segmentos: list[Segmento] = []
    for ordem, (titulo, inicio, fim) in enumerate(secoes):
        segmento = criar_segmento(documento, titulo, inicio, fim, ordem)
        segmentos.append(segmento)
    return segmentos
