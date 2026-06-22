"""Avaliação da extração de argumentos (Q2.5) contra testes/gabarito-q2.md.

Mede o que os critérios de qualidade pedem (casos-de-teste.md):
- recall e precisão dos argumentos vs. gabarito;
- concordância de `tipo`;
- taxa de alucinação (trechos sem âncora literal — vem de ExtracaoArgumentos).

Como os títulos extraídos não são idênticos aos do gabarito, o casamento é
SEMÂNTICO: cosseno do embedding do título (reusa a infra de embeddings). O
`LIMIAR_MATCH` é mais um valor CHUTADO — mesmo ponto de calibração futura dos
limiares da Q1.
"""

from __future__ import annotations

import re
from pathlib import Path

from embeddings import EncoderTokens, _tokens_validos, cosseno, media_vetores, normalizar_l2
from modelagem import Argumento, ExtracaoArgumentos

LIMIAR_MATCH = 0.88  # provisório (anisotropia do e5); ver seam de calibração

_RE_DOC = re.compile(r"^##\s+Doc\s+(\d+)\b", re.MULTILINE)
_RE_ARG = re.compile(r"^\d+\.\s+\*\*(.+?)\*\*\s*·\s*`(\w+)`", re.MULTILINE)

# (titulo, tipo) esperado
ArgumentoEsperado = tuple[str, str]


def carregar_gabarito_q2(caminho: str | Path) -> dict[str, list[ArgumentoEsperado]]:
    """Parseia o gabarito (formato `N. **titulo** · `tipo` · resumo`) por documento."""
    texto = Path(caminho).read_text(encoding="utf-8")
    cabecalhos = list(_RE_DOC.finditer(texto))
    gabarito: dict[str, list[ArgumentoEsperado]] = {}
    for i in range(len(cabecalhos)):
        doc_id = cabecalhos[i].group(1)
        inicio = cabecalhos[i].end()
        fim = cabecalhos[i + 1].start() if i + 1 < len(cabecalhos) else len(texto)
        bloco = texto[inicio:fim]
        esperados: list[ArgumentoEsperado] = []
        for achado in _RE_ARG.finditer(bloco):
            esperados.append((achado.group(1), achado.group(2)))
        gabarito[doc_id] = esperados
    return gabarito


def _embed_texto(encoder: EncoderTokens, texto: str) -> list[float] | None:
    saida = encoder(texto)
    vetores = _tokens_validos(saida)
    if not vetores:
        return None
    return normalizar_l2(media_vetores(vetores))


def casar_argumentos(
    extraidos: list[Argumento],
    esperados: list[ArgumentoEsperado],
    encoder: EncoderTokens,
    limiar: float = LIMIAR_MATCH,
) -> list[tuple[Argumento, ArgumentoEsperado]]:
    """Casamento guloso por cosseno do título. Cada extraído casa no máximo um
    esperado (e vice-versa) acima do limiar."""
    emb_esperados: list[list[float] | None] = []
    for titulo, _tipo in esperados:
        emb_esperados.append(_embed_texto(encoder, titulo))

    pares: list[tuple[Argumento, ArgumentoEsperado]] = []
    usados: set[int] = set()
    for arg in extraidos:
        emb_arg = _embed_texto(encoder, arg.titulo)
        if emb_arg is None:
            continue
        melhor_idx = -1
        melhor_cos = limiar
        for idx in range(len(esperados)):
            if idx in usados or emb_esperados[idx] is None:
                continue
            atual = cosseno(emb_arg, emb_esperados[idx])
            if atual >= melhor_cos:
                melhor_cos = atual
                melhor_idx = idx
        if melhor_idx >= 0:
            usados.add(melhor_idx)
            pares.append((arg, esperados[melhor_idx]))
    return pares


def avaliar(
    extracao: ExtracaoArgumentos,
    esperados: list[ArgumentoEsperado],
    encoder: EncoderTokens,
    limiar: float = LIMIAR_MATCH,
) -> dict[str, float]:
    """Recall, precisão, concordância de tipo e taxa de alucinação."""
    extraidos = extracao.argumentos
    pares = casar_argumentos(extraidos, esperados, encoder, limiar)

    casados = len(pares)
    tipos_ok = 0
    for arg, (_titulo, tipo_esperado) in pares:
        if arg.tipo.value == tipo_esperado:
            tipos_ok += 1

    total_gerados = len(extraidos) + extracao.n_rejeitados
    recall = casados / len(esperados) if esperados else 0.0
    precisao = casados / len(extraidos) if extraidos else 0.0
    concordancia_tipo = tipos_ok / casados if casados else 0.0
    taxa_alucinacao = extracao.n_rejeitados / total_gerados if total_gerados else 0.0

    return {
        "recall": recall,
        "precisao": precisao,
        "concordancia_tipo": concordancia_tipo,
        "taxa_alucinacao": taxa_alucinacao,
    }
