from dash import Input, Output, callback_context

from .data_loader import load_reequilibrio_data, compute_ref_columns, DEFAULT_LUCRO

COLUMNS = [
    "Período",
    "Descrição",
    "Valor a PI",
    "Fator de Reajuste",
    "Reajustamento da Medição (R)",
    "∆P",
    "Reajustamento Total Base Produtor",
    "REF Bruto com Lucro",
    "REF sem Lucro",
]


def register_callbacks(app):
    data = load_reequilibrio_data()
    if not data:
        return

    items = sorted(data.items())

    for idx, (item_name, df) in enumerate(items):
        _register_table_callback(app, idx, df)

    _register_total_callback(app, len(items))


def _register_table_callback(app, idx, base_df):
    @app.callback(
        Output(f"table-{idx}", "data"),
        [
            Input(f"delta-p-{idx}", "value"),
            Input(f"lucro-{idx}", "value"),
        ],
    )
    def update_table(delta_p, lucro, _df=base_df):
        dp = float(delta_p) if delta_p is not None else 0.0
        lc = float(lucro) if lucro is not None else DEFAULT_LUCRO
        updated = compute_ref_columns(_df, dp, lc)
        return updated[COLUMNS].to_dict("records")

    @app.callback(
        Output(f"subtotal-{idx}", "children"),
        Input(f"table-{idx}", "derived_virtual_data"),
    )
    def update_subtotal(filtered_rows):
        if not filtered_rows:
            return "0.00"
        subtotal = sum(row.get("REF sem Lucro", 0) or 0 for row in filtered_rows)
        return f"{subtotal:,.2f}"


def _register_total_callback(app, num_items):
    @app.callback(
        Output("total-reequilibrio", "children"),
        [Input(f"subtotal-{idx}", "children") for idx in range(num_items)],
    )
    def update_total(*subtotals):
        total = 0.0
        for s in subtotals:
            if s:
                try:
                    total += float(s.replace(",", ""))
                except (ValueError, AttributeError):
                    pass
        return f"{total:,.2f}"
