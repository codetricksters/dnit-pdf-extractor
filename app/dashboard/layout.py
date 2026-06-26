from dash import html, dash_table
import dash_bootstrap_components as dbc

from .data_loader import load_reequilibrio_data, DEFAULT_LUCRO

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
    {
        "if": {"row_index": "odd"},
        "backgroundColor": "#0d1c2d",
    },
    {
        "if": {"column_id": "Período"},
        "textAlign": "left",
    },
    {
        "if": {"column_id": "Descrição"},
        "textAlign": "left",
    },
]

STYLE_FILTER = {
    "backgroundColor": "#122131",
    "color": "#d4e4fa",
    "border": "1px solid rgba(69, 70, 77, 0.3)",
}

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


def build_layout():
    data = load_reequilibrio_data()

    nav_bar = dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand(
                    "DNIT — Reequilíbrio de Materiais Betuminosos", className="ms-2"
                ),
                dbc.Nav(
                    [
                        dbc.NavItem(
                            dbc.NavLink(
                                "Voltar ao Extrator", href="/", external_link=True
                            )
                        ),
                    ],
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

    if not data:
        return dbc.Container(
            [
                nav_bar,
                dbc.Alert(
                    "Nenhum dado de AQUISIÇÃO encontrado. Processe PDFs com itens de aquisição de materiais betuminosos.",
                    color="warning",
                    className="mt-4",
                ),
            ],
            fluid=True,
            style={"backgroundColor": "#020617", "minHeight": "100vh"},
        )
    header = html.Div(
        [
            dbc.Row(
                dbc.Col(html.H4("""ESTUDO REEQUILÍBRIO DOS MATERIAIS BETUMINOSOS"""), align='center'), justify='center'
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            children=[
                                "Contrato: 	12 00426/2021",html.Br(),
                                "Edital:	0168/2021",html.Br(),
                                "Rodovia:	BR-251/GO e BR-251/GO",html.Br(),
                                "Trecho: 	TRECHO 1: DIV MG/GO - RIO ARAGUAIA (ARUANÃ) (DIV GO/MT); TRECHO 2: ENTR DF-295 (DIV GO/DF) - ENTR DF-180(B) (DIV DF/GO)",html.Br(),
                                "Subtrecho:	SUBTRECHO 1: DIV MG/GO - ENTR GO-080(A) (DIV GO/DF) SUBTRECHO 2: ENTR DF-295 (DIV GO/DF) - ENTR BR-040/050/450 (CENTRO RODOVIÁRIO DNIT (BRASÍLIA)",html.Br(),
                                "Segmento:	SEGMENTO 1: km 0,00 ao km 34,00; SEGMENTO 2: km 0,00 ao km 60,80",html.Br(),
                                "Extensão: 	94,80 KM",html.Br(),
                                "Contratada: 	HWN Engenharia Ltda",html.Br(),
                                "Processo:	50612.002481/2020-10",html.Br(),
                                "Data base:	July de 2020",html.Br(),
                                "Período:	Setembro de 2021 a Dezembro de 2021"
                            ]
                        )
                    ),
                    dbc.Col(
                        html.Div(
                            children=[
                            '∆𝑃= Variação do Preço Produtor calculado nos termos do artigo 16',html.Br(),
                            'PI = Valor medido a preços iniciais',html.Br(),
                            'R = Valor Medido referente a parcela de reajustamento',html.Br(),
                            'm = Mês de Análise do REF',html.Br(),
                            ]
                        )
                    ),
                ]
            ),
        ]
    )
    section_cards = []
    for idx, (item_name, df) in enumerate(sorted(data.items())):
        subtotal = df["REF sem Lucro"].sum()

        table = dash_table.DataTable(
            id=f"table-{idx}",
            columns=[{"name": col, "id": col} for col in COLUMNS],
            data=df[COLUMNS].to_dict("records"),
            style_table={"overflowX": "auto"},
            style_header=STYLE_HEADER,
            style_cell=STYLE_CELL,
            style_data_conditional=STYLE_DATA_CONDITIONAL,
            style_filter=STYLE_FILTER,
            page_size=20,
            sort_action="native",
            filter_action="native",
        )

        card = dbc.Card(
            [
                dbc.CardHeader(
                    [
                        html.Div(
                            [
                                html.H5(
                                    item_name,
                                    className="mb-0",
                                    style={"color": "#bec6e0"},
                                ),
                                html.Div(
                                    [
                                        html.Label(
                                            "∆P: ",
                                            style={
                                                "color": "#adc6ff",
                                                "marginRight": "8px",
                                                "fontSize": "13px",
                                            },
                                        ),
                                        dbc.Input(
                                            id=f"delta-p-{idx}",
                                            type="number",
                                            value=0,
                                            step=0.0001,
                                            size="sm",
                                            style={
                                                "width": "120px",
                                                "backgroundColor": "#122131",
                                                "color": "#d4e4fa",
                                                "border": "1px solid rgba(69, 70, 77, 0.3)",
                                            },
                                        ),
                                        html.Label(
                                            "Lucro: ",
                                            style={
                                                "color": "#adc6ff",
                                                "marginRight": "8px",
                                                "marginLeft": "16px",
                                                "fontSize": "13px",
                                            },
                                        ),
                                        dbc.Input(
                                            id=f"lucro-{idx}",
                                            type="number",
                                            value=DEFAULT_LUCRO,
                                            step=0.0001,
                                            size="sm",
                                            style={
                                                "width": "120px",
                                                "backgroundColor": "#122131",
                                                "color": "#d4e4fa",
                                                "border": "1px solid rgba(69, 70, 77, 0.3)",
                                            },
                                        ),
                                    ],
                                    style={"display": "flex", "alignItems": "center"},
                                ),
                            ],
                            style={
                                "display": "flex",
                                "justifyContent": "space-between",
                                "alignItems": "center",
                            },
                        ),
                    ],
                    style={
                        "backgroundColor": "#0a1628",
                        "border": "1px solid rgba(69, 70, 77, 0.3)",
                    },
                ),
                dbc.CardBody(table, style={"padding": "0"}),
                dbc.CardFooter(
                    html.Div(
                        [
                            html.Span(
                                "SUBTOTAL REF sem Lucro: ", style={"color": "#adc6ff"}
                            ),
                            html.Span(
                                f"{subtotal:,.2f}",
                                id=f"subtotal-{idx}",
                                style={
                                    "color": "#d4e4fa",
                                    "fontFamily": "'JetBrains Mono', monospace",
                                },
                            ),
                        ],
                        style={"textAlign": "right"},
                    ),
                    style={
                        "backgroundColor": "#0a1628",
                        "border": "1px solid rgba(69, 70, 77, 0.3)",
                    },
                ),
            ],
            className="mb-4",
            style={
                "backgroundColor": "#051424",
                "border": "1px solid rgba(69, 70, 77, 0.3)",
            },
        )

        section_cards.append(card)

    total_ref = sum(df["REF sem Lucro"].sum() for df in data.values())
    total_card = dbc.Card(
        [
            dbc.CardBody(
                html.Div(
                    [
                        html.Span(
                            "TOTAL REEQUILÍBRIO: ",
                            style={"color": "#adc6ff", "fontSize": "16px"},
                        ),
                        html.Span(
                            f"{total_ref:,.2f}",
                            id="total-reequilibrio",
                            style={
                                "color": "#d4e4fa",
                                "fontSize": "18px",
                                "fontWeight": "600",
                                "fontFamily": "'JetBrains Mono', monospace",
                            },
                        ),
                    ],
                    style={"textAlign": "right"},
                ),
                style={"padding": "16px 24px"},
            ),
        ],
        style={"backgroundColor": "#0a1628", "border": "2px solid #adc6ff"},
        className="mb-4",
    )

    return dbc.Container(
        [
            nav_bar,
            header,
            *section_cards,
            total_card,
        ],
        fluid=True,
        style={
            "backgroundColor": "#020617",
            "minHeight": "100vh",
            "paddingBottom": "40px",
        },
    )
