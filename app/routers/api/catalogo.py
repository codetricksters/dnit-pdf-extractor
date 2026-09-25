"""Catálogo: produtos do usuário e a associação código de serviço → produto."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Path, Query, Response

from ...services import catalogo
from .erros import ErroApi
from .schemas import (
    CODIGO_SERVICO,
    Associacao,
    Codigo,
    CodigoAssociado,
    CodigosDoProduto,
    Produto,
    ProdutoNovo,
    ProdutoPatch,
)

router = APIRouter(tags=["catálogo"])

CodigoServico = Annotated[
    str, Path(pattern=CODIGO_SERVICO, description="Código de serviço do PDF")
]


def _erro_catalogo(e: catalogo.ErroCatalogo) -> ErroApi:
    status = 409 if isinstance(e, catalogo.ProdutoDuplicado) else 422
    return ErroApi(status, str(e))


@router.get("/produtos", response_model=list[Produto])
async def listar_produtos():
    return await asyncio.to_thread(catalogo.listar_produtos)


@router.post("/produtos", response_model=Produto, status_code=201)
async def criar_produto(novo: ProdutoNovo):
    try:
        produto_id = await asyncio.to_thread(
            catalogo.novo_produto, novo.descricao_export, novo.familia, novo.ordem
        )
    except catalogo.ErroCatalogo as e:
        raise _erro_catalogo(e) from e
    return await asyncio.to_thread(catalogo.buscar_produto, produto_id)


@router.patch("/produtos/{produto_id}", response_model=Produto)
async def atualizar_produto(produto_id: int, patch: ProdutoPatch):
    try:
        produto = await asyncio.to_thread(
            lambda: catalogo.atualizar_produto(
                produto_id, **patch.model_dump(exclude_unset=True)
            )
        )
    except catalogo.ErroCatalogo as e:
        raise _erro_catalogo(e) from e
    if produto is None:
        raise ErroApi(404, f"Produto {produto_id} não encontrado.")
    return produto


@router.delete("/produtos/{produto_id}", status_code=204)
async def excluir_produto(produto_id: int):
    if not await asyncio.to_thread(catalogo.excluir_produto, produto_id):
        raise ErroApi(404, f"Produto {produto_id} não encontrado.")
    return Response(status_code=204)


@router.put("/produtos/{produto_id}/codigos", response_model=Produto)
async def associar_codigos(produto_id: int, corpo: CodigosDoProduto):
    if not await asyncio.to_thread(catalogo.associar_codigos, produto_id, corpo.codigos):
        raise ErroApi(404, f"Produto {produto_id} não encontrado.")
    return await asyncio.to_thread(catalogo.buscar_produto, produto_id)


@router.get("/codigos", response_model=list[Codigo])
async def listar_codigos(
    q: str | None = Query(None, description="Trecho do código ou da descrição"),
    associado: bool | None = None,
    produto_id: int | None = Query(None, description="Só os códigos deste produto"),
    limite: int = Query(500, ge=1, le=5000),
):
    return await asyncio.to_thread(
        lambda: catalogo.buscar_codigos(q, associado, limite, produto_id=produto_id)
    )


@router.put("/codigos/{codigo}", response_model=CodigoAssociado)
async def associar_codigo(codigo: CodigoServico, associacao: Associacao):
    try:
        await asyncio.to_thread(catalogo.registrar_codigo, codigo, associacao.produto_id)
    except catalogo.ErroCatalogo as e:
        raise _erro_catalogo(e) from e
    return await asyncio.to_thread(catalogo.buscar_por_codigo, codigo)


@router.delete("/codigos/{codigo}", status_code=204)
async def desassociar_codigo(codigo: CodigoServico):
    if not await asyncio.to_thread(catalogo.desassociar_codigo, codigo):
        raise ErroApi(404, f"O código {codigo} não está associado a nenhum produto.")
    return Response(status_code=204)
