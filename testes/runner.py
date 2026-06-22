"""Runner interativo dos pipelines de teste.

Loop principal (lê um caractere por iteração):
  1 -> comparar 2 documentos (cascata Q1; ação de cópia inclusa)
  2 -> extrair argumentos judiciais de uma sentença (Q2)
  0 -> sair

Rode a partir da raiz do projeto, usando o venv:  .venv/bin/python testes/runner.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

# permite importar os módulos da raiz do projeto
sys.path.append(str(Path(__file__).resolve().parent.parent))

from acoes import notificador_console, registrar_copia
from avaliacao import avaliar, carregar_gabarito_q2
from comparacao import ClasseSimilaridade, ResultadoComparacao, comparar
from embeddings import (
    encoder_tokens_dummy,  # noqa: F401  (fallback offline, sem atenção)
    encoder_tokens_transformers,
    processar_embeddings,
)
from extracao import aprovar, editar, extrair_argumentos, rejeitar
from modelagem import Documento, ExtracaoArgumentos
from pipeline import processar_documento

# Encoder ativo: Transformer real (atenção global -> late chunking de verdade).
# Para rodar offline sem torch/transformers, troque por encoder_tokens_dummy(dim=64).
MODELO = "intfloat/multilingual-e5-small"
ENCODER = encoder_tokens_transformers(MODELO)


def exibir_resultado(res: ResultadoComparacao) -> None:
    print(f"\n=== Resultado: {res.doc_a_id or '?'} × {res.doc_b_id or '?'} ===")
    print(f"mesmo caso: {'sim' if res.mesmo_caso else 'não'}")
    print(f"similaridade léxica (Jaccard): {res.sim_lexica:.4f}")
    if res.campos:
        print("\nsimilaridade por campo (cosseno):")
        print(f"  {'campo':18s} {'isolada':>9s} {'contextual':>11s}")
        for campo in res.campos:
            print(f"  {campo.tipo.value:18s} {campo.cos_isolada:9.4f} {campo.cos_contextual:11.4f}")
    if res.sim_tese is not None:
        print(f"\nsinal primário (tese isolada): {res.sim_tese:.4f}")
    if res.sim_documento is not None:
        print(f"documento inteiro (emb_geral): {res.sim_documento:.4f}")
    print(f"\n>>> CLASSE: {res.classe.value.upper()}")
    print(f"    motivo: {res.motivo}")


def carregar_documento(rotulo: str = "") -> Documento | None:
    """Carga: segmenta (segmentador LLM), mas NÃO calcula embeddings (custo adiado)."""
    sufixo = f" {rotulo}" if rotulo else ""
    caminho = input(f"Path do documento{sufixo}: ").strip()
    if not caminho:
        print("Path vazio.")
        return None
    if not Path(caminho).exists():
        print(f"Arquivo não encontrado: {caminho}")
        return None
    return processar_documento(caminho)


def embeddar(documento: Documento) -> Documento:
    """Black box `Embedder` para a cascata: aplica o encoder ativo ao documento."""
    return processar_embeddings(documento, ENCODER, MODELO)


def pipeline_comparar() -> None:
    doc_a = carregar_documento("1º")
    if doc_a is None:
        return
    doc_b = carregar_documento("2º")
    if doc_b is None:
        return

    # comparar() roda a cascata: caso -> portão léxico -> semântico, e só paga
    # o custo dos embeddings (via embeddar) se a etapa semântica for alcançada.
    resultado = comparar(doc_a, doc_b, embeddar)
    exibir_resultado(resultado)

    # Regra de negócio 1: ao detectar cópia, registrar vínculo + notificar.
    if resultado.classe == ClasseSimilaridade.COPIA:
        vinculo = registrar_copia(doc_a, doc_b, resultado.sim_lexica, notificador_console)
        print(
            f"\n[vínculo] {vinculo.doc_a_id} ↔ {vinculo.doc_b_id} "
            f"classe={vinculo.classe} representante={vinculo.representante_id} (mais novo)"
        )


def exibir_extracao(extracao: ExtracaoArgumentos) -> None:
    print(f"\n=== Argumentos: doc {extracao.documento_id} ===")
    print(
        f"modelo={extracao.modelo}  prompt={extracao.versao_prompt}  schema={extracao.versao_schema}"
    )
    print(f"extraídos={len(extracao.argumentos)}  rejeitados(alucinação)={extracao.n_rejeitados}")
    for arg in extracao.argumentos:
        corte = "..." if len(arg.trecho_citado) > 120 else ""
        print(
            f"\n  [{arg.posicao}] {arg.titulo}  ·  {arg.tipo.value}  ·  "
            f"conf={arg.confianca:.2f}  [{arg.status.value}]"
        )
        print(f"      resumo: {arg.resumo}")
        print(f'      trecho: "{arg.trecho_citado[:120]}{corte}"  (offsets {arg.inicio}-{arg.fim})')


def revisar(extracao: ExtracaoArgumentos) -> ExtracaoArgumentos:
    """Revisão humana (Q2.4): aprovar/rejeitar/editar cada argumento."""
    revisados: list = []
    for arg in extracao.argumentos:
        print(f"\n  [{arg.posicao}] {arg.titulo}  ·  {arg.tipo.value}")
        acao = input("    (a)provar / (r)ejeitar / (e)ditar título / Enter=pular: ").strip().lower()
        if acao == "a":
            revisados.append(aprovar(arg))
        elif acao == "r":
            revisados.append(rejeitar(arg))
        elif acao == "e":
            novo = input("    novo título: ").strip()
            revisados.append(editar(arg, titulo=novo))
        else:
            revisados.append(arg)
    return replace(extracao, argumentos=revisados)


def pipeline_extrair() -> None:
    doc = carregar_documento("(sentença)")
    if doc is None:
        return

    extracao = extrair_argumentos(doc)
    exibir_extracao(extracao)

    if input("\nRevisar argumentos? (s/N): ").strip().lower() == "s":
        extracao = revisar(extracao)
        exibir_extracao(extracao)

    if input("\nAvaliar contra o gabarito-q2? (s/N): ").strip().lower() == "s":
        gabarito = carregar_gabarito_q2(Path(__file__).resolve().parent / "gabarito-q2.md")
        esperados = gabarito.get(doc.id, [])
        if not esperados:
            print(f"Sem gabarito para o doc {doc.id}.")
        else:
            metr = avaliar(extracao, esperados, ENCODER)
            print(
                f"recall={metr['recall']:.2f}  precisao={metr['precisao']:.2f}  "
                f"concordância_tipo={metr['concordancia_tipo']:.2f}  "
                f"alucinação={metr['taxa_alucinacao']:.2f}"
            )


def main() -> None:
    print(f"(encoder ativo: {MODELO})")
    while True:
        print("\n=== Menu ===")
        print(" 1 - comparar 2 documentos")
        print(" 2 - extrair argumentos judiciais")
        print(" 0 - sair")
        escolha = input("> ").strip()
        if escolha == "0":
            print("Saindo.")
            break
        elif escolha == "1":
            pipeline_comparar()
        elif escolha == "2":
            pipeline_extrair()
        else:
            print("Opção inválida.")


if __name__ == "__main__":
    main()
