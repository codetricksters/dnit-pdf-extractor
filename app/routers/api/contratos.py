"""Contratos: lista, detalhe e edição do cadastro (inclui Data Base e regiões)."""

import asyncio

from fastapi import APIRouter

from ...services import contratos_repo
from .erros import ErroApi
from .schemas import Contrato, ContratoPatch, ContratoResumo

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
