"""Comparação de documentos (Q1): cascata cópia / versão modificada / diferente.

Orquestra as duas etapas no estilo funcional do projeto:

  0. Portão léxico (lexico.py): Jaccard sobre shingles. Se altíssimo -> CÓPIA,
     e paramos aqui — sem pagar o custo de embeddings.
  1. Etapa semântica: alinhamos os segmentos POR TIPO (tese↔tese, etc.) e
     comparamos campo a campo com os embeddings. A tese isolada é o sinal
     primário para separar "versão modificada" de "diferente".

Regra de domínio (Q1): a comparação é intra-caso. Documentos de casos
diferentes são sempre "diferente".

O custo de embeddings fica atrás de uma black box `Embedder` (Documento ->
Documento), injetada por quem chama. Assim este módulo não conhece o encoder e
só paga o custo quando a etapa semântica é realmente alcançada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from embeddings import cosseno
from lexico import similaridade_lexica
from modelagem import LIMIARES_PADRAO, Documento, Limiares, Segmento, TipoSegmento


class ClasseSimilaridade(str, Enum):
    COPIA = "cópia"
    VERSAO_MODIFICADA = "versão modificada"
    DIFERENTE = "diferente"


# Os limiares de decisão vivem em modelagem.Limiares (seam de calibração):
# LIMIARES_PADRAO traz os valores provisórios chutados contra testes/gabarito-q1.md.


# Black box: aplica embeddings a um Documento (custo adiado para a etapa semântica)
Embedder = Callable[[Documento], Documento]


@dataclass
class SimilaridadeCampo:
    """Similaridade de um tipo de segmento alinhado entre os dois documentos."""

    tipo: TipoSegmento
    cos_isolada: float
    cos_contextual: float


@dataclass
class ResultadoComparacao:
    """Saída estruturada e interpretável da comparação (alimenta a Q1.5)."""

    doc_a_id: str
    doc_b_id: str
    mesmo_caso: bool
    classe: ClasseSimilaridade
    motivo: str
    sim_lexica: float
    sim_tese: float | None = None
    sim_documento: float | None = None
    campos: list[SimilaridadeCampo] = field(default_factory=list)


# --- Alinhamento e similaridade por campo ----------------------------------
def mesmo_caso(doc_a: Documento, doc_b: Documento) -> bool:
    if not doc_a.caso_jur_id or not doc_b.caso_jur_id:
        return False
    return doc_a.caso_jur_id == doc_b.caso_jur_id


def segmentos_por_tipo(documento: Documento) -> dict[TipoSegmento, list[Segmento]]:
    """Agrupa os segmentos do documento por tipo (preserva a ordem do documento)."""
    mapa: dict[TipoSegmento, list[Segmento]] = {}
    for seg in documento.segmentos:
        if seg.tipo not in mapa:
            mapa[seg.tipo] = []
        mapa[seg.tipo].append(seg)
    return mapa


def melhor_cosseno(
    segs_a: list[Segmento], segs_b: list[Segmento], qual: str
) -> float:
    """Alinhamento guloso: maior cosseno entre os pares de segmentos do mesmo
    tipo. `qual` é o nome do atributo de embedding ('emb_isolada'/'emb_contextual')."""
    melhor = -1.0
    for seg_a in segs_a:
        for seg_b in segs_b:
            emb_a = getattr(seg_a, qual)
            emb_b = getattr(seg_b, qual)
            if emb_a is None or emb_b is None:
                continue
            atual = cosseno(emb_a.vetor, emb_b.vetor)
            if atual > melhor:
                melhor = atual
    return melhor


def similaridades_por_campo(
    doc_a: Documento, doc_b: Documento
) -> list[SimilaridadeCampo]:
    """Para cada tipo presente nos dois documentos, a similaridade do campo."""
    por_tipo_a = segmentos_por_tipo(doc_a)
    por_tipo_b = segmentos_por_tipo(doc_b)
    campos: list[SimilaridadeCampo] = []
    for tipo in por_tipo_a:
        if tipo not in por_tipo_b:
            continue
        cos_iso = melhor_cosseno(por_tipo_a[tipo], por_tipo_b[tipo], "emb_isolada")
        cos_ctx = melhor_cosseno(por_tipo_a[tipo], por_tipo_b[tipo], "emb_contextual")
        campos.append(SimilaridadeCampo(tipo=tipo, cos_isolada=cos_iso, cos_contextual=cos_ctx))
    return campos


def sim_tese(campos: list[SimilaridadeCampo]) -> float | None:
    """Similaridade da tese principal (isolada), o sinal semântico primário."""
    for campo in campos:
        if campo.tipo == TipoSegmento.TESE_PRINCIPAL:
            return campo.cos_isolada
    return None


# --- Classificação ---------------------------------------------------------
def classificar_semantica(
    sim_da_tese: float | None,
    sim_do_documento: float | None,
    limiares: Limiares = LIMIARES_PADRAO,
) -> tuple[ClasseSimilaridade, str]:
    """Decide modificada × diferente. Tese é o sinal primário; sem tese, cai no
    documento inteiro. Sem nenhum dos dois, assume diferente."""
    if sim_da_tese is not None:
        if sim_da_tese >= limiares.mesma_tese:
            return (
                ClasseSimilaridade.VERSAO_MODIFICADA,
                f"mesma tese (cos isolada {sim_da_tese:.3f} >= {limiares.mesma_tese})",
            )
        return (
            ClasseSimilaridade.DIFERENTE,
            f"teses distintas (cos isolada {sim_da_tese:.3f} < {limiares.mesma_tese})",
        )
    if sim_do_documento is not None:
        if sim_do_documento >= limiares.doc_modificado:
            return (
                ClasseSimilaridade.VERSAO_MODIFICADA,
                f"sem tese; documento semelhante (cos {sim_do_documento:.3f} >= {limiares.doc_modificado})",
            )
        return (
            ClasseSimilaridade.DIFERENTE,
            f"sem tese; documentos distintos (cos {sim_do_documento:.3f} < {limiares.doc_modificado})",
        )
    return (ClasseSimilaridade.DIFERENTE, "sem segmentos comparáveis")


# --- Orquestração da cascata -----------------------------------------------
def comparar(
    doc_a: Documento,
    doc_b: Documento,
    embedder: Embedder,
    forcar_intra_caso: bool = True,
    limiares: Limiares = LIMIARES_PADRAO,
) -> ResultadoComparacao:
    """Cascata completa da Q1: caso -> portão léxico -> etapa semântica.
    Embeddings só são calculados (via `embedder`) se a etapa semântica for
    alcançada (não é cópia e é intra-caso)."""
    sim_lex = similaridade_lexica(doc_a.conteudo, doc_b.conteudo)
    intra = mesmo_caso(doc_a, doc_b)

    # Regra de domínio: cross-caso é sempre diferente (e nem rodamos o semântico).
    if forcar_intra_caso and not intra:
        return ResultadoComparacao(
            doc_a_id=doc_a.id,
            doc_b_id=doc_b.id,
            mesmo_caso=intra,
            classe=ClasseSimilaridade.DIFERENTE,
            motivo="casos diferentes (comparação Q1 é intra-caso)",
            sim_lexica=sim_lex,
        )

    # Etapa 0: portão léxico. Cópia decide aqui, sem embeddings.
    if sim_lex >= limiares.copia:
        return ResultadoComparacao(
            doc_a_id=doc_a.id,
            doc_b_id=doc_b.id,
            mesmo_caso=intra,
            classe=ClasseSimilaridade.COPIA,
            motivo=f"Jaccard léxico {sim_lex:.3f} >= {limiares.copia}",
            sim_lexica=sim_lex,
        )

    # Etapa semântica: agora sim pagamos o custo dos embeddings.
    doc_a = embedder(doc_a)
    doc_b = embedder(doc_b)
    campos = similaridades_por_campo(doc_a, doc_b)
    sim_da_tese = sim_tese(campos)
    sim_do_documento = None
    if doc_a.emb_geral is not None and doc_b.emb_geral is not None:
        sim_do_documento = cosseno(doc_a.emb_geral.vetor, doc_b.emb_geral.vetor)

    classe, motivo = classificar_semantica(sim_da_tese, sim_do_documento, limiares)
    return ResultadoComparacao(
        doc_a_id=doc_a.id,
        doc_b_id=doc_b.id,
        mesmo_caso=intra,
        classe=classe,
        motivo=motivo,
        sim_lexica=sim_lex,
        sim_tese=sim_da_tese,
        sim_documento=sim_do_documento,
        campos=campos,
    )
