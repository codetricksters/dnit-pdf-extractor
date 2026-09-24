"""Exportação dos índices: uma linha por semana e região, valores exatos."""

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal

import openpyxl

from app.services import exportadores, importadores

ATUALIZADO = datetime(2026, 9, 24, 13, 5, tzinfo=timezone.utc)
PRECOS = [
    {"id": 1, "produto": "CAP", "regiao": "Nordeste", "vigencia_inicio": date(2021, 12, 13),
     "vigencia_fim": date(2021, 12, 19), "preco": Decimal("4.02073"), "origem": "seed",
     "atualizado_em": ATUALIZADO},
    {"id": 2, "produto": "CAP", "regiao": "Centro-Oeste", "vigencia_inicio": date(2021, 12, 13),
     "vigencia_fim": date(2021, 12, 19), "preco": None, "origem": "manual",
     "atualizado_em": ATUALIZADO},
]
INDICES = [
    {"id": 1, "indice": "IGP - DI", "base_label": "ago/1994 = 100", "mes_ref": date(2022, 1, 1),
     "valor": Decimal("1110.398"), "origem": "seed", "atualizado_em": ATUALIZADO},
]


def _csv(conteudo: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(conteudo.decode("utf-8"))))


def test_precos_csv():
    linhas = _csv(exportadores.precos_csv(PRECOS))
    assert list(linhas[0]) == list(exportadores.COLUNAS_ANP)
    assert linhas[0]["preco"] == "4.02073"
    assert linhas[0]["vigencia_inicio"] == "2021-12-13"
    assert linhas[0]["atualizado_em"] == "2026-09-24T13:05:00+00:00"
    assert linhas[1]["preco"] == ""


def test_precos_xlsx():
    ws = openpyxl.load_workbook(io.BytesIO(exportadores.precos_xlsx(PRECOS))).active
    assert [c.value for c in ws[1]] == list(exportadores.COLUNAS_ANP)
    assert ws["E2"].value == 4.02073
    assert ws["B2"].value.date() == date(2021, 12, 13)
    assert ws["E3"].value is None
    assert ws["G2"].value == "2026-09-24T13:05:00+00:00"


def test_precos_xlsx_nao_deixa_produto_virar_formula():
    """Um ``produto`` (dado do usuário, via cadastro de código) começando com
    ``=``, ``+``, ``-`` ou ``@`` não pode ser interpretado como fórmula pelo
    Excel na planilha exportada."""
    malicioso = [{**PRECOS[0], "produto": "=HYPERLINK(1)"}]
    ws = openpyxl.load_workbook(io.BytesIO(exportadores.precos_xlsx(malicioso))).active
    celula = ws["A2"]
    assert celula.value == "=HYPERLINK(1)"
    assert celula.data_type == "s"


def test_indices_csv():
    (linha,) = _csv(exportadores.indices_csv(INDICES))
    assert linha == {"mes": "2022-01", "valor": "1110.398", "origem": "seed",
                     "atualizado_em": "2026-09-24T13:05:00+00:00"}


def test_indices_xlsx_e_o_template_reimportavel():
    leitura = importadores.ler_igp_di(exportadores.indices_xlsx(INDICES))
    assert [(r["mes_ref"], r["valor"]) for r in leitura.registros] == [
        (date(2022, 1, 1), Decimal("1110.398"))
    ]
