"""Generating the Reequilíbrio spreadsheet from the active template.

Two requirements shape this module.

**The calculation has to travel as live formulas.** F, H, I and J are written as
Excel formulas, not results, so the user can audit every number by clicking the
cell. ΔP (column G) is the single literal: it comes from ``delta_p.py``, which
computes it from the índices in the database.

**The memória de cálculo has to survive.** openpyxl drops text boxes, so the
equation is lifted from the template and re-injected after openpyxl writes —
see ``xlsx_drawings``.

Layout and formatting come from the template, never from here: the export copies
the formatting of the model rows (17–20) for every row it writes, which lets the
user restyle the spreadsheet in Excel without a code change.
"""

import io
from copy import copy
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import openpyxl

from . import contratos_repo, medicoes_repo, xlsx_drawings
from .delta_p import IndiceIndisponivel, delta_p
from .indices_repo import FonteBanco
from .reequilibrio_layout import (
    ABA,
    CAMPOS_CABECALHO,
    COL_DELTA_P,
    COL_DESCRICAO,
    COL_FATOR,
    COL_FIM,
    COL_INICIO,
    COL_MES,
    COL_REAJUSTAMENTO,
    COL_REF_BRUTO,
    COL_REF_SEM_LUCRO,
    COL_TOTAL_PRODUTOR,
    COL_VALOR_PI,
    LINHA_CABECALHO_INICIO,
    LINHA_DADOS,
    LINHA_GRUPO,
    LINHA_SUBTOTAL,
    LINHA_TOTAL,
    LINHAS_MODELO,
    LUCRO,
    PRIMEIRA_LINHA,
    ROTULO_SUBTOTAL,
    ROTULO_TOTAL,
)

class ExportacaoImpossivel(Exception):
    """The export cannot be produced, with a reason to show the user."""


@dataclass
class Linha:
    """One measurement month of one product."""

    mes: date
    valor_pi: Decimal
    fator: Decimal
    delta_p: Decimal


@dataclass
class Grupo:
    """One product: the block the spreadsheet subtotals."""

    descricao: str
    familia: str
    linhas: list[Linha] = field(default_factory=list)


@dataclass
class Resultado:
    conteudo: bytes
    grupos: int
    linhas: int
    descartadas: int
    avisos: list[str] = field(default_factory=list)


def montar_grupos(itens: list[dict], deltas: dict[tuple[str, date], Decimal]) -> tuple[list[Grupo], int]:
    """Turn measurement items into the spreadsheet's product blocks.

    Items arrive ordered família → produto → mês from ``itens_para_export``.

    Two items of the same product and month happen when several service codes
    map onto one product: their ``Valor a PI`` is summed, as one spreadsheet row
    per month is what the reference layout has. They are only summed when the
    ``Fator`` matches — a differing fator means a different reajustamento, and
    blending them would corrupt column F. Those keep separate rows.

    The same code, month and product arriving from two ``source_file`` values is
    the same measurement uploaded under two names. Summing it would silently
    double the total, so only the most recent row is kept and the rest are
    counted as discarded for the caller to report.
    """
    por_codigo: dict[tuple[str, str, date], dict] = {}
    descartadas = 0
    for item in itens:
        chave = (item["descricao_export"], item["codigo_servico"], item["mes_medicao"])
        if chave in por_codigo:
            descartadas += 1
            continue
        por_codigo[chave] = item

    grupos: list[Grupo] = []
    atual: Grupo | None = None
    acumulado: dict[tuple[date, Decimal], Decimal] = {}

    def fechar() -> None:
        if atual is None:
            return
        for (mes, fator), valor in sorted(acumulado.items()):
            atual.linhas.append(
                Linha(
                    mes=mes,
                    valor_pi=valor,
                    fator=fator,
                    delta_p=deltas[(atual.familia, mes)],
                )
            )
        if atual.linhas:
            grupos.append(atual)

    for item in por_codigo.values():
        if atual is None or item["descricao_export"] != atual.descricao:
            fechar()
            atual = Grupo(descricao=item["descricao_export"], familia=item["familia"])
            acumulado = {}
        chave = (item["mes_medicao"], item["fator"])
        acumulado[chave] = acumulado.get(chave, Decimal(0)) + item["valor_pi"]
    fechar()

    return grupos, descartadas


def gerar_planilha(contrato: dict, grupos: list[Grupo], template: bytes) -> bytes:
    """Write the contract header and the calculation table into *template*."""
    formas = xlsx_drawings.extrair_formas(template, ABA)

    wb = openpyxl.load_workbook(io.BytesIO(template))
    if ABA not in wb.sheetnames:
        raise ExportacaoImpossivel(
            f"O template não contém a aba '{ABA}'. Envie um template válido."
        )
    ws = wb[ABA]

    estilos = _capturar_modelos(ws)
    ws.delete_rows(PRIMEIRA_LINHA, max(ws.max_row - PRIMEIRA_LINHA + 1, 1))
    for faixa in [m for m in ws.merged_cells.ranges if m.min_row >= PRIMEIRA_LINHA]:
        ws.merged_cells.ranges.remove(faixa)

    _escrever_cabecalho(ws, contrato)
    _escrever_tabela(ws, grupos, estilos)

    saida = io.BytesIO()
    wb.save(saida)
    return xlsx_drawings.injetar_formas(saida.getvalue(), ABA, formas)


def _capturar_modelos(ws) -> dict[int, dict]:
    """Formatting of the model rows, read before they are deleted."""
    return {
        linha: {
            "estilos": [
                copy(ws.cell(linha, col)._style) for col in range(COL_INICIO, COL_FIM + 1)
            ],
            "altura": ws.row_dimensions[linha].height,
        }
        for linha in LINHAS_MODELO
    }


def _aplicar(ws, linha: int, modelo: dict) -> None:
    for deslocamento, estilo in enumerate(modelo["estilos"]):
        ws.cell(linha, COL_INICIO + deslocamento)._style = copy(estilo)
    if modelo["altura"]:
        ws.row_dimensions[linha].height = modelo["altura"]


def _numero(valor: Decimal | float | None) -> float | None:
    """Coerce to float before writing.

    An xlsx number cell is a float64, so Decimal's job — carrying the value
    through the database and the ΔP arithmetic without drift — ends here. Making
    the conversion explicit keeps the cell type unambiguous; openpyxl has no
    Decimal number type and writes both through the same 17-significant-digit
    path (``-0.0758`` becomes ``-0.07580000000000001`` in the XML, which Excel
    reads back as the same float64).
    """
    return None if valor is None else float(valor)


def _escrever_cabecalho(ws, contrato: dict) -> None:
    for deslocamento, (_rotulo, campo) in enumerate(CAMPOS_CABECALHO):
        if campo is None:  # Período: a template formula over the months written
            continue
        valor = contrato.get(campo)
        if isinstance(valor, Decimal):
            valor = _numero(valor)
        ws.cell(LINHA_CABECALHO_INICIO + deslocamento, COL_DESCRICAO).value = valor


def _escrever_tabela(ws, grupos: list[Grupo], estilos: dict[int, dict]) -> None:
    linha = PRIMEIRA_LINHA
    celulas_subtotal: list[str] = []

    for grupo in grupos:
        linha_grupo = linha
        _aplicar(ws, linha, estilos[LINHA_GRUPO])
        ws.cell(linha, COL_INICIO).value = grupo.descricao
        ws.merge_cells(start_row=linha, start_column=2, end_row=linha, end_column=10)
        linha += 1

        primeira_dados = linha
        for item in grupo.linhas:
            _aplicar(ws, linha, estilos[LINHA_DADOS])
            ws.cell(linha, COL_MES).value = item.mes
            # The description points at the group header, so renaming the
            # product in the spreadsheet updates every row of the block.
            ws.cell(linha, COL_DESCRICAO).value = f"=B{linha_grupo}"
            ws.cell(linha, COL_VALOR_PI).value = _numero(item.valor_pi)
            ws.cell(linha, COL_FATOR).value = _numero(item.fator)
            ws.cell(linha, COL_REAJUSTAMENTO).value = f"=TRUNC(E{linha}*D{linha},2)"
            ws.cell(linha, COL_DELTA_P).value = _numero(item.delta_p)
            ws.cell(linha, COL_TOTAL_PRODUTOR).value = f"=D{linha}*G{linha}"
            ws.cell(linha, COL_REF_BRUTO).value = f"=H{linha}-F{linha}"
            ws.cell(linha, COL_REF_SEM_LUCRO).value = f"=I{linha}*(1-{LUCRO})"
            linha += 1

        _aplicar(ws, linha, estilos[LINHA_SUBTOTAL])
        ws.cell(linha, COL_TOTAL_PRODUTOR).value = ROTULO_SUBTOTAL
        ws.merge_cells(start_row=linha, start_column=8, end_row=linha, end_column=9)
        ws.cell(linha, COL_REF_SEM_LUCRO).value = (
            f"=SUM(J{primeira_dados}:J{linha - 1})"
        )
        celulas_subtotal.append(f"J{linha}")
        linha += 1

    _aplicar(ws, linha, estilos[LINHA_TOTAL])
    ws.cell(linha, COL_TOTAL_PRODUTOR).value = ROTULO_TOTAL
    ws.merge_cells(start_row=linha, start_column=8, end_row=linha, end_column=9)
    ws.cell(linha, COL_REF_SEM_LUCRO).value = (
        "=" + "+".join(celulas_subtotal) if celulas_subtotal else 0
    )


def calcular_deltas(contrato: dict, itens: list[dict]) -> tuple[dict, list[str]]:
    """ΔP for every (família, mês) the spreadsheet needs.

    A família whose region was never chosen, or a month with no published índice,
    blocks the export: a spreadsheet missing ΔP would look complete and be wrong.
    """
    fonte = FonteBanco()
    regioes = contrato.get("regioes") or {}
    deltas: dict[tuple[str, date], Decimal] = {}
    faltando: list[str] = []

    for item in itens:
        chave = (item["familia"], item["mes_medicao"])
        if chave in deltas:
            continue
        regiao = regioes.get(item["familia"])
        if not regiao:
            aviso = f"Escolha a região da ANP para a família {item['familia']}."
            if aviso not in faltando:
                faltando.append(aviso)
            continue
        try:
            deltas[chave] = delta_p(
                item["familia"],
                mes_medicao=item["mes_medicao"],
                data_base=contrato["data_base"],
                regiao=regiao,
                fonte=fonte,
            )
        except IndiceIndisponivel as e:
            faltando.append(str(e))

    return deltas, faltando


def exportar(numero_contrato: str, template: bytes) -> Resultado:
    """Assemble the spreadsheet for a contract from what is in the database."""
    contrato = contratos_repo.buscar(numero_contrato)
    if contrato is None:
        raise ExportacaoImpossivel(f"Contrato '{numero_contrato}' não cadastrado.")
    if contrato.get("data_base") is None:
        raise ExportacaoImpossivel(
            "O contrato está sem Data Base, e sem ela não há como calcular o ΔP."
        )

    itens = medicoes_repo.itens_para_export(contrato["id"])
    if not itens:
        raise ExportacaoImpossivel(
            "Nenhum item confirmado para este contrato. Confirme os códigos de "
            "serviço pendentes ou processe as medições."
        )

    deltas, faltando = calcular_deltas(contrato, itens)
    if faltando:
        raise ExportacaoImpossivel(
            "Faltam dados para calcular o ΔP:\n- " + "\n- ".join(faltando)
        )

    grupos, descartadas = montar_grupos(itens, deltas)
    conteudo = gerar_planilha(contrato, grupos, template)

    avisos = []
    if descartadas:
        avisos.append(
            f"{descartadas} linha(s) repetida(s) foram ignoradas: a mesma medição "
            "consta de mais de um arquivo enviado."
        )
    faltam_cadastro = contratos_repo.campos_faltantes(contrato)
    if faltam_cadastro:
        avisos.append(
            "Campos do contrato ainda não cadastrados: "
            + ", ".join(faltam_cadastro)
        )

    return Resultado(
        conteudo=conteudo,
        grupos=len(grupos),
        linhas=sum(len(g.linhas) for g in grupos),
        descartadas=descartadas,
        avisos=avisos,
    )
