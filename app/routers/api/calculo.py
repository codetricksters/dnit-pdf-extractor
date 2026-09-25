"""Cálculo do reequilíbrio de um contrato, em JSON ou como planilha.

As duas rotas chamam ``reequilibrio_export.calcular`` — o mesmo cálculo — e só
diferem na saída. ``regiao_cap``/``regiao_emulsoes`` trocam a região de uma
família só nesta geração (simulação); o cadastro não muda.
"""

import asyncio
import re

from fastapi import APIRouter, Response

from ...services import contratos_repo, reequilibrio_export, template_repo
from ...services.delta_p import FAMILIA_CAP, FAMILIA_EMULSOES
from ...services.reequilibrio_export import Calculo, ExportacaoImpossivel
from ...services.xlsx_drawings import TemplateInvalido
from .erros import ErroApi
from .schemas import CalculoResposta

router = APIRouter(prefix="/contratos", tags=["cálculo"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _seguro(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", texto).strip("-")


def nome_do_arquivo(numero: str, simuladas: dict[str, str]) -> str:
    """``Reequilibrio_<numero>[_SIMULACAO_<FAMILIA>-<Regiao>…].xlsx``.

    A simulação fica no nome porque o template não tem célula de região: é o
    que distingue, na pasta de downloads, a planilha simulada da oficial.
    """
    nome = f"Reequilibrio_{_seguro(numero)}"
    if simuladas:
        nome += "_SIMULACAO_" + "_".join(
            f"{familia}-{_seguro(regiao)}" for familia, regiao in simuladas.items()
        )
    return nome + ".xlsx"


def cabecalho_avisos(avisos: list[str]) -> str:
    """Os avisos num valor de cabeçalho HTTP, que só aceita latin-1.

    Os avisos são escritos sem Δ, travessão ou reticências; o ``replace`` é a
    rede de segurança para que um aviso novo não derrube a resposta inteira.
    """
    return " | ".join(avisos).encode("latin-1", errors="replace").decode("latin-1")


def _calcular(contrato_id: int, regiao_cap: str | None, regiao_emulsoes: str | None) -> Calculo:
    contrato = contratos_repo.buscar_por_id(contrato_id)
    if contrato is None:
        raise ErroApi(404, f"Contrato {contrato_id} não encontrado.")
    override = {FAMILIA_CAP: regiao_cap, FAMILIA_EMULSOES: regiao_emulsoes}
    try:
        return reequilibrio_export.calcular(contrato, override)
    except ExportacaoImpossivel as e:
        raise ErroApi(422, e.mensagem, faltando=e.faltando) from e


@router.get("/{contrato_id}/calculo", response_model=CalculoResposta)
async def calculo(
    contrato_id: int, regiao_cap: str | None = None, regiao_emulsoes: str | None = None
):
    resultado = await asyncio.to_thread(_calcular, contrato_id, regiao_cap, regiao_emulsoes)
    resposta = reequilibrio_export.serializar(resultado)
    # O nome que a planilha terá: a tela mostra qual arquivo a simulação gera.
    resposta["arquivo"] = nome_do_arquivo(resultado.contrato["numero"], resultado.simuladas)
    return resposta


@router.get("/{contrato_id}/planilha")
async def planilha(
    contrato_id: int, regiao_cap: str | None = None, regiao_emulsoes: str | None = None
):
    resultado = await asyncio.to_thread(_calcular, contrato_id, regiao_cap, regiao_emulsoes)
    try:
        template = await asyncio.to_thread(template_repo.conteudo_ativo)
        gerado = await asyncio.to_thread(reequilibrio_export.gerar, resultado, template)
    except TemplateInvalido as e:
        raise ErroApi(422, str(e)) from e
    except ExportacaoImpossivel as e:
        raise ErroApi(422, e.mensagem, faltando=e.faltando) from e
    nome = nome_do_arquivo(resultado.contrato["numero"], resultado.simuladas)
    return Response(
        content=gerado.conteudo,
        media_type=XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="{nome}"',
            "X-Avisos": cabecalho_avisos(gerado.avisos),
        },
    )
