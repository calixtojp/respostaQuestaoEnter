"""Pipeline: costura carga -> segmentação -> (embeddings) sobre a pasta.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from modelagem import Documento
from segmentacao import Segmentador, carregar_documento, segmentar_estrutural  # noqa: F401
from segmentador_llm import segmentar_llm


def processar_documento(
    caminho: str | Path,
    segmentador: Segmentador = segmentar_llm
) -> Documento:
    doc = carregar_documento(caminho)
    return replace(doc, segmentos=segmentador(doc))


def processar_pasta(
    pasta: str | Path,
    segmentador: Segmentador = segmentar_llm
) -> list[Documento]:
    arquivos = sorted(Path(pasta).glob("*.md"))
    return [processar_documento(p, segmentador) for p in arquivos]


if __name__ == "__main__":
    docs = processar_pasta("documentos")
    print(f"{len(docs)} documentos processados\n")

    for d in docs:
        tipos = ", ".join(f"{s.tipo.value}" for s in d.segmentos)
        print(f"[{d.id:>2}] {d.tipo:<24} caso={d.caso_jur_id:<10} "
              f"{len(d.segmentos)} segmentos: {tipos}")
