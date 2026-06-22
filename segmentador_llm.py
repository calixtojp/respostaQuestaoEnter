"""Segmentador híbrido: LLM só para o que exige semântica (regra de negócio 2).

Conforma à interface `Segmentador = Callable[[Documento], list[Segmento]]`, então
substitui `segmentar_estrutural` sem o resto do pipeline mudar. A divisão:

- **Semântico (LLM)**: tese principal, nome das partes, relatório, fundamentação,
  dispositivo. O modelo devolve o TRECHO LITERAL; os offsets são recuperados por
  `segmentacao.ancorar_trecho` contra o `conteudo` (fonte única). Trecho que não
  ancora é descartado (anti-alucinação).
- **Barato (regex)**: data e valores monetários, via `extratores` — sem LLM.

Não depende de cabeçalhos markdown: funciona em documento de formato livre.
"""

from __future__ import annotations

from typing import Callable

from extratores import span_data, spans_valores
from llm import gerar_json
from modelagem import Documento, Segmento, TipoSegmento
from segmentacao import ancorar_trecho

# tipos semânticos que pedimos ao modelo (string -> TipoSegmento)
_MAPA_TIPOS: dict[str, TipoSegmento] = {
    "tese_principal": TipoSegmento.TESE_PRINCIPAL,
    "nome_partes": TipoSegmento.NOME_PARTES,
    "relatorio": TipoSegmento.RELATORIO,
    "fundamentacao": TipoSegmento.FUNDAMENTO,
    "fundamento": TipoSegmento.FUNDAMENTO,
    "dispositivo": TipoSegmento.DISPOSITIVO,
}

_PROMPT = """Você recebe o CORPO de um documento jurídico brasileiro.
Identifique as seções SEMÂNTICAS presentes e, para cada uma, devolva o seu tipo e
o TRECHO LITERAL — copiado EXATAMENTE do texto, sem parafrasear, sem corrigir, sem
abreviar. Inclua apenas as seções que de fato existirem no texto.

Tipos possíveis: tese_principal, nome_partes, relatorio, fundamentacao, dispositivo.

Não invente texto. Cada `trecho` precisa existir caractere a caractere no documento.

DOCUMENTO:
---
{corpo}
---"""

_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "tipo": {"type": "STRING", "enum": list(_MAPA_TIPOS.keys())},
            "trecho": {"type": "STRING"},
        },
        "required": ["tipo", "trecho"],
    },
}

GeradorJSON = Callable[[str, dict], object]


def _segmento(documento: Documento, tipo: TipoSegmento, inicio: int, fim: int, ordem: int) -> Segmento:
    return Segmento(
        id=f"{documento.id}#{ordem}",
        documento_id=documento.id,
        tipo=tipo,
        texto=documento.conteudo[inicio:fim],
        inicio=inicio,
        fim=fim,
        ordem=ordem,
    )


def _segmentos_semanticos(documento: Documento, gerar: GeradorJSON) -> list[tuple[TipoSegmento, int, int]]:
    """Chama o LLM, mapeia tipos e ANCORA cada trecho. Descarta o que não ancora."""
    prompt = _PROMPT.format(corpo=documento.conteudo)
    bruto = gerar(prompt, _SCHEMA)
    achados: list[tuple[TipoSegmento, int, int]] = []
    for item in bruto:
        rotulo = item.get("tipo", "")
        if rotulo not in _MAPA_TIPOS:
            continue
        trecho = item.get("trecho", "")
        intervalo = ancorar_trecho(documento.conteudo, trecho)
        if intervalo is None:  # âncora ausente -> alucinação, descarta
            continue
        achados.append((_MAPA_TIPOS[rotulo], intervalo[0], intervalo[1]))
    return achados


def _segmentos_baratos(documento: Documento) -> list[tuple[TipoSegmento, int, int]]:
    """Data e valores monetários por regex — sem LLM (regra de negócio 2)."""
    achados: list[tuple[TipoSegmento, int, int]] = []
    span = span_data(documento.conteudo)
    if span is not None:
        achados.append((TipoSegmento.DATA, span[0], span[1]))
    for ini, fim in spans_valores(documento.conteudo):
        achados.append((TipoSegmento.VALORES, ini, fim))
    return achados


def _coalescer(
    achados: list[tuple[TipoSegmento, int, int]]
) -> list[tuple[TipoSegmento, int, int]]:
    """Funde corridas consecutivas (já ordenadas) do MESMO tipo num só span — o
    LLM às vezes devolve uma seção fatiada em vários trechos."""
    fundidos: list[tuple[TipoSegmento, int, int]] = []
    for tipo, ini, fim in achados:
        if fundidos and fundidos[-1][0] == tipo:
            t_ant, ini_ant, fim_ant = fundidos[-1]
            fundidos[-1] = (t_ant, ini_ant, max(fim_ant, fim))
        else:
            fundidos.append((tipo, ini, fim))
    return fundidos


def segmentar_llm(documento: Documento, gerar: GeradorJSON = gerar_json) -> list[Segmento]:
    """Segmentador da interface `Segmentador`. `gerar` é injetável (black box →
    testável com stub offline)."""
    achados = _segmentos_semanticos(documento, gerar)
    for tipo, ini, fim in _segmentos_baratos(documento):
        achados.append((tipo, ini, fim))

    achados.sort(key=lambda t: t[1])  # por offset de início
    achados = _coalescer(achados)

    segmentos: list[Segmento] = []
    for ordem in range(len(achados)):
        tipo, ini, fim = achados[ordem]
        segmentos.append(_segmento(documento, tipo, ini, fim, ordem))
    return segmentos
