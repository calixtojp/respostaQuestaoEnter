"""Extratores baratos de campos estruturados — SEM LLM (regra de negócio 2).

Campos que têm forma previsível (CPF, data, valores monetários) não precisam de
um modelo caro: regex resolve. Cada extrator tenta primeiro o frontmatter (já
parseado por segmentacao.parse_frontmatter) e cai no corpo por regex quando o
campo não está disponível ali — o que faz a função servir também para documentos
sem frontmatter (formato livre).
"""

from __future__ import annotations

import re

_RE_CPF = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")
_RE_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_RE_DATA_BR = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_RE_VALOR = re.compile(r"R\$\s?\d[\d.]*(?:,\d{2})?")


def extrair_cpf(texto: str) -> str | None:
    """Primeiro CPF no formato 000.000.000-00 encontrado no texto."""
    achado = _RE_CPF.search(texto)
    if achado is None:
        return None
    return achado.group(0)


def extrair_data(texto: str) -> str | None:
    """Primeira data encontrada, normalizada para ISO (YYYY-MM-DD).
    Aceita ISO direto e dd/mm/aaaa."""
    iso = _RE_DATA_ISO.search(texto)
    if iso is not None:
        return iso.group(0)
    br = _RE_DATA_BR.search(texto)
    if br is not None:
        dia, mes, ano = br.group(1), br.group(2), br.group(3)
        return f"{ano}-{mes}-{dia}"
    return None


def extrair_valores(texto: str) -> list[str]:
    """Todos os valores monetários (R$ ...) na ordem em que aparecem."""
    valores: list[str] = []
    for achado in _RE_VALOR.finditer(texto):
        valores.append(achado.group(0))
    return valores


# --- Spans (offsets) — usados pelo segmentador para criar segmentos baratos ---
def span_data(texto: str) -> tuple[int, int] | None:
    """Offset (inicio, fim) da primeira data literal no texto (ISO ou dd/mm/aaaa)."""
    achado = _RE_DATA_ISO.search(texto)
    if achado is None:
        achado = _RE_DATA_BR.search(texto)
    if achado is None:
        return None
    return achado.start(), achado.end()


def spans_valores(texto: str) -> list[tuple[int, int]]:
    """Offsets (inicio, fim) de todos os valores monetários no texto."""
    spans: list[tuple[int, int]] = []
    for achado in _RE_VALOR.finditer(texto):
        spans.append((achado.start(), achado.end()))
    return spans
