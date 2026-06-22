"""Extração de argumentos de sentenças (Questão 2).

Inversão habitual do projeto: primeiro SEGMENTAMOS (a fundamentação é um
`Segmento`), depois extraímos os argumentos de dentro dela. A extração usa LLM
(black box `gerar`), mas o que vale são as ÂNCORAS: cada `trecho_citado` é
recuperado por `segmentacao.ancorar_trecho` contra o `conteudo` — argumento sem
âncora literal é descartado (anti-alucinação, Q2.2).

A saída é um `ExtracaoArgumentos` versionado (modelo + versão de prompt/schema),
para permitir reprocessar e comparar quando algo mudar (Q2.6).
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable

from llm import MODELO, gerar_json
from modelagem import (
    Argumento,
    Documento,
    ExtracaoArgumentos,
    StatusRevisao,
    TipoArgumento,
    TipoSegmento,
)
from segmentacao import ancorar_trecho

# Versionamento (Q2.6): mudar o prompt/schema => bumpar estas versões.
VERSAO_PROMPT = "args-v1"
VERSAO_SCHEMA = "args-v1"

# Acima disto, a fundamentação é dividida em janelas (Q2.3 — sentenças longas).
LIMITE_CARACTERES = 6000

_TAXONOMIA = ["probatorio", "merito", "jurisprudencial", "principiologico", "processual", "quantum"]

_PROMPT = """Você recebe a FUNDAMENTAÇÃO de uma sentença judicial brasileira.
Extraia os principais argumentos usados pelo juiz. Cada argumento DISTINTO é um item.

Regras:
- NÃO funda dois argumentos distintos num só, nem fragmente um argumento em vários.
- `trecho_citado` deve ser copiado EXATAMENTE do texto (verbatim), sem parafrasear.
- NÃO invente: todo trecho precisa existir caractere a caractere na fundamentação.
- `tipo` deve ser um de: {taxonomia}.
- `confianca` entre 0 e 1.

Para cada argumento devolva: titulo (curto), resumo (1 frase), trecho_citado, tipo, confianca.

FUNDAMENTAÇÃO:
---
{texto}
---"""

_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "titulo": {"type": "STRING"},
            "resumo": {"type": "STRING"},
            "trecho_citado": {"type": "STRING"},
            "tipo": {"type": "STRING", "enum": _TAXONOMIA},
            "confianca": {"type": "NUMBER"},
        },
        "required": ["titulo", "resumo", "trecho_citado", "tipo", "confianca"],
    },
}

GeradorJSON = Callable[[str, dict], object]


# --- Helpers ---------------------------------------------------------------
def _tipo_argumento(valor: str) -> TipoArgumento:
    for tipo in TipoArgumento:
        if tipo.value == valor:
            return tipo
    return TipoArgumento.OUTRO


def _texto_fundamentacao(documento: Documento) -> str | None:
    """Texto da fundamentação: span-união de todos os segmentos FUNDAMENTO
    (defensivo, caso o segmentador a tenha devolvido em pedaços)."""
    inicios: list[int] = []
    fins: list[int] = []
    for seg in documento.segmentos:
        if seg.tipo == TipoSegmento.FUNDAMENTO:
            inicios.append(seg.inicio)
            fins.append(seg.fim)
    if not inicios:
        return None
    return documento.conteudo[min(inicios):max(fins)]


def dividir_para_contexto(texto: str, limite: int = LIMITE_CARACTERES) -> list[str]:
    """Janela por sentenças, com 1 sentença de sobreposição, para textos que não
    cabem no orçamento de contexto (Q2.3). Texto curto -> uma janela só."""
    if len(texto) <= limite:
        return [texto]
    sentencas = re.split(r"(?<=[.!?])\s+", texto)
    janelas: list[str] = []
    atual: list[str] = []
    tamanho = 0
    for sentenca in sentencas:
        if tamanho + len(sentenca) > limite and atual:
            janelas.append(" ".join(atual))
            atual = [atual[-1]]  # sobreposição de 1 sentença
            tamanho = len(atual[0])
        atual.append(sentenca)
        tamanho += len(sentenca)
    if atual:
        janelas.append(" ".join(atual))
    return janelas


def _sobrepoe(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def ancorar_argumento(
    conteudo: str, dados: dict, documento_id: str, posicao: int
) -> Argumento | None:
    """Constrói um Argumento ancorando `trecho_citado` no conteudo. Retorna None
    se o trecho não existir literalmente (alucinação)."""
    trecho = dados.get("trecho_citado", "")
    intervalo = ancorar_trecho(conteudo, trecho)
    if intervalo is None:
        return None
    inicio, fim = intervalo
    return Argumento(
        id=f"{documento_id}@arg{posicao}",
        documento_id=documento_id,
        titulo=dados.get("titulo", ""),
        resumo=dados.get("resumo", ""),
        trecho_citado=conteudo[inicio:fim],
        inicio=inicio,
        fim=fim,
        posicao=posicao,
        tipo=_tipo_argumento(dados.get("tipo", "")),
        confianca=float(dados.get("confianca", 0.0)),
        status=StatusRevisao.PENDENTE,
    )


# --- Orquestração ----------------------------------------------------------
def extrair_argumentos(documento: Documento, gerar: GeradorJSON = gerar_json) -> ExtracaoArgumentos:
    """Extrai os argumentos da fundamentação do documento. `gerar` é injetável."""
    fundamentacao = _texto_fundamentacao(documento)
    criado_em = datetime.now(timezone.utc).isoformat()
    base = ExtracaoArgumentos(
        documento_id=documento.id,
        modelo=MODELO,
        versao_prompt=VERSAO_PROMPT,
        versao_schema=VERSAO_SCHEMA,
        criado_em=criado_em,
    )
    if fundamentacao is None:
        return base

    # 1) coleta argumentos brutos de cada janela (Q2.3)
    brutos: list[dict] = []
    for janela in dividir_para_contexto(fundamentacao):
        prompt = _PROMPT.format(taxonomia=", ".join(_TAXONOMIA), texto=janela)
        resposta = gerar(prompt, _SCHEMA)
        for item in resposta:
            brutos.append(item)

    # 2) ancora (anti-alucinação) e deduplica por sobreposição de span
    argumentos: list[Argumento] = []
    spans: list[tuple[int, int]] = []
    rejeitados = 0
    for dados in brutos:
        candidato = ancorar_argumento(documento.conteudo, dados, documento.id, len(argumentos))
        if candidato is None:
            rejeitados += 1
            continue
        span = (candidato.inicio, candidato.fim)
        duplicado = False
        for existente in spans:
            if _sobrepoe(span, existente):
                duplicado = True
                break
        if duplicado:
            continue
        spans.append(span)
        argumentos.append(candidato)

    # 3) ordena por posição no texto e renumera posicao/id
    argumentos.sort(key=lambda a: a.inicio)
    finais: list[Argumento] = []
    for posicao in range(len(argumentos)):
        arg = argumentos[posicao]
        finais.append(replace(arg, posicao=posicao, id=f"{documento.id}@arg{posicao}"))

    return replace(base, argumentos=finais, n_rejeitados=rejeitados)


# --- Revisão humana (Q2.4 / CT2.5) -----------------------------------------
def aprovar(argumento: Argumento) -> Argumento:
    return replace(argumento, status=StatusRevisao.APROVADO)


def rejeitar(argumento: Argumento) -> Argumento:
    return replace(argumento, status=StatusRevisao.REJEITADO)


def editar(argumento: Argumento, **campos: object) -> Argumento:
    return replace(argumento, status=StatusRevisao.EDITADO, **campos)
