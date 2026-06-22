"""Portão léxico: detecção barata de cópias via Jaccard sobre shingles.

Primeira etapa da cascata de comparação (Q1). É puramente léxico — não usa
embeddings nem semântica. A ideia: representar cada texto como o CONJUNTO dos
seus n-gramas de palavras (shingles) e medir a sobreposição por Jaccard.

Robusto a pequenas edições (um nome/valor trocado afeta só os poucos shingles
que o contêm) mas barato (O(n) para montar, interseção de conjuntos). A própria
magnitude do Jaccard separa os casos:
    ~1.0   cópia (texto quase idêntico)
    médio  versão modificada (mesma base, trechos diferentes)
    baixo  documento diferente

Aqui só decidimos o EXTREMO ALTO (cópia). Distinguir "versão modificada" de
"diferente" fica para a etapa semântica.
"""

from __future__ import annotations

import re
import unicodedata

# n-grama de palavras: tupla de k tokens consecutivos
Shingle = tuple[str, ...]

_RE_NAO_PALAVRA = re.compile(r"[^0-9a-z]+")

# Provisórios: calibrar contra testes/gabarito-q1.md.
LIMIAR_COPIA = 0.8
TAMANHO_SHINGLE = 3


def normalizar_texto(texto: str) -> str:
    """Caixa baixa, sem acento, pontuação -> espaço, espaços colapsados.
    Absorve diferenças de formatação; preserva palavras (nome/valor trocado
    continua mudando o texto — por isso cópia != versão modificada)."""
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = ""
    for caractere in decomposto:
        if not unicodedata.combining(caractere):
            sem_acento += caractere
    minusculo = sem_acento.lower()
    sem_pontuacao = _RE_NAO_PALAVRA.sub(" ", minusculo)
    return sem_pontuacao.strip()


def tokenizar(texto: str) -> list[str]:
    """Quebra o texto normalizado em tokens de palavra."""
    normalizado = normalizar_texto(texto)
    if not normalizado:
        return []
    return normalizado.split()


def gerar_shingles(tokens: list[str], k: int = TAMANHO_SHINGLE) -> set[Shingle]:
    """Conjunto de n-gramas de palavras (janelas de k tokens consecutivos).
    Com menos de k tokens, devolve um único shingle com tudo que houver."""
    if not tokens:
        return set()
    if len(tokens) < k:
        return {tuple(tokens)}
    shingles: set[Shingle] = set()
    ultimo_inicio = len(tokens) - k
    for i in range(ultimo_inicio + 1):
        janela = tuple(tokens[i : i + k])
        shingles.add(janela)
    return shingles


def jaccard(a: set[Shingle], b: set[Shingle]) -> float:
    """|A ∩ B| / |A ∪ B|. Dois conjuntos vazios -> 1.0 (idênticos)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersecao = a & b
    uniao = a | b
    return len(intersecao) / len(uniao)


def similaridade_lexica(texto_a: str, texto_b: str, k: int = TAMANHO_SHINGLE) -> float:
    """Jaccard sobre shingles de palavras dos dois textos. Resultado em [0, 1]."""
    shingles_a = gerar_shingles(tokenizar(texto_a), k)
    shingles_b = gerar_shingles(tokenizar(texto_b), k)
    return jaccard(shingles_a, shingles_b)


def eh_provavel_copia(
    texto_a: str, texto_b: str, limiar: float = LIMIAR_COPIA, k: int = TAMANHO_SHINGLE
) -> bool:
    """Portão da cascata: True se a similaridade léxica >= limiar (provável cópia).
    Quando False, segue para a etapa semântica."""
    return similaridade_lexica(texto_a, texto_b, k) >= limiar
