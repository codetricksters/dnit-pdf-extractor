"""The dashboard's data and rendering.

``compute_ref_columns`` had no coverage before, and it is the arithmetic the user
reads on screen — including the truncation of F, which is a truncation and not a
rounding.
"""

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.dashboard import views
from app.dashboard.data_loader import (
    DEFAULT_LUCRO,
    _truncate,
    compute_ref_columns,
    load_reequilibrio_data,
)
from app.services import catalogo, contratos_repo, indices_repo, medicoes_repo
from app.services.delta_p import ANP_PRODUTO_CAP, FAMILIA_CAP

HEADER = {
    "Contrato": "15 00716/2022 - HWN ENGENHARIA LTDA Índices I0 I1 K",
    "Data Base": "01/01/2022",
    "Período Líquido": "01/02/2023 - 28/02/2023",
    "Número do Processo": "50615.000404/2022-67",
}


def _tabela() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Período": "02/2023",
                "Descrição": "AQUISIÇÃO DE CAP 50/70",
                "Valor a PI": 208133.17,
                "Fator de Reajuste": -0.1839,
                "Reajustamento da Medição (R)": _truncate(-0.1839 * 208133.17, 2),
                "∆P": -0.1828,
                "Reajustamento Total Base Produtor": 0.0,
                "REF Bruto com Lucro": 0.0,
                "REF sem Lucro": 0.0,
            }
        ]
    )


def test_truncate_corta_e_nao_arredonda():
    # 0.567 would round up to 0.57; the PDF and the spreadsheet's TRUNC cut it.
    assert _truncate(0.567, 2) == 0.56
    assert _truncate(-0.567, 2) == -0.56


def test_compute_ref_columns_reproduz_a_cadeia_do_calculo():
    df = compute_ref_columns(_tabela())
    linha = df.iloc[0]

    total_produtor = 208133.17 * -0.1828
    reajustamento = _truncate(-0.1839 * 208133.17, 2)
    assert linha["Reajustamento Total Base Produtor"] == pytest.approx(total_produtor)
    assert linha["REF Bruto com Lucro"] == pytest.approx(total_produtor - reajustamento)
    assert linha["REF sem Lucro"] == pytest.approx(
        (total_produtor - reajustamento) * (1 - DEFAULT_LUCRO)
    )


def test_compute_ref_columns_aceita_outro_lucro():
    df = compute_ref_columns(_tabela(), lucro=0.0)
    linha = df.iloc[0]
    # With no lucro deducted the two REF columns coincide.
    assert linha["REF sem Lucro"] == pytest.approx(linha["REF Bruto com Lucro"])


def test_compute_ref_columns_com_tabela_vazia():
    vazia = _tabela().iloc[0:0]
    assert compute_ref_columns(vazia).empty


async def test_load_reequilibrio_data_sem_contrato():
    tabelas, pendencias = load_reequilibrio_data("99 99999/9999")
    assert tabelas == {}
    assert "não cadastrado" in pendencias[0]


async def _semear() -> None:
    contrato_id = contratos_repo.registrar_do_pdf(HEADER)
    produto_id = catalogo.criar_produto("AQUISIÇÃO DE CAP 50/70", FAMILIA_CAP)
    catalogo.registrar_codigo("8300980", produto_id)
    medicoes_repo.gravar_itens(
        contrato_id,
        [
            {
                "Serviço": "8300980",
                "Descrição": "AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70",
                "Valor a PI Líquido": 208133.17,
                "Fator": -0.1839,
                "Período Líquido": "01/02/2023 - 28/02/2023",
                "Source_File": "1ª MP.pdf",
            }
        ],
    )
    contratos_repo.definir_regiao("15 00716/2022", FAMILIA_CAP, "Nordeste")


async def test_falta_de_indice_aparece_como_pendencia_e_nao_como_erro():
    """The screen shows what it can and says what is missing.

    The export refuses instead — a spreadsheet without ΔP would look finished.
    """
    await _semear()
    tabelas, pendencias = load_reequilibrio_data("15 00716/2022")
    assert tabelas == {}
    assert pendencias


async def test_tabela_por_produto_com_delta_p_do_banco():
    await _semear()
    indices_repo.gravar_precos_anp(
        [
            {
                "produto": ANP_PRODUTO_CAP,
                "vigencia_inicio": date(2021, 12, 12),
                "vigencia_fim": date(2021, 12, 18),
                "regiao": "Nordeste",
                "preco": Decimal("3.0000"),
            },
            {
                "produto": ANP_PRODUTO_CAP,
                "vigencia_inicio": date(2023, 1, 9),
                "vigencia_fim": date(2023, 1, 15),
                "regiao": "Nordeste",
                "preco": Decimal("2.7000"),
            },
        ]
    )

    tabelas, pendencias = load_reequilibrio_data("15 00716/2022")

    assert pendencias == []
    assert list(tabelas) == ["AQUISIÇÃO DE CAP 50/70"]
    linha = tabelas["AQUISIÇÃO DE CAP 50/70"].iloc[0]
    assert linha["Período"] == "02/2023"
    # ΔP = 2,70 / 3,00 - 1, computed from the índices, not typed by the user.
    assert linha["∆P"] == pytest.approx(-0.1)
    assert linha["Valor a PI"] == pytest.approx(208133.17)


async def test_telas_renderizam_sem_dados():
    """Every screen has to render on a fresh database, not raise."""
    assert views.tela_reequilibrio(None, {}, []) is not None
    assert views.tela_cadastro(None) is not None
    assert views.tela_pendencias([], []) is not None
    assert views.tela_indices(indices_repo.cobertura()) is not None
    assert views.tela_administracao([], []) is not None


async def test_tela_de_pendencias_oferece_os_produtos_existentes():
    """Confirming a code means pointing it at a product — that is how several
    codes end up under one export description."""
    produto_id = catalogo.criar_produto("AQUISIÇÃO DE CAP 50/70", FAMILIA_CAP)
    catalogo.registrar_pendencia("99999", "AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70")

    tela = views.tela_pendencias(catalogo.listar_pendencias(), catalogo.listar_produtos())

    texto = str(tela)
    assert "99999" in texto
    assert str(produto_id) in texto


async def test_tela_de_reequilibrio_libera_o_download_sem_pendencias():
    await _semear()
    contrato = contratos_repo.buscar("15 00716/2022")

    com_pendencia = str(views.tela_reequilibrio(contrato, {}, ["falta índice"]))
    assert "/reequilibrio/planilha" not in com_pendencia

    tabelas = {"AQUISIÇÃO DE CAP 50/70": _tabela()}
    liberada = str(views.tela_reequilibrio(contrato, tabelas, []))
    assert "/reequilibrio/planilha?contrato=15 00716/2022" in liberada


async def test_rota_da_planilha_recusa_com_o_motivo(client):
    from app.services import template_repo

    template_repo.garantir_semente()
    r = await client.get("/reequilibrio/planilha", params={"contrato": "99 99999/9999"})
    assert r.status_code == 422
    assert "não cadastrado" in r.json()["detail"]


async def test_rota_da_planilha_entrega_o_arquivo(client):
    await _semear()
    indices_repo.gravar_precos_anp(
        [
            {
                "produto": ANP_PRODUTO_CAP,
                "vigencia_inicio": date(2021, 12, 12),
                "vigencia_fim": date(2021, 12, 18),
                "regiao": "Nordeste",
                "preco": Decimal("3.0000"),
            },
            {
                "produto": ANP_PRODUTO_CAP,
                "vigencia_inicio": date(2023, 1, 9),
                "vigencia_fim": date(2023, 1, 15),
                "regiao": "Nordeste",
                "preco": Decimal("2.7000"),
            },
        ]
    )
    from app.services import template_repo

    template_repo.garantir_semente()

    r = await client.get("/reequilibrio/planilha", params={"contrato": "15 00716/2022"})

    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # é um .xlsx
    assert "Reequilibrio" in r.headers["content-disposition"]
    # The contract is still missing registration fields, and the download says so
    # instead of quietly producing a header with blanks.
    assert "Campos do contrato" in r.headers["x-avisos"]
