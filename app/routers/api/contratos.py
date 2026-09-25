"""Contratos: lista, detalhe e edição do cadastro (inclui Data Base e regiões)."""

import asyncio
from datetime import date

from fastapi import APIRouter, Query

from ...services import contratos_repo, medicoes_repo
from .erros import ErroApi
from .indices import MES
from .schemas import Contrato, ContratoPatch, ContratoResumo, ItemMedicao

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


def _medicoes(contrato_id: int, mes: str | None, no_calculo: bool | None, q: str | None) -> list[dict]:
    if contratos_repo.buscar_por_id(contrato_id) is None:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    mes_ref = date(int(mes[:4]), int(mes[5:7]), 1) if mes else None
    return medicoes_repo.listar_itens(contrato_id, mes=mes_ref, no_calculo=no_calculo, q=q)


@router.get("/{contrato_id}/medicoes", response_model=list[ItemMedicao])
async def medicoes(
    contrato_id: int,
    mes: str | None = Query(None, pattern=MES, description="AAAA-MM"),
    no_calculo: bool | None = Query(None, description="Só itens com produto (true) ou sem (false)"),
    q: str | None = Query(None, description="Trecho do código ou da descrição"),
):
    return await asyncio.to_thread(_medicoes, contrato_id, mes, no_calculo, q)
