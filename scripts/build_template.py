"""Build the initial export template from the user's reference workbook.

Run once, by hand. The resulting ``app/templates_xlsx/reequilibrio_template.xlsx``
is committed and seeded into the ``template`` table on first migration; from then
on the database is the source of truth and the user maintains templates through
the interface.

Deriving the template from ``data/Reequilíbrio - 26 - Contrato 716-22.xlsx``
rather than drawing it from scratch keeps the layout the user already validates
against — column widths, borders, number formats, the DNIT logo and the
equation — instead of an approximation of it.

What it does: keeps one sheet, clears the contract values and every data row, and
leaves rows 17–20 as **model rows** (group header, data, subtotal, total) whose
formatting the export copies for each row it writes.

    uv run python scripts/build_template.py
"""

import sys
from copy import copy
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import xlsx_drawings  # noqa: E402
from app.services.reequilibrio_layout import (  # noqa: E402
    ABA,
    COL_FIM,
    COL_INICIO,
    LINHA_DADOS,
    LINHA_GRUPO,
    LINHA_SUBTOTAL,
    LINHA_TOTAL,
    PRIMEIRA_LINHA,
)

REFERENCIA = Path("data/Reequilíbrio - 26 - Contrato 716-22.xlsx")
ABA_REFERENCIA = "JAN-23 A JUN-26"
DESTINO = Path("app/templates_xlsx/reequilibrio_template.xlsx")

# Rows in the reference whose formatting each model row is taken from.
MODELOS = {
    LINHA_GRUPO: 17,  # product header, merged B:J
    LINHA_DADOS: 18,  # one measurement month
    LINHA_SUBTOTAL: 60,  # SUBTOTAL, merged H:I
    LINHA_TOTAL: 237,  # TOTAL REEQUILÍBRIO
}


def main() -> None:
    if not REFERENCIA.exists():
        raise SystemExit(f"Arquivo de referência não encontrado: {REFERENCIA}")

    formas = xlsx_drawings.extrair_formas(REFERENCIA, ABA_REFERENCIA)
    if not formas:
        raise SystemExit(
            "A referência não contém a caixa de texto da memória de cálculo."
        )

    wb = openpyxl.load_workbook(REFERENCIA)
    ws = wb[ABA_REFERENCIA]

    # Capture the model formatting before the rows holding it are deleted.
    formatos = {
        destino: [
            copy(ws.cell(origem, col)._style)
            for col in range(COL_INICIO, COL_FIM + 1)
        ]
        for destino, origem in MODELOS.items()
    }
    alturas = {
        destino: ws.row_dimensions[origem].height
        for destino, origem in MODELOS.items()
    }

    ws.delete_rows(PRIMEIRA_LINHA, ws.max_row - PRIMEIRA_LINHA + 1)

    # delete_rows leaves the merged ranges behind, and those keep the deleted
    # cells alive — the sheet would still report 237 rows.
    for faixa in [
        m for m in ws.merged_cells.ranges if m.min_row >= PRIMEIRA_LINHA
    ]:
        # Not unmerge_cells(): it tries to delete cells that delete_rows already
        # removed and raises KeyError.
        ws.merged_cells.ranges.remove(faixa)
    for linha in [r for r in ws.row_dimensions if r > LINHA_TOTAL]:
        del ws.row_dimensions[linha]

    for linha, estilos in formatos.items():
        for deslocamento, estilo in enumerate(estilos):
            ws.cell(linha, COL_INICIO + deslocamento)._style = estilo
        if alturas[linha]:
            ws.row_dimensions[linha].height = alturas[linha]

    # The merges of the model rows, which delete_rows took away with them.
    ws.merge_cells(start_row=LINHA_GRUPO, start_column=2, end_row=LINHA_GRUPO, end_column=10)
    ws.merge_cells(start_row=LINHA_SUBTOTAL, start_column=8, end_row=LINHA_SUBTOTAL, end_column=9)
    ws.merge_cells(start_row=LINHA_TOTAL, start_column=8, end_row=LINHA_TOTAL, end_column=9)

    # Contract values are filled per export; the labels stay.
    for linha in range(3, 13):
        ws.cell(linha, 3).value = None

    # One sheet only: the reference's other sheets hold a specific contract's
    # calculation, and the app computes ΔP itself.
    ws.title = ABA
    for nome in [s for s in wb.sheetnames if s != ABA]:
        del wb[nome]
    for nome in list(wb.defined_names):
        del wb.defined_names[nome]

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    wb.save(DESTINO)
    xlsx_drawings.injetar_formas_em_arquivo(DESTINO, ABA, formas)

    print(f"Template gravado em {DESTINO}")
    print(f"  memória de cálculo presente: {xlsx_drawings.contem_equacao(DESTINO, ABA)}")


if __name__ == "__main__":
    main()
