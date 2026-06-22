"""Embeddings por segmento (isolada e contextual via late chunking) + documento.

Abstração central: um encoder em NÍVEL DE TOKEN — uma black box
`EncoderTokens = str -> SaidaTokens`, que devolve um vetor por token e o span
(offset de caractere) de cada token no texto de entrada. Tudo o mais é derivado
disso por funções puras:

- isolada:    roda o encoder só no texto do segmento -> média dos tokens.
- contextual: roda o encoder no DOCUMENTO INTEIRO uma vez (late chunking); cada
              token já "viu" o documento todo via atenção; depois mediamos só os
              tokens que caem no intervalo do segmento. Foco no segmento + contexto
              global.
- documento:  média de TODOS os tokens da passada do documento (pooling simples
              uniforme = embedding do documento completo).
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, replace
from typing import Callable

from modelagem import Documento, Embedding, Segmento


@dataclass
class SaidaTokens:
    """Saída de um encoder em nível de token para UM texto."""

    vetores: list[list[float]]      # um vetor por token
    spans: list[tuple[int, int]]    # (char_inicio, char_fim) de cada token


# Black box: texto -> embeddings de token + offsets de caractere
EncoderTokens = Callable[[str], SaidaTokens]


# --- Operações vetoriais puras ---------------------------------------------
def normalizar_l2(vetor: list[float]) -> list[float]:
    soma_quadrados = 0.0
    for x in vetor:
        soma_quadrados += x * x
    norma = math.sqrt(soma_quadrados)
    if norma == 0:
        return list(vetor)
    resultado: list[float] = []
    for x in vetor:
        resultado.append(x / norma)
    return resultado


def media_vetores(vetores: list[list[float]]) -> list[float]:
    """Pooling simples: média uniforme dos vetores (sem pesos)."""
    if not vetores:
        raise ValueError("sem vetores para pooling")
    dim = len(vetores[0])
    soma = [0.0] * dim
    for vetor in vetores:
        for i in range(dim):
            soma[i] += vetor[i]
    media: list[float] = []
    for valor in soma:
        media.append(valor / len(vetores))
    return media


def cosseno(a: list[float], b: list[float]) -> float:
    produto = 0.0
    norma_a = 0.0
    norma_b = 0.0
    for i in range(len(a)):
        produto += a[i] * b[i]
        norma_a += a[i] * a[i]
        norma_b += b[i] * b[i]
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return produto / (math.sqrt(norma_a) * math.sqrt(norma_b))


# --- Seleção de tokens / montagem de Embedding -----------------------------
def _tokens_validos(saida: SaidaTokens) -> list[list[float]]:
    """Descarta tokens especiais/vazios (span degenerado, ex.: [CLS]/[SEP])."""
    vetores: list[list[float]] = []
    for vetor, (tok_ini, tok_fim) in zip(saida.vetores, saida.spans):
        if tok_fim > tok_ini:
            vetores.append(vetor)
    return vetores


def tokens_no_intervalo(saida: SaidaTokens, inicio: int, fim: int) -> list[list[float]]:
    """Vetores dos tokens cujo span cai dentro de [inicio, fim)."""
    vetores: list[list[float]] = []
    for vetor, (tok_ini, tok_fim) in zip(saida.vetores, saida.spans):
        if tok_fim <= tok_ini:
            continue
        if tok_ini >= inicio and tok_fim <= fim:
            vetores.append(vetor)
    return vetores


def _montar_embedding(vetores: list[list[float]], modelo: str) -> Embedding:
    media = normalizar_l2(media_vetores(vetores))
    return Embedding(vetor=media, modelo=modelo, dim=len(media), normalizado=True)


# --- As três embeddings ----------------------------------------------------
def embedding_isolada(encoder: EncoderTokens, segmento: Segmento, modelo: str) -> Embedding:
    """Segmento sozinho: passada própria, sem nenhum contexto do documento."""
    saida = encoder(segmento.texto)
    return _montar_embedding(_tokens_validos(saida), modelo)


def embedding_contextual(saida_doc: SaidaTokens, segmento: Segmento, modelo: str) -> Embedding:
    """Late chunking: tokens do segmento extraídos da passada do documento."""
    vetores = tokens_no_intervalo(saida_doc, segmento.inicio, segmento.fim)
    if not vetores:
        raise ValueError(f"nenhum token no intervalo do segmento {segmento.id}")
    return _montar_embedding(vetores, modelo)


def embedding_documento(saida_doc: SaidaTokens, modelo: str) -> Embedding:
    """Documento completo: média de todos os tokens da passada do documento."""
    return _montar_embedding(_tokens_validos(saida_doc), modelo)


# --- Alto nível ------------------------------------------------------------
def processar_embeddings(
    documento: Documento, encoder: EncoderTokens, modelo: str
) -> Documento:
    saida_doc = encoder(documento.conteudo)  # 1 passada -> contextual + geral
    novos: list[Segmento] = []
    for seg in documento.segmentos:
        isolada = embedding_isolada(encoder, seg, modelo)
        contextual = embedding_contextual(saida_doc, seg, modelo)
        novos.append(replace(seg, emb_isolada=isolada, emb_contextual=contextual))
    geral = embedding_documento(saida_doc, modelo)
    return replace(documento, segmentos=novos, emb_geral=geral)


# --- Encoders (implementações da black box) --------------------------------
_RE_TOKEN = re.compile(r"\S+")


def encoder_tokens_dummy(dim: int = 64, peso_contexto: float = 0.25) -> EncoderTokens:
    """Encoder em nível de token SEM significado semântico. Tokeniza por espaços
    e mistura um pouco dos vizinhos em cada token, simulando grosseiramente o
    efeito de contexto — só para validar o pipeline e o late chunking offline.
    NÃO substitui um modelo real."""

    def _hash_vetor(token: str) -> list[float]:
        h = hashlib.sha256(token.encode("utf-8")).digest()
        vetor: list[float] = []
        for i in range(dim):
            vetor.append(h[i % len(h)] / 255.0)
        return vetor

    def encode(texto: str) -> SaidaTokens:
        spans: list[tuple[int, int]] = []
        bases: list[list[float]] = []
        for m in _RE_TOKEN.finditer(texto):
            spans.append((m.start(), m.end()))
            bases.append(_hash_vetor(m.group()))

        vetores: list[list[float]] = []
        for idx in range(len(bases)):
            atual = bases[idx]
            vetor: list[float] = []
            for i in range(dim):
                valor = (1 - 2 * peso_contexto) * atual[i]
                if idx > 0:
                    valor += peso_contexto * bases[idx - 1][i]
                if idx < len(bases) - 1:
                    valor += peso_contexto * bases[idx + 1][i]
                vetor.append(valor)
            vetores.append(vetor)
        return SaidaTokens(vetores=vetores, spans=spans)

    return encode


def encoder_tokens_transformers(
    nome: str = "intfloat/multilingual-e5-small",
) -> EncoderTokens:
    """Encoder real em nível de token (last_hidden_state + offset_mapping).
    Requer torch + transformers e baixa o modelo na 1ª vez. Import lazzy."""

    import torch  # noqa: PLC0415
    from transformers import AutoModel, AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(nome)
    modelo = AutoModel.from_pretrained(nome)
    modelo.eval()

    def encode(texto: str) -> SaidaTokens:
        enc = tokenizer(
            texto,
            return_offsets_mapping=True,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        offsets = enc.pop("offset_mapping")[0].tolist()
        with torch.no_grad():
            saida = modelo(**enc)
        ocultos = saida.last_hidden_state[0]
        vetores = ocultos.tolist()
        spans: list[tuple[int, int]] = []
        for par in offsets:
            spans.append((par[0], par[1]))
        return SaidaTokens(vetores=vetores, spans=spans)

    return encode
