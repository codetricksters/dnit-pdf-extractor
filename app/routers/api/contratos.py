"""Contratos: lista, detalhe e edição do cadastro (inclui Data Base e regiões)."""

import asyncio
from datetime import date

from fastapi import APIRouter, Query, Response

from ...services import contratos_repo, medicoes_repo
from .erros import MES, ErroApi
from .schemas import (
    Contrato,
    ContratoPatch,
    ContratoResumo,
    ExclusaoEmMassa,
    ItemMedicao,
    MedicaoNova,
    MedicaoPatch,
    MedicoesExcluidas,
    RegiaoAplicada,
    RegiaoEmLote,
)

router = APIRouter(prefix="/contratos", tags=["contratos"])


def _detalhe(contrato_id: int) -> dict:
    contrato = contratos_repo.buscar_por_id(contrato_id)
    if contrato is None:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    contrato["faltantes"] = contratos_repo.campos_faltantes(contrato)
    return contrato


@router.get("", response_model=list[ContratoResumo])
async def listar(numero: str | None = None):
    return await asyncio.to_thread(contratos_repo.listar, numero)


@router.get("/{contrato_id}", response_model=Contrato)
async def detalhar(contrato_id: int):
    return await asyncio.to_thread(_detalhe, contrato_id)


@router.patch("/{contrato_id}", response_model=Contrato)
async def atualizar(contrato_id: int, patch: ContratoPatch):
    dados = patch.model_dump(exclude_unset=True)
    regioes = dados.pop("regioes", None)
    try:
        existe = await asyncio.to_thread(
            contratos_repo.atualizar, contrato_id, dados, regioes
        )
    except contratos_repo.CadastroInvalido as e:
        raise ErroApi(422, str(e)) from e
    if not existe:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    return await asyncio.to_thread(_detalhe, contrato_id)


def _existe(contrato_id: int) -> None:
    if contratos_repo.buscar_por_id(contrato_id) is None:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")


def _medicoes(contrato_id: int, mes: str | None, no_calculo: bool | None, q: str | None,
              arquivo: str | None) -> list[dict]:
    _existe(contrato_id)
    mes_ref = date(int(mes[:4]), int(mes[5:7]), 1) if mes else None
    return medicoes_repo.listar_itens(
        contrato_id, mes=mes_ref, no_calculo=no_calculo, q=q, arquivo=arquivo
    )


@router.get("/{contrato_id}/medicoes", response_model=list[ItemMedicao])
async def medicoes(
    contrato_id: int,
    mes: str | None = Query(None, pattern=MES, description="AAAA-MM"),
    no_calculo: bool | None = Query(None, description="Só itens com produto (true) ou sem (false)"),
    q: str | None = Query(None, description="Trecho do código ou da descrição"),
    arquivo: str | None = Query(None, description="Arquivo de origem; 'manual' para os incluídos à mão"),
):
    return await asyncio.to_thread(_medicoes, contrato_id, mes, no_calculo, q, arquivo)


def _item(contrato_id: int, item_id: int) -> dict:
    item = medicoes_repo.buscar_item(contrato_id, item_id)
    if item is None:
        raise ErroApi(404, f"Registro {item_id} não encontrado neste contrato.")
    return item


def _incluir(contrato_id: int, dados: dict) -> dict:
    try:
        item_id = medicoes_repo.incluir_item(contrato_id, dados)
    except medicoes_repo.MedicaoInvalida as e:
        raise ErroApi(422, str(e)) from e
    if item_id is None:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    return _item(contrato_id, item_id)


def _alterar(contrato_id: int, item_id: int, dados: dict) -> dict:
    try:
        existe = medicoes_repo.atualizar_item(contrato_id, item_id, dados)
    except medicoes_repo.MedicaoInvalida as e:
        raise ErroApi(422, str(e)) from e
    if not existe:
        raise ErroApi(404, f"Registro {item_id} não encontrado neste contrato.")
    return _item(contrato_id, item_id)


def _excluir(contrato_id: int, item_id: int) -> None:
    if not medicoes_repo.excluir_item(contrato_id, item_id):
        raise ErroApi(404, f"Registro {item_id} não encontrado neste contrato.")


def _aplicar_regiao(contrato_id: int, dados: dict, simular: bool) -> dict:
    _existe(contrato_id)
    try:
        return {"alterados": medicoes_repo.aplicar_regiao(contrato_id, **dados, simular=simular)}
    except medicoes_repo.MedicaoInvalida as e:
        raise ErroApi(422, str(e)) from e


@router.post("/{contrato_id}/medicoes/regiao", response_model=RegiaoAplicada)
async def aplicar_regiao(
    contrato_id: int,
    corpo: RegiaoEmLote,
    simular: bool = Query(False, description="Só conta os registros, sem gravar"),
):
    return await asyncio.to_thread(_aplicar_regiao, contrato_id, corpo.model_dump(), simular)


def _excluir_varios(contrato_id: int, ids: list[int]) -> dict:
    _existe(contrato_id)
    return {"excluidos": medicoes_repo.excluir_itens(contrato_id, ids)}


# POST, não DELETE: proxies e clientes costumam descartar o corpo de um DELETE.
@router.post("/{contrato_id}/medicoes/excluir", response_model=MedicoesExcluidas)
async def excluir_medicoes(contrato_id: int, corpo: ExclusaoEmMassa):
    return await asyncio.to_thread(_excluir_varios, contrato_id, corpo.ids)


@router.post("/{contrato_id}/medicoes", response_model=ItemMedicao, status_code=201)
async def incluir_medicao(contrato_id: int, novo: MedicaoNova):
    return await asyncio.to_thread(_incluir, contrato_id, novo.model_dump())


@router.patch("/{contrato_id}/medicoes/{item_id}", response_model=ItemMedicao)
async def alterar_medicao(contrato_id: int, item_id: int, patch: MedicaoPatch):
    return await asyncio.to_thread(
        _alterar, contrato_id, item_id, patch.model_dump(exclude_unset=True)
    )


@router.delete("/{contrato_id}/medicoes/{item_id}", status_code=204)
async def excluir_medicao(contrato_id: int, item_id: int):
    await asyncio.to_thread(_excluir, contrato_id, item_id)
    return Response(status_code=204)
