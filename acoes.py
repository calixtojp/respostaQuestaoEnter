"""Ações de negócio ao classificar um par de documentos (regra de negócio 1).

Ao detectar uma CÓPIA, o sistema NÃO funde nem exclui nada: preserva os dois
documentos, registra um vínculo entre eles, elege o mais NOVO como representante
e notifica um responsável pelo caso/cliente (CT1.5). O documento não-representante
fica marcável como duplicado, evitando reprocessamento redundante.

O notificador é uma black box `Notificador` (intercambiável): aqui só há um stub
de console; em produção plugaria o sistema real de alertas.
"""

from __future__ import annotations

from typing import Callable

from modelagem import Alerta, Documento, VinculoDocumentos

# Black box: recebe um Alerta e o entrega a quem for responsável.
Notificador = Callable[[Alerta], None]


def notificador_console(alerta: Alerta) -> None:
    """Stub: imprime o alerta. Substituível pelo sistema real de notificação."""
    print(
        f"[ALERTA] caso={alerta.caso_id} cliente={alerta.cliente_cpf}: {alerta.mensagem} "
        f"(novo={alerta.doc_novo_id}, existente={alerta.doc_existente_id})"
    )


def escolher_representante(doc_a: Documento, doc_b: Documento) -> str:
    """Elege o documento mais NOVO como representante (data ISO ordena por string).
    Sem data, ou empate, desempata pelo maior id."""
    data_a = doc_a.data or ""
    data_b = doc_b.data or ""
    if data_a != data_b:
        return doc_a.id if data_a > data_b else doc_b.id
    return doc_a.id if doc_a.id >= doc_b.id else doc_b.id


def registrar_copia(
    doc_a: Documento,
    doc_b: Documento,
    score: float,
    notificar: Notificador = notificador_console,
) -> VinculoDocumentos:
    """Registra o vínculo de cópia (representante = mais novo) e dispara o alerta.
    Não funde nem exclui — apenas liga e avisa."""
    representante = escolher_representante(doc_a, doc_b)
    duplicado = doc_b.id if representante == doc_a.id else doc_a.id

    vinculo = VinculoDocumentos(
        doc_a_id=doc_a.id,
        doc_b_id=doc_b.id,
        classe="cópia",
        representante_id=representante,
        score=score,
    )

    alerta = Alerta(
        caso_id=doc_a.caso_jur_id or doc_b.caso_jur_id,
        cliente_cpf=doc_a.cliente_cpf or doc_b.cliente_cpf,
        doc_novo_id=duplicado,
        doc_existente_id=representante,
        mensagem=(
            f"Provável cópia detectada (score {score:.3f}). "
            f"Representante: {representante}. Revisar/deduplicar."
        ),
    )
    notificar(alerta)
    return vinculo
