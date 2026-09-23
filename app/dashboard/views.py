"""Rendering of each dashboard screen.

Kept apart from ``layout.py`` (the shell and the styles) and from
``callbacks.py`` (the wiring), because these functions are what grow as screens
are added, and each one is a pure function of data it is given — no Dash state,
no database access — which makes them readable and testable on their own.

Every screen is rendered on demand by a callback rather than at start-up: the
data changes while the application runs (a PDF is uploaded, an índice is
published) and a layout built at import time would show a stale picture until
restart.
"""

from dash import dash_table, dcc, html
import dash_bootstrap_components as dbc

from ..services.contratos_repo import CAMPOS_CADASTRO
from ..services.delta_p import FAMILIAS
from ..services.indices_repo import REGIOES
from ..services.reequilibrio_layout import LEGENDA
from .data_loader import COLUNAS, DEFAULT_LUCRO
from .layout import (
    STYLE_CELL,
    STYLE_DATA_CONDITIONAL,
    STYLE_FILTER,
    STYLE_HEADER,
    STYLE_INPUT,
)

ROTULOS_CADASTRO = {
    "edital": "Edital",
    "rodovia": "Rodovia",
    "trecho": "Trecho",
    "subtrecho": "Subtrecho",
    "segmento": "Segmento",
    "extensao": "Extensão (km)",
    "contratada": "Contratada",
}


def _alerta(mensagens: list[str], cor: str = "warning"):
    if not mensagens:
        return None
    return dbc.Alert(
        [html.Div(m) for m in mensagens], color=cor, className="mb-3"
    )


def tela_reequilibrio(
    contrato: dict | None, tabelas: dict, pendencias: list[str], lucro: float = DEFAULT_LUCRO
):
    """The calculation tables, one card per product, plus the download button."""
    if contrato is None:
        return _alerta(
            ["Selecione um contrato. Se a lista está vazia, envie os PDFs das "
             "medições na página do extrator."]
        )

    cartoes = []
    for indice, (produto, df) in enumerate(tabelas.items()):
        cartoes.append(_cartao_produto(indice, produto, df))

    total = sum(df["REF sem Lucro"].sum() for df in tabelas.values())

    return html.Div(
        [
            _cabecalho_contrato(contrato),
            _alerta(pendencias),
            _campo_lucro(lucro),
            *cartoes,
            _cartao_total(total),
            _barra_de_exportacao(contrato["numero"], bool(tabelas and not pendencias)),
        ]
    )


def _campo_lucro(lucro: float):
    """Lets the user try a different lucro on screen.

    Only on screen: the exported spreadsheet carries the contractual 5,11% as a
    formula, so this is for checking a hypothesis, not for changing the export.
    """
    return dbc.Row(
        [
            dbc.Col(dbc.Label("Lucro (na tela):"), width="auto"),
            dbc.Col(
                dbc.Input(
                    id="lucro",
                    type="number",
                    value=lucro,
                    step=0.0001,
                    size="sm",
                    style={**STYLE_INPUT, "width": "120px"},
                ),
                width="auto",
            ),
        ],
        className="mb-3",
        align="center",
    )


def _cabecalho_contrato(contrato: dict):
    """The export's header block, on screen, so the two can be compared."""
    linhas = [f"Contrato: {contrato['numero']}"]
    for campo in CAMPOS_CADASTRO:
        valor = contrato.get(campo)
        linhas.append(f"{ROTULOS_CADASTRO[campo]}: {valor if valor else '—'}")
    linhas.append(f"Processo: {contrato.get('numero_processo') or '—'}")
    data_base = contrato.get("data_base")
    linhas.append(f"Data base: {data_base.strftime('%m/%Y') if data_base else '—'}")
    for familia in FAMILIAS:
        regiao = (contrato.get("regioes") or {}).get(familia)
        linhas.append(f"Região ANP ({familia}): {regiao or '—'}")

    return dbc.Row(
        [
            dbc.Col(
                html.Div([html.Div(linha) for linha in linhas]),
                style={"fontSize": "13px"},
            ),
            dbc.Col(html.Div([html.Div(linha) for linha in LEGENDA])),
        ],
        className="mb-4",
    )


def _cartao_produto(indice: int, produto: str, df):
    tabela = dash_table.DataTable(
        id={"tipo": "tabela-produto", "indice": indice},
        columns=[{"name": c, "id": c} for c in COLUNAS],
        data=df[COLUNAS].to_dict("records"),
        style_table={"overflowX": "auto"},
        style_header=STYLE_HEADER,
        style_cell=STYLE_CELL,
        style_data_conditional=STYLE_DATA_CONDITIONAL,
        style_filter=STYLE_FILTER,
        page_size=20,
        sort_action="native",
        filter_action="native",
    )
    subtotal = df["REF sem Lucro"].sum()

    return dbc.Card(
        [
            dbc.CardHeader(
                html.H5(produto, className="mb-0", style={"color": "#bec6e0"}),
                style={"backgroundColor": "#0a1628"},
            ),
            dbc.CardBody(tabela, style={"padding": "0"}),
            dbc.CardFooter(
                html.Div(
                    [
                        html.Span("SUBTOTAL REF sem Lucro: ", style={"color": "#adc6ff"}),
                        html.Span(
                            f"{subtotal:,.2f}",
                            style={"fontFamily": "'JetBrains Mono', monospace"},
                        ),
                    ],
                    style={"textAlign": "right"},
                ),
                style={"backgroundColor": "#0a1628"},
            ),
        ],
        className="mb-4",
        style={"backgroundColor": "#051424", "border": "1px solid rgba(69,70,77,.3)"},
    )


def _cartao_total(total: float):
    return dbc.Card(
        dbc.CardBody(
            html.Div(
                [
                    html.Span("TOTAL REEQUILÍBRIO: ", style={"color": "#adc6ff"}),
                    html.Span(
                        f"{total:,.2f}",
                        style={
                            "fontSize": "18px",
                            "fontWeight": "600",
                            "fontFamily": "'JetBrains Mono', monospace",
                        },
                    ),
                ],
                style={"textAlign": "right"},
            )
        ),
        style={"backgroundColor": "#0a1628", "border": "2px solid #adc6ff"},
        className="mb-4",
    )


def _barra_de_exportacao(numero: str, liberado: bool):
    """Download link, disabled while anything is missing.

    A plain link rather than a button with a callback: the file is served by
    ``/reequilibrio/planilha``, so the browser downloads it directly instead of
    the bytes travelling through a Dash callback.
    """
    if not liberado:
        return dbc.Alert(
            "A planilha fica disponível quando não houver pendências acima.",
            color="secondary",
        )
    return html.Div(
        dbc.Button(
            "Baixar planilha (.xlsx)",
            href=f"/reequilibrio/planilha?contrato={numero}",
            external_link=True,
            target="_blank",
            color="primary",
        ),
        className="mb-4",
    )


def tela_cadastro(contrato: dict | None):
    """The fields no PDF carries, plus the ANP region of each family."""
    if contrato is None:
        return _alerta(["Selecione um contrato para cadastrar os dados."])

    campos = [
        dbc.Row(
            [
                dbc.Col(dbc.Label(ROTULOS_CADASTRO[campo]), width=3),
                dbc.Col(
                    dbc.Input(
                        id={"tipo": "campo-cadastro", "campo": campo},
                        value=contrato.get(campo) if contrato.get(campo) is not None else "",
                        style=STYLE_INPUT,
                    )
                ),
            ],
            className="mb-2",
        )
        for campo in CAMPOS_CADASTRO
    ]

    regioes = [
        dbc.Row(
            [
                dbc.Col(dbc.Label(f"Região ANP — {familia}"), width=3),
                dbc.Col(
                    dcc.Dropdown(
                        id={"tipo": "regiao-familia", "familia": familia},
                        options=[{"label": r, "value": r} for r in REGIOES],
                        value=(contrato.get("regioes") or {}).get(familia),
                        placeholder="Escolha a região",
                    )
                ),
            ],
            className="mb-2",
        )
        for familia in FAMILIAS
    ]

    return html.Div(
        [
            html.H5(f"Contrato {contrato['numero']}", className="mb-3"),
            # Read-only on purpose: both come from the PDF, and the Data Base is
            # what anchors the ΔP — a typo here would move every calculation.
            dbc.Alert(
                [
                    html.Div(f"Data base (do PDF): {contrato.get('data_base') or '—'}"),
                    html.Div(f"Processo (do PDF): {contrato.get('numero_processo') or '—'}"),
                ],
                color="dark",
            ),
            *campos,
            html.Hr(),
            html.P(
                "As regiões são independentes: o CAP pode ser cotado numa região "
                "e as emulsões noutra.",
                style={"fontSize": "13px", "color": "#adc6ff"},
            ),
            *regioes,
            dbc.Button("Salvar cadastro", id="salvar-cadastro", color="primary"),
            html.Div(id="aviso-cadastro", className="mt-3"),
        ]
    )


def tela_pendencias(pendencias: list[dict], produtos: list[dict]):
    """Service codes seen in PDFs that nobody has confirmed yet.

    Unconfirmed codes stay out of the calculation, so this screen is what keeps a
    new material from being silently left out — or silently counted in the wrong
    family.

    Confirming means choosing the product the code belongs to, which is how
    several codes end up under one export description: the provisional product
    the app created from the PDF description is pre-selected, and pointing the
    code at an existing product instead merges it there.
    """
    if not pendencias:
        return dbc.Alert("Nenhum código pendente de confirmação.", color="success")

    opcoes = [
        {"label": f"{p['descricao_export']} ({p['familia']})", "value": p["id"]}
        for p in produtos
    ]

    itens = [
        dbc.ListGroupItem(
            dbc.Row(
                [
                    dbc.Col(html.Strong(p["codigo_servico"]), width=2),
                    dbc.Col(html.Span(p.get("descricao_pdf") or "—")),
                    dbc.Col(
                        dcc.Dropdown(
                            id={"tipo": "produto-pendencia", "codigo": p["codigo_servico"]},
                            options=opcoes,
                            value=p.get("produto_id"),
                            placeholder="Produto de exportação",
                        ),
                        width=3,
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Confirmar",
                            id={"tipo": "confirmar-codigo", "codigo": p["codigo_servico"]},
                            size="sm",
                            color="success",
                        ),
                        width=2,
                    ),
                ],
                align="center",
            ),
            style={"backgroundColor": "#051424"},
        )
        for p in pendencias
    ]
    return html.Div(
        [
            html.P(
                "Códigos não confirmados ficam fora do cálculo. Confira o produto "
                "sugerido antes de confirmar — vários códigos podem apontar para o "
                "mesmo produto.",
                style={"fontSize": "13px", "color": "#adc6ff"},
            ),
            dbc.ListGroup(itens),
            html.Div(id="aviso-pendencias", className="mt-3"),
        ]
    )


def tela_administracao(templates: list[dict], backups: list[dict]):
    """Templates and backups.

    Both are here rather than on the filesystem because the application runs in
    Docker and the user has no practical access to the container's files.
    """
    return html.Div(
        [
            html.H5("Template da planilha", className="mb-2"),
            html.P(
                "O template define o layout, o logotipo e a memória de cálculo. "
                "Edite-o no Excel e envie de volta.",
                style={"fontSize": "13px", "color": "#adc6ff"},
            ),
            dcc.Upload(
                id="enviar-template",
                children=dbc.Button("Enviar template (.xlsx)", color="primary"),
                multiple=False,
                className="mb-2",
            ),
            html.Div(id="aviso-template"),
            _lista_templates(templates),
            html.Hr(className="my-4"),
            html.H5("Backups do banco", className="mb-2"),
            html.P(
                "O backup cobre tudo: índices, contratos, medições e os templates.",
                style={"fontSize": "13px", "color": "#adc6ff"},
            ),
            dbc.Button("Gerar backup agora", id="gerar-backup", color="primary"),
            dcc.Upload(
                id="enviar-backup",
                children=dbc.Button("Enviar backup (.dump)", color="secondary"),
                multiple=False,
                className="ms-2 d-inline-block",
            ),
            html.Div(id="aviso-backup", className="mt-2"),
            _lista_backups(backups),
        ]
    )


def _lista_templates(templates: list[dict]):
    if not templates:
        return dbc.Alert("Nenhum template cadastrado.", color="warning")
    return dbc.ListGroup(
        [
            dbc.ListGroupItem(
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Strong(t["nome"]),
                                dbc.Badge(
                                    "ativo", color="success", className="ms-2"
                                ) if t["ativo"] else None,
                                html.Div(
                                    t["criado_em"].strftime("%d/%m/%Y %H:%M"),
                                    style={"fontSize": "12px", "color": "#adc6ff"},
                                ),
                            ]
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Baixar",
                                href=f"/admin/templates/{t['id']}/download",
                                external_link=True,
                                size="sm",
                                color="secondary",
                            ),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Ativar",
                                id={"tipo": "ativar-template", "id": t["id"]},
                                size="sm",
                                color="primary",
                                disabled=t["ativo"],
                            ),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Excluir",
                                id={"tipo": "excluir-template", "id": t["id"]},
                                size="sm",
                                color="danger",
                                # The active template cannot be deleted; showing
                                # it disabled explains why without a failed click.
                                disabled=t["ativo"],
                            ),
                            width="auto",
                        ),
                    ],
                    align="center",
                ),
                style={"backgroundColor": "#051424"},
            )
            for t in templates
        ]
    )


def _lista_backups(backups: list[dict]):
    if not backups:
        return dbc.Alert("Nenhum backup gerado ainda.", color="warning")
    return dbc.ListGroup(
        [
            dbc.ListGroupItem(
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Strong(b["nome"]),
                                html.Div(
                                    f"{b['criado_em'].strftime('%d/%m/%Y %H:%M')} — "
                                    f"{b['tamanho'] / 1024:,.0f} kB",
                                    style={"fontSize": "12px", "color": "#adc6ff"},
                                ),
                            ]
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Baixar",
                                href=f"/admin/backups/{b['nome']}/download",
                                external_link=True,
                                size="sm",
                                color="secondary",
                            ),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Restaurar",
                                id={"tipo": "restaurar-backup", "nome": b["nome"]},
                                size="sm",
                                color="warning",
                            ),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Excluir",
                                id={"tipo": "excluir-backup", "nome": b["nome"]},
                                size="sm",
                                color="danger",
                            ),
                            width="auto",
                        ),
                    ],
                    align="center",
                ),
                style={"backgroundColor": "#051424"},
            )
            for b in backups
        ]
        + [_confirmacao_de_restauracao()]
    )


def _confirmacao_de_restauracao():
    """Restoring replaces the whole database, so it asks for the name typed out.

    The service checks the confirmation again, so this field is the explanation,
    not the protection.
    """
    return dbc.ListGroupItem(
        [
            html.Div(
                "Restaurar substitui todo o conteúdo do banco. Digite o nome do "
                "backup para confirmar; um backup do estado atual é gerado antes.",
                style={"fontSize": "13px", "color": "#ffb4a2"},
            ),
            dbc.Input(
                id="confirmacao-restauracao",
                placeholder="nome do backup",
                style=STYLE_INPUT,
                className="mt-2",
            ),
        ],
        style={"backgroundColor": "#0a1628"},
    )


def tela_indices(cobertura: dict):
    """What the índices tables currently cover.

    The ΔP is only as current as these two series, and the user is the one who
    feeds them, so the coverage is shown rather than left to be discovered by a
    failed export.
    """
    anp = cobertura.get("anp") or {}
    igp = cobertura.get("igp_di") or {}
    return html.Div(
        [
            html.H5("Índices", className="mb-3"),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H6("ANP — preços semanais"),
                                    html.Div(f"Registros: {anp.get('registros', 0)}"),
                                    html.Div(f"De: {anp.get('de') or '—'}"),
                                    html.Div(f"Até: {anp.get('ate') or '—'}"),
                                    html.Div(
                                        "Regiões: "
                                        + (", ".join(cobertura.get("regioes") or []) or "—")
                                    ),
                                ]
                            ),
                            style={"backgroundColor": "#051424"},
                        )
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H6("Índices mensais (IGP-DI)"),
                                    html.Div(f"Registros: {igp.get('registros', 0)}"),
                                    html.Div(f"De: {igp.get('de') or '—'}"),
                                    html.Div(f"Até: {igp.get('ate') or '—'}"),
                                ]
                            ),
                            style={"backgroundColor": "#051424"},
                        )
                    ),
                ]
            ),
            html.Hr(className="my-4"),
            _formulario_anp(),
            html.Hr(className="my-4"),
            _formulario_mensal(),
        ]
    )


def _formulario_anp():
    """Entry of one weekly ANP price, per region.

    One region at a time: the published table has a column per region, but a user
    typically adds the region their contract uses.
    """
    return html.Div(
        [
            html.H6("Acrescentar preço semanal da ANP"),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.DatePickerSingle(
                            id="anp-inicio", display_format="DD/MM/YYYY",
                            placeholder="Início da vigência",
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dcc.DatePickerSingle(
                            id="anp-fim", display_format="DD/MM/YYYY",
                            placeholder="Fim da vigência",
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dcc.Dropdown(
                            id="anp-regiao",
                            options=[{"label": r, "value": r} for r in REGIOES],
                            placeholder="Região",
                            style={"width": "180px"},
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Input(
                            id="anp-preco", type="number", step=0.0001,
                            placeholder="R$/kg", style={**STYLE_INPUT, "width": "140px"},
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Button("Gravar", id="gravar-anp", color="primary", size="sm"),
                        width="auto",
                    ),
                ],
                align="center",
            ),
            html.Div(id="aviso-anp", className="mt-2"),
        ]
    )


def _formulario_mensal():
    return html.Div(
        [
            html.H6("Acrescentar índice mensal"),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Input(
                            id="mensal-indice", value="IGP - DI",
                            style={**STYLE_INPUT, "width": "180px"},
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dcc.DatePickerSingle(
                            id="mensal-mes", display_format="MM/YYYY",
                            placeholder="Mês de referência",
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Input(
                            id="mensal-valor", type="number", step=0.0001,
                            placeholder="Valor", style={**STYLE_INPUT, "width": "140px"},
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Button("Gravar", id="gravar-mensal", color="primary", size="sm"),
                        width="auto",
                    ),
                ],
                align="center",
            ),
            html.Div(id="aviso-mensal", className="mt-2"),
        ]
    )
