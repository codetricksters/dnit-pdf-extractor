"""The dashboard shell: navbar, contract selector, tabs and the shared styles.

Only the frame is built here. Each tab's content is rendered by a callback (see
``views.py`` and ``callbacks.py``) so that what the user sees reflects the
database at the moment they look, not at the moment the process started.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc

STYLE_HEADER = {
    "backgroundColor": "#1c2b3c",
    "color": "#bec6e0",
    "fontWeight": "600",
    "fontSize": "11px",
    "letterSpacing": "0.05em",
    "textTransform": "uppercase",
    "border": "1px solid rgba(69, 70, 77, 0.3)",
    "fontFamily": "'Inter', system-ui, sans-serif",
    "padding": "12px 8px",
}

STYLE_CELL = {
    "backgroundColor": "#051424",
    "color": "#d4e4fa",
    "border": "1px solid rgba(69, 70, 77, 0.2)",
    "fontFamily": "'JetBrains Mono', monospace",
    "fontSize": "13px",
    "padding": "10px 8px",
    "textAlign": "right",
}

STYLE_DATA_CONDITIONAL = [
    {"if": {"row_index": "odd"}, "backgroundColor": "#0d1c2d"},
    {"if": {"column_id": "Período"}, "textAlign": "left"},
    {"if": {"column_id": "Descrição"}, "textAlign": "left"},
]

STYLE_FILTER = {
    "backgroundColor": "#122131",
    "color": "#d4e4fa",
    "border": "1px solid rgba(69, 70, 77, 0.3)",
}

STYLE_INPUT = {
    "backgroundColor": "#122131",
    "color": "#d4e4fa",
    "border": "1px solid rgba(69, 70, 77, 0.3)",
}

ABAS = [
    ("reequilibrio", "Reequilíbrio"),
    ("cadastro", "Cadastro do contrato"),
    ("pendencias", "Códigos pendentes"),
    ("indices", "Índices"),
    ("administracao", "Templates e backup"),
]


def build_layout():
    barra = dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand(
                    "DNIT — Reequilíbrio de Materiais Betuminosos", className="ms-2"
                ),
                dbc.Nav(
                    dbc.NavItem(
                        dbc.NavLink("Voltar ao Extrator", href="/", external_link=True)
                    ),
                    navbar=True,
                ),
            ],
            fluid=True,
        ),
        color="#0a1628",
        dark=True,
        className="mb-4",
        style={"borderBottom": "1px solid rgba(69, 70, 77, 0.3)"},
    )

    seletor = dbc.Row(
        [
            dbc.Col(dbc.Label("Contrato:"), width="auto"),
            dbc.Col(
                dcc.Dropdown(
                    id="contrato",
                    placeholder="Selecione o contrato",
                    style={"minWidth": "320px"},
                ),
                width="auto",
            ),
        ],
        className="mb-3",
        align="center",
    )

    return dbc.Container(
        [
            barra,
            seletor,
            dbc.Tabs(
                [dbc.Tab(label=rotulo, tab_id=aba) for aba, rotulo in ABAS],
                id="aba",
                active_tab=ABAS[0][0],
                className="mb-3",
            ),
            dcc.Loading(html.Div(id="conteudo")),
            # Bumped by every write so the screens re-render from the database
            # instead of showing what was true before the click.
            dcc.Store(id="recarregar", data=0),
        ],
        fluid=True,
        style={
            "backgroundColor": "#020617",
            "minHeight": "100vh",
            "paddingBottom": "40px",
        },
    )
