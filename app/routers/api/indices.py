"""Índices globais: preços semanais da ANP e IGP-DI mensal.

Não dependem de contrato. Qualquer usuário grava ou corrige um valor
(``origem = 'manual'``) ou importa um arquivo inteiro, com prévia
(``simular``) e preservação das correções manuais (``sobrescrever_manuais``).
"""

import asyncio
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Response, UploadFile

from ...services import exportadores, importacao, indices_repo
from ...services.delta_p import ANP_PRODUTO_CAP
from ...services.importadores import ArquivoInvalido
from .erros import ErroApi
from .schemas import (
    Cobertura,
    IndiceEntrada,
    IndiceMensal,
    ResultadoImportacao,
    SemanaAnp,
    SemanaAnpEntrada,
)

router = APIRouter(prefix="/indices", tags=["índices"])

LIMITE_UPLOAD = 20 * 1024 * 1024
MES = r"^\d{4}-(0[1-9]|1[0-2])$"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

Mes = Annotated[str, Path(pattern=MES, description="Mês no formato AAAA-MM")]
MesFiltro = Annotated[str | None, Query(pattern=MES, description="AAAA-MM")]
Formato = Literal["xlsx", "csv"]


def _mes(texto: str) -> date:
    return date(int(texto[:4]), int(texto[5:7]), 1)


def _indice(linha: dict) -> dict:
    return {
        "mes": f"{linha['mes_ref']:%Y-%m}",
        "valor": linha["valor"],
        "origem": linha["origem"],
        "atualizado_em": linha["atualizado_em"],
    }


def _download(conteudo: bytes, nome: str, formato: Formato) -> Response:
    return Response(
        content=conteudo,
        media_type=XLSX if formato == "xlsx" else "text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


async def ler_upload(arquivo: UploadFile) -> bytes:
    """O conteúdo do upload, recusando vazio ou acima de ``LIMITE_UPLOAD``.

    Lê no máximo um byte além do limite: basta para saber que passou, sem
    carregar um arquivo gigante na memória.
    """
    conteudo = await arquivo.read(LIMITE_UPLOAD + 1)
    if len(conteudo) > LIMITE_UPLOAD:
        raise ErroApi(413, f"O arquivo passa do limite de {LIMITE_UPLOAD // (1024 * 1024)} MB.")
    if not conteudo:
        raise ErroApi(422, "O arquivo enviado está vazio.")
    return conteudo


async def _importar(funcao, arquivo: UploadFile, simular: bool, sobrescrever_manuais: bool):
    conteudo = await ler_upload(arquivo)
    nome = arquivo.filename or "arquivo"
    try:
        return await asyncio.to_thread(
            lambda: funcao(
                conteudo, nome, simular=simular, sobrescrever_manuais=sobrescrever_manuais
            )
        )
    except ArquivoInvalido as e:
        raise ErroApi(422, e.mensagem, erros=e.erros) from e
    except indices_repo.IndiceInvalido as e:
        raise ErroApi(422, str(e), erros=[str(e)]) from e


@router.get("/cobertura", response_model=Cobertura)
async def cobertura():
    return await asyncio.to_thread(indices_repo.cobertura)


# ── ANP ─────────────────────────────────────────────────────────────────────


@router.get("/anp/produtos", response_model=list[str])
async def produtos_anp():
    return await asyncio.to_thread(indices_repo.produtos_anp)


@router.get("/anp", response_model=list[SemanaAnp])
async def listar_anp(
    produto: str = ANP_PRODUTO_CAP,
    regiao: str | None = None,
    de: date | None = None,
    ate: date | None = None,
    limite: int = Query(500, ge=1, le=100000),
):
    return await asyncio.to_thread(
        lambda: indices_repo.listar_precos_anp(produto, regiao, limite, de=de, ate=ate)
    )


@router.put("/anp", response_model=SemanaAnp)
async def gravar_semana(semana: SemanaAnpEntrada):
    try:
        return await asyncio.to_thread(indices_repo.gravar_semana_manual, semana.model_dump())
    except indices_repo.IndiceInvalido as e:
        raise ErroApi(422, str(e)) from e


@router.delete("/anp/{preco_id}", status_code=204)
async def excluir_semana(preco_id: int):
    if not await asyncio.to_thread(indices_repo.excluir_preco_anp, preco_id):
        raise ErroApi(404, f"Semana {preco_id} não encontrada.")
    return Response(status_code=204)


@router.post("/anp/importar", response_model=ResultadoImportacao)
async def importar_anp(
    arquivo: UploadFile, simular: bool = False, sobrescrever_manuais: bool = False
):
    return await _importar(importacao.importar_anp, arquivo, simular, sobrescrever_manuais)


@router.get("/anp/exportar")
async def exportar_anp(
    produto: str = ANP_PRODUTO_CAP,
    regiao: str | None = None,
    de: date | None = None,
    ate: date | None = None,
    formato: Formato = "xlsx",
):
    linhas = await asyncio.to_thread(
        lambda: indices_repo.listar_precos_anp(produto, regiao, None, de=de, ate=ate)
    )
    gerar = exportadores.precos_xlsx if formato == "xlsx" else exportadores.precos_csv
    return _download(gerar(linhas), f"precos_anp.{formato}", formato)


# ── IGP-DI ──────────────────────────────────────────────────────────────────


@router.get("/igp-di", response_model=list[IndiceMensal])
async def listar_igp_di(de: MesFiltro = None, ate: MesFiltro = None):
    linhas = await asyncio.to_thread(
        lambda: indices_repo.listar_indices_mensais(
            limite=None,
            de=_mes(de) if de else None,
            ate=_mes(ate) if ate else None,
        )
    )
    return [_indice(l) for l in linhas]


@router.put("/igp-di/{mes}", response_model=IndiceMensal)
async def gravar_igp_di(mes: Mes, entrada: IndiceEntrada):
    try:
        linha = await asyncio.to_thread(indices_repo.gravar_indice_manual, _mes(mes), entrada.valor)
    except indices_repo.IndiceInvalido as e:
        raise ErroApi(422, str(e)) from e
    return _indice(linha)


@router.delete("/igp-di/{mes}", status_code=204)
async def excluir_igp_di(mes: Mes):
    if not await asyncio.to_thread(indices_repo.excluir_indice_mensal, _mes(mes)):
        raise ErroApi(404, f"Não há IGP-DI cadastrado para {mes}.")
    return Response(status_code=204)


async def _todos_os_meses() -> list[dict]:
    return await asyncio.to_thread(lambda: indices_repo.listar_indices_mensais(limite=None))


@router.get("/igp-di/template")
async def template_igp_di():
    """O template de importação, já preenchido com o que está no banco."""
    conteudo = exportadores.indices_xlsx(await _todos_os_meses())
    return _download(conteudo, "igp_di_template.xlsx", "xlsx")


@router.post("/igp-di/importar", response_model=ResultadoImportacao)
async def importar_igp_di(
    arquivo: UploadFile, simular: bool = False, sobrescrever_manuais: bool = False
):
    return await _importar(importacao.importar_igp_di, arquivo, simular, sobrescrever_manuais)


@router.get("/igp-di/exportar")
async def exportar_igp_di(formato: Formato = "xlsx"):
    linhas = await _todos_os_meses()
    gerar = exportadores.indices_xlsx if formato == "xlsx" else exportadores.indices_csv
    return _download(gerar(linhas), f"igp_di.{formato}", formato)
