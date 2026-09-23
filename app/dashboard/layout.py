"""The dashboard shell: sidebar, step trail, contract selector and the styles.

Only the frame is built here. Each screen's content is rendered by a callback (see
``views.py`` and ``callbacks.py``) so that what the user sees reflects the
database at the moment they look, not at the moment the process started.

The shell is deliberately the same object as the one in ``app/templates`` — same
markup, same classes, same ``style.css`` (loaded through ``external_stylesheets``,
so still same-origin and no CDN). Navigation is driven by the sidebar, not by
tabs: the whole point of the design is that the user always sees where the
contract stands, and a tab strip hid that.
"""

from dash import dcc, html

from ..services.progresso import Resumo

# Tokens duplicated from style.css because DataTable takes style dicts, not CSS.
# Kept in sync with the :root block in style.css ("Audit Precision Dark").
COR_FUNDO = "#020617"
COR_SUPERFICIE = "#051424"
COR_LINHA_PAR = "#0d1c2d"
COR_CABECALHO = "#1c2b3c"
COR_TEXTO = "#f8fafc"
COR_DESTAQUE = "#38bdf8"
COR_BORDA = "rgba(69, 70, 77, 0.35)"

ALTURA_LINHA = "32px"

STYLE_HEADER = {
    "backgroundColor": COR_CABECALHO,
    "color": COR_DESTAQUE,
    "fontWeight": "600",
    "fontSize": "11px",
    "letterSpacing": "0.05em",
    "textTransform": "uppercase",
    "border": f"1px solid {COR_BORDA}",
    "fontFamily": "'Inter', system-ui, sans-serif",
    "padding": "10px 8px",
    "whiteSpace": "pre-line",
}

STYLE_CELL = {
    "backgroundColor": COR_SUPERFICIE,
    "color": COR_TEXTO,
    "border": f"1px solid {COR_BORDA}",
    "fontFamily": "'JetBrains Mono', ui-monospace, monospace",
    "fontVariantNumeric": "tabular-nums",
    "fontSize": "13px",
    "height": ALTURA_LINHA,
    "padding": "6px 8px",
    "textAlign": "right",
}

STYLE_DATA_CONDITIONAL = [
    {"if": {"row_index": "odd"}, "backgroundColor": COR_LINHA_PAR},
    {"if": {"column_id": "Período"}, "textAlign": "left",
     "fontFamily": "'Inter', system-ui, sans-serif"},
    {"if": {"column_id": "Descrição"}, "textAlign": "left",
     "fontFamily": "'Inter', system-ui, sans-serif"},
]

STYLE_FILTER = {
    "backgroundColor": "#122131",
    "color": COR_TEXTO,
    "border": f"1px solid {COR_BORDA}",
}

STYLE_INPUT = {
    "backgroundColor": "#122131",
    "color": COR_TEXTO,
    "border": f"1px solid {COR_BORDA}",
}

ABAS = [
    ("reequilibrio", "Reequilíbrio"),
    ("cadastro", "Cadastro do contrato"),
    ("pendencias", "Códigos pendentes"),
    ("indices", "Índices"),
    ("administracao", "Templates e backup"),
]

# Sidebar entries for the reequilíbrio group: (aba, rótulo, ícone).
NAVEGACAO = [
    ("reequilibrio", "Memória de Cálculo", "calculate"),
    ("cadastro", "Cadastro do Contrato", "fact_check"),
    ("pendencias", "Códigos Pendentes", "rule"),
    ("indices", "Índices ANP / FGV", "monitoring"),
    ("administracao", "Templates & Backup", "settings_backup_restore"),
]

TITULOS = {
    "reequilibrio": (
        "Memória de Cálculo",
        "O REF do art. 16, linha por linha, com o ΔP calculado contra a Data Base.",
    ),
    "cadastro": (
        "Cadastro do Contrato & Região ANP",
        "Os campos que nenhum PDF traz e a região da ANP de cada família.",
    ),
    "pendencias": (
        "Códigos Pendentes de Homologação",
        "Um código não confirmado fica fora do cálculo — nada entra classificado errado.",
    ),
    "indices": (
        "Índices ANP / FGV",
        "Cobertura das séries e entrada dos valores publicados.",
    ),
    "administracao": (
        "Templates & Backup",
        "O template da planilha e os dumps do banco, sem terminal.",
    ),
}


def icone(nome: str, className: str = "material-symbols-outlined"):
    return html.Span(nome, className=className)


def _span(texto, className=None):
    return html.Span(texto, className=className)


def painel_contrato(resumo: Resumo):
    """The "Contrato ativo" block in the sidebar."""
    return [
        html.Div(
            [
                _span("Contrato ativo", className="label-md label-caps muted"),
                html.Span(
                    [icone("warning"), f"{resumo.pendencias} pendência"
                     + ("s" if resumo.pendencias != 1 else "")],
                    className="badge badge-warn",
                ) if resumo.pendencias else None,
            ],
            className="sidebar-contract-head",
        ),
        html.Div(
            [
                icone("description"),
                html.Div(
                    [
                        html.P(resumo.rotulo_contrato, className="sidebar-contract-number"),
                        html.P(resumo.descricao_contrato, className="body-sm muted"),
                    ]
                ),
            ],
            className="sidebar-contract-card",
        ),
    ]


def trilha(resumo: Resumo):
    """The six-step trail, identical to the one in the Jinja shell."""
    filhos = []
    for indice, etapa in enumerate(resumo.etapas):
        if indice:
            filhos.append(icone("chevron_right", "material-symbols-outlined step-sep"))
        filhos.append(
            html.A(
                [icone(etapa.icone), _span(f"{etapa.numero}. {etapa.rotulo}")],
                href=etapa.destino,
                title=etapa.detalhe,
                className=f"step step-{etapa.status}",
            )
        )
    return filhos


def _barra_lateral():
    return html.Div(
        [
            html.Div(
                [
                    html.Img(src="/static/images/logo.svg", className="brand-mark", alt=""),
                    html.Div(
                        [
                            html.P("DNIT", className="brand-title"),
                            html.P("Extrator & Reequilíbrio", className="brand-sub"),
                        ]
                    ),
                ],
                className="sidebar-brand",
            ),
            html.Div(id="painel-contrato", className="sidebar-contract"),
            html.Nav(
                [
                    html.Div(
                        [
                            html.P("Extrator de dados", className="nav-group-title"),
                            html.A(
                                [icone("upload_file"), _span("Upload & Processamento")],
                                href="/", className="nav-item",
                            ),
                            html.A(
                                [icone("pending_actions"), _span("Fila de Jobs")],
                                href="/", className="nav-item",
                            ),
                            html.A(
                                [icone("inventory_2"), _span("Arquivos Processados")],
                                href="/", className="nav-item",
                            ),
                        ],
                        className="nav-group",
                    ),
                    html.Div(
                        [html.P("Reequilíbrio & auditoria", className="nav-group-title")]
                        + [
                            html.A(
                                [icone(ico), _span(rotulo)],
                                id={"tipo": "nav-aba", "aba": aba},
                                n_clicks=0,
                                className="nav-item",
                            )
                            for aba, rotulo, ico in NAVEGACAO
                        ],
                        className="nav-group",
                    ),
                ],
                className="sidebar-nav",
            ),
            html.Div(
                [_span("Medições no banco"), html.Span(id="rodape-itens", className="num")],
                className="sidebar-footer",
            ),
        ],
        className="sidebar",
    )


def _topo():
    return html.Div(
        [
            html.Div(id="trilha", className="steps"),
            html.Div(
                [
                    html.Span(
                        [icone("verified_user"), _span("Memória de cálculo auditável")],
                        className="topbar-user",
                    ),
                    html.A(icone("api"), href="/docs", className="topbar-avatar",
                           title="Documentação da API"),
                ],
                className="topbar-right",
            ),
        ],
        className="topbar",
    )


def _cabecalho_pagina():
    return html.Div(
        [
            html.Div(
                [
                    html.P(
                        [
                            icone("analytics"),
                            _span("Reequilíbrio econômico-financeiro"),
                            _span("/", className="sep"),
                            html.Span(id="crumb-atual", className="current"),
                        ],
                        className="page-crumb",
                    ),
                    html.H1(id="titulo-pagina", className="page-title"),
                    html.P(id="subtitulo-pagina", className="page-subtitle"),
                ]
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Contrato", className="field-label"),
                            dcc.Dropdown(
                                id="contrato",
                                placeholder="Selecione o contrato",
                                className="dash-dropdown",
                                style={"minWidth": "320px"},
                            ),
                        ],
                        className="field",
                    )
                ],
                className="page-actions",
            ),
        ],
        className="page-head",
    )


def build_layout():
    return html.Div(
        [
            dcc.Location(id="url", refresh=False),
            _barra_lateral(),
            _topo(),
            html.Main(
                [
                    _cabecalho_pagina(),
                    dcc.Loading(html.Div(id="conteudo"), color=COR_DESTAQUE),
                ],
                className="main-content",
            ),
            # The active screen. A store, not a tab strip: the sidebar is the
            # navigation, and deep links (?aba=cadastro) write here too.
            dcc.Store(id="aba", data=ABAS[0][0]),
            # Bumped by every write so the screens re-render from the database
            # instead of showing what was true before the click.
            dcc.Store(id="recarregar", data=0),
        ],
        className="app-layout",
    )
