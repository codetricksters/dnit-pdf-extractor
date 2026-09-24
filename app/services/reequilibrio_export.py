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
from decimal import ROUND_DOWN, Decimal

import openpyxl

from . import contratos_repo, indices_repo, medicoes_repo, xlsx_drawings
from .catalogo import ROTULOS_FAMILIA
from .delta_p import FAMILIAS, IndiceIndisponivel, delta_p
from .delta_p import faltantes as delta_p_faltantes
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
    """The export cannot be produced, with a reason to show the user.

    ``faltando`` lists every missing piece (índices, data_base, a region), so
    the API can return them all at once instead of one per attempt.
    """

    def __init__(self, mensagem: str, faltando: list[str] | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.faltando = list(faltando or [])


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


@dataclass
class Calculo:
    """Everything the JSON and the spreadsheet share, computed once."""

    contrato: dict
    regioes: dict[str, str]
    simuladas: dict[str, str]
    grupos: list[Grupo]
    descartadas: int
    avisos: list[str] = field(default_factory=list)


CENTAVO = Decimal("0.01")


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


def _acrescentar(faltando: list[str], mensagens: list[str], token: str, texto: str) -> None:
    """Record one missing thing once, keeping the order of discovery.

    ``token`` is what the caller acts on to fix the problem — a code such as
    ``regiao_cap`` or, for a missing índice, the índice's own message; ``texto``
    is what gets shown, and always contains ``token`` literally, so joining
    every ``texto`` into one message is guaranteed to mention every ``token``.
    """
    if token in faltando:
        return
    faltando.append(token)
    mensagens.append(texto)


def regioes_efetivas(contrato: dict, override: dict | None = None) -> tuple[dict, dict]:
    """The regions this generation uses: the registered ones, replaced by
    *override* for this export only (a simulation). Returns ``(efetivas,
    simuladas)``; ``simuladas`` holds only families whose region changed.

    Every bad família in *override* is checked before raising, so the caller
    learns about all of them at once instead of one attempt at a time.
    """
    cadastro = dict(contrato.get("regioes") or {})
    efetivas = dict(cadastro)
    simuladas: dict[str, str] = {}
    faltando: list[str] = []
    mensagens: list[str] = []

    for familia, regiao in (override or {}).items():
        if not regiao:
            continue
        if familia not in FAMILIAS:
            texto = f"Família desconhecida: {familia!r}."
            _acrescentar(faltando, mensagens, texto, texto)
            continue
        campo = f"regiao_{familia.lower()}"
        grafia = indices_repo.normalizar_regiao(regiao)
        if grafia is None:
            texto = (
                f"{campo}: região {regiao!r} sem preços ANP do CAP 50/70; escolha "
                "uma das regiões importadas."
            )
            _acrescentar(faltando, mensagens, campo, texto)
            continue
        efetivas[familia] = grafia
        if grafia != cadastro.get(familia):
            simuladas[familia] = grafia

    if faltando:
        raise ExportacaoImpossivel(
            "Não é possível simular a região informada:\n- " + "\n- ".join(mensagens),
            faltando,
        )
    return efetivas, simuladas


def _deltas(
    contrato: dict, itens: list[dict], regioes: dict
) -> tuple[dict, list[str], list[str]]:
    """ΔP por (família, mês), com todo problema — não só o primeiro.

    Cada (família, mês) só é examinado uma vez: a região e a Data Base são as
    mesmas para todo item daquela chave, então o resultado seria idêntico.
    """
    fonte = FonteBanco()
    deltas: dict[tuple[str, date], Decimal] = {}
    faltando: list[str] = []
    mensagens: list[str] = []
    processados: set[tuple[str, date]] = set()

    for item in itens:
        chave = (item["familia"], item["mes_medicao"])
        if chave in processados:
            continue
        processados.add(chave)
        familia, mes_medicao = chave

        regiao = regioes.get(familia)
        if not regiao:
            codigo = f"regiao_{familia.lower()}"
            texto = f"{codigo}: escolha a região da ANP para a família {familia}."
            _acrescentar(faltando, mensagens, codigo, texto)
            continue

        problemas = delta_p_faltantes(
            familia, mes_medicao=mes_medicao, data_base=contrato["data_base"],
            regiao=regiao, fonte=fonte,
        )
        if problemas:
            for problema in problemas:
                _acrescentar(faltando, mensagens, problema, problema)
            continue

        deltas[chave] = delta_p(
            familia, mes_medicao=mes_medicao, data_base=contrato["data_base"],
            regiao=regiao, fonte=fonte,
        )

    return deltas, faltando, mensagens


def calcular_deltas(
    contrato: dict, itens: list[dict], regioes_override: dict | None = None
) -> tuple[dict, list[str]]:
    """ΔP for every (família, mês) the spreadsheet needs.

    A família whose region was never chosen, or a month with no published índice,
    blocks the export: a spreadsheet missing ΔP would look complete and be wrong.
    """
    regioes, _ = regioes_efetivas(contrato, regioes_override)
    deltas, faltando, _ = _deltas(contrato, itens, regioes)
    return deltas, faltando


def calcular(contrato: dict, regioes_override: dict | None = None) -> Calculo:
    """The whole calculation for a contract, shared by the JSON and the .xlsx."""
    if contrato.get("data_base") is None:
        raise ExportacaoImpossivel(
            "O contrato está sem Data Base, e sem ela não há como calcular o ΔP.",
            ["data_base"],
        )
    regioes, simuladas = regioes_efetivas(contrato, regioes_override)

    itens = medicoes_repo.itens_para_export(contrato["id"])
    if not itens:
        raise ExportacaoImpossivel(
            "Nenhum código de serviço deste contrato está associado a um produto. "
            "Associe os códigos no catálogo ou processe as medições."
        )

    deltas, faltando, mensagens = _deltas(contrato, itens, regioes)
    if faltando:
        raise ExportacaoImpossivel(
            "Faltam dados para calcular o ΔP:\n- " + "\n- ".join(mensagens), faltando
        )

    grupos, descartadas = montar_grupos(itens, deltas)

    avisos = []
    for familia, regiao in simuladas.items():
        cadastrada = (contrato.get("regioes") or {}).get(familia) or "sem região"
        avisos.append(
            f"Simulação: {familia} calculado com a região {regiao} (cadastro: {cadastrada})."
        )
    if descartadas:
        avisos.append(
            f"{descartadas} linha(s) repetida(s) foram ignoradas: a mesma medição "
            "consta de mais de um arquivo enviado."
        )
    faltam_cadastro = contratos_repo.campos_faltantes(contrato)
    if faltam_cadastro:
        avisos.append(
            "Campos do contrato ainda não cadastrados: " + ", ".join(faltam_cadastro)
        )

    return Calculo(contrato, regioes, simuladas, grupos, descartadas, avisos)


def gerar(calculo: Calculo, template: bytes) -> Resultado:
    return Resultado(
        conteudo=gerar_planilha(calculo.contrato, calculo.grupos, template),
        grupos=len(calculo.grupos),
        linhas=sum(len(g.linhas) for g in calculo.grupos),
        descartadas=calculo.descartadas,
        avisos=calculo.avisos,
    )


def serializar(calculo: Calculo) -> dict:
    """The calculation as data, with the spreadsheet's formulas evaluated.

    Same letters as row 16 of the template: ``b = TRUNC(a·fator, 2)``,
    ``c = a·d``, ``e = c − b``, ``f = e·(1 − lucro)``. TRUNC rounds toward zero,
    which is ``ROUND_DOWN`` in Decimal.
    """
    fator_lucro = 1 - Decimal(LUCRO)
    familias: list[dict] = []
    por_familia: dict[str, dict] = {}
    total = Decimal(0)
    for grupo in calculo.grupos:
        familia = por_familia.get(grupo.familia)
        if familia is None:
            familia = {
                "familia": grupo.familia,
                "rotulo": ROTULOS_FAMILIA.get(grupo.familia, grupo.familia),
                "subtotal": Decimal(0),
                "produtos": [],
            }
            por_familia[grupo.familia] = familia
            familias.append(familia)
        linhas = []
        subtotal = Decimal(0)
        for linha in grupo.linhas:
            b = (linha.valor_pi * linha.fator).quantize(CENTAVO, rounding=ROUND_DOWN)
            c = linha.valor_pi * linha.delta_p
            e = c - b
            f = e * fator_lucro
            linhas.append({"mes": linha.mes, "a": linha.valor_pi, "fator": linha.fator,
                           "b": b, "d": linha.delta_p, "c": c, "e": e, "f": f})
            subtotal += f
        familia["produtos"].append(
            {"descricao": grupo.descricao, "subtotal": subtotal, "linhas": linhas}
        )
        familia["subtotal"] += subtotal
        total += subtotal
    return {
        "contrato": {"id": calculo.contrato["id"], "numero": calculo.contrato["numero"]},
        "parametros": {
            "data_base": calculo.contrato["data_base"],
            "regioes": calculo.regioes,
            "simulacao": bool(calculo.simuladas),
            "lucro": Decimal(LUCRO),
        },
        "familias": familias,
        "total": total,
        "avisos": calculo.avisos,
    }


def exportar(
    numero_contrato: str, template: bytes, regioes_override: dict | None = None
) -> Resultado:
    """Assemble the spreadsheet for a contract from what is in the database."""
    contrato = contratos_repo.buscar(numero_contrato)
    if contrato is None:
        raise ExportacaoImpossivel(f"Contrato '{numero_contrato}' não cadastrado.")
    return gerar(calcular(contrato, regioes_override), template)
