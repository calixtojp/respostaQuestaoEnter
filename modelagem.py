"""Modelagem de domínio para seleção e comparação de segmentos.

A ideia central (inversão das tarefas): primeiro SEGMENTAMOS o documento em
partes rotuladas (tese principal, data, valores, argumento jurídico, etc.) e só
depois comparamos/classificamos POR SEGMENTO, não o documento bruto inteiro.

Princípio de fonte única: o texto canônico vive em `Documento.conteudo`. Um
`Segmento` guarda apenas os offsets (inicio/fim) e uma cópia literal do trecho
(útil como âncora anti-alucinação). Assim o trecho é sempre verificável por
substring contra o documento original.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TipoSegmento(str, Enum):
    """Rótulo funcional de um segmento. Une os campos da Q1 e os da Q2 sob o
    mesmo tipo de objeto (um segmento rotulado)."""

    # Q1 — campos estruturados de petições/peças
    TESE_PRINCIPAL = "tese_principal"
    NOME_PARTES = "nome_partes"
    DATA = "data"
    VALORES = "valores"
    FUNDAMENTO = "fundamento"
    # Q2 — partes de sentenças
    RELATORIO = "relatorio"
    ARGUMENTO_JURIDICO = "argumento_juridico"
    DISPOSITIVO = "dispositivo"
    # genérico
    OUTRO = "outro"


@dataclass
class Embedding:
    """Vetor + metadados. Os metadados são essenciais para versionamento:
    dois embeddings só são comparáveis se vierem do MESMO modelo/versão/dim."""

    vetor: list[float]
    modelo: str          # ex.: "intfloat/multilingual-e5-large"
    dim: int
    normalizado: bool = False  # L2-normalizado? (necessário p/ cosseno)


@dataclass
class Segmento:
    """Uma parte rotulada do documento. Offsets apontam para Documento.conteudo."""

    id: str
    documento_id: str
    tipo: TipoSegmento
    texto: str                 # cópia literal do trecho (âncora verificável)
    inicio: int                # offset de caractere (início, inclusivo)
    fim: int                   # offset de caractere (fim, exclusivo)
    ordem: int                 # posição do segmento no documento
    confianca: float = 1.0     # confiança da segmentação/rotulagem

    # duas visões do segmento (ver embeddings.py):
    emb_isolada: Embedding | None = None     # segmento sozinho, sem contexto
    emb_contextual: Embedding | None = None  # late chunking: ciente do documento


@dataclass
class Documento:
    id: str
    conteudo: str              # texto canônico (fonte única da verdade)
    caso_jur_id: str
    tipo: str                  # petição inicial, sentença, etc.
    cliente_cpf: str | None = None
    data: str | None = None    # ISO YYYY-MM-DD; usado p/ escolher o representante

    segmentos: list[Segmento] = field(default_factory=list)

    # embedding-resumo do documento inteiro (pré-filtro de candidatos).
    emb_geral: Embedding | None = None


@dataclass
class CasoJuridico:
    id: str
    cliente_id: str
    documentos: list[str] = field(default_factory=list)  # ids de Documento


@dataclass
class Cliente:
    cpf: str
    nome: str


# --- Questão 2: argumentos extraídos de sentenças -------------------------
class TipoArgumento(str, Enum):
    """Taxonomia de argumentos jurídicos (ver testes/gabarito-q2.md)."""

    PROBATORIO = "probatorio"
    MERITO = "merito"
    JURISPRUDENCIAL = "jurisprudencial"
    PRINCIPIOLOGICO = "principiologico"
    PROCESSUAL = "processual"
    QUANTUM = "quantum"
    OUTRO = "outro"


class StatusRevisao(str, Enum):
    """Estado da revisão humana de um argumento extraído (Q2.4)."""

    PENDENTE = "pendente"
    APROVADO = "aprovado"
    EDITADO = "editado"
    REJEITADO = "rejeitado"


@dataclass
class Argumento:
    """Argumento do juiz extraído da fundamentação. `trecho_citado` é a âncora
    literal (deve existir no conteudo); offsets recuperados por str.find."""

    id: str
    documento_id: str
    titulo: str
    resumo: str
    trecho_citado: str          # cópia literal (âncora anti-alucinação)
    inicio: int                 # offset de caractere no conteudo (inclusivo)
    fim: int                    # offset de caractere no conteudo (exclusivo)
    posicao: int                # ordem do argumento na fundamentação
    tipo: TipoArgumento
    confianca: float
    status: StatusRevisao = StatusRevisao.PENDENTE


@dataclass
class ExtracaoArgumentos:
    """Resultado versionado de uma extração (Q2.6). Reprocessar com outro
    prompt/modelo/schema gera uma nova extração comparável."""

    documento_id: str
    argumentos: list[Argumento] = field(default_factory=list)
    modelo: str = ""
    versao_prompt: str = ""
    versao_schema: str = ""
    criado_em: str = ""         # timestamp ISO
    n_rejeitados: int = 0       # argumentos descartados por falta de âncora


# --- Regra de negócio: detecção de cópia ----------------------------------
@dataclass
class VinculoDocumentos:
    """Vínculo persistido entre dois documentos parecidos (cópia/versão).
    Não funde nem exclui: liga e elege um representante."""

    doc_a_id: str
    doc_b_id: str
    classe: str                 # valor de ClasseSimilaridade
    representante_id: str       # documento eleito (o mais novo)
    score: float                # similaridade que motivou o vínculo


@dataclass
class Alerta:
    """Aviso disparado a um responsável pelo caso/cliente ao detectar cópia."""

    caso_id: str
    cliente_cpf: str | None
    doc_novo_id: str
    doc_existente_id: str
    mensagem: str


# --- Seam de calibração (NÃO implementada; valores provisórios) -----------
@dataclass
class Limiares:
    """Limiares de decisão da Q1. Hoje são valores CHUTADOS, calibrados à mão
    contra testes/gabarito-q1.md. No futuro, uma `calibrar()` os derivaria de
    dados rotulados e devolveria uma instância deste tipo — por isso eles vivem
    aqui, e não como constantes soltas espalhadas pelo código."""

    copia: float = 0.8           # Jaccard léxico >= copia -> cópia
    mesma_tese: float = 0.95     # cos da tese isolada >= mesma_tese -> modificada
    doc_modificado: float = 0.96  # fallback sem tese: cos emb_geral


LIMIARES_PADRAO = Limiares()
