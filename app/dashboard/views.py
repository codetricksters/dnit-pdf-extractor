"""Rendering of each dashboard screen.

Kept apart from ``layout.py`` (the shell and the styles) and from
``callbacks.py`` (the wiring), because these functions are what grow as screens
are added, and each one is a pure function of data it is given — no Dash state,
no database access — which makes them readable and testable on their own.

Every screen is rendered on demand by a callback rather than at start-up: the
data changes while the application runs (a PDF is uploaded, an índice is
published) and a layout built at import time would show a stale picture until
restart.

The visual vocabulary is the one in ``style.css`` (panels, notices, badges,
stat cards): the screens here and the upload page are the same interface, so a
class name is preferred over an inline style dict wherever Dash allows it.
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
    icone,
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

# The hint under each field, so the user knows what the export expects before
# typing. "Opcional" means the spreadsheet is generated with the field blank.
DICAS_CADASTRO = {
    "edital": "Obrigatório",
    "rodovia": "BR / UF",
    "trecho": "Delimitação",
    "subtrecho": "Delimitação",
    "segmento": "Quilometragem",
    "extensao": "km",
    "contratada": "Razão social",
}

# Which spreadsheet column each on-screen column becomes, and the letter of the
# equation it carries. The audit is done side by side with the .xlsx, so the
# correspondence is on the header instead of in the user's memory.
COLUNA_PLANILHA = {
    "Período": ("B", ""),
    "Descrição": ("C", ""),
    "Valor a PI": ("D", "a"),
    "Fator de Reajuste": ("E", ""),
    "Reajustamento da Medição (R)": ("F", "b"),
    "∆P": ("G", "d"),
    "Reajustamento Total Base Produtor": ("H", "c = a*d"),
    "REF Bruto com Lucro": ("I", "e = c - b"),
    "REF sem Lucro": ("J", "f = e*(1-5,11%)"),
}


def _brl(valor) -> str:
    """Brazilian formatting, as the user checks it against the spreadsheet."""
    return f"{valor:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _aviso(titulo: str, texto, *, tipo: str = "warn", icone_nome: str = "warning",
           acoes: list | None = None):
    """The notice block: a reason, and the buttons that resolve it.

    ``DESIGN.md`` asks for the blocked export to be *actionable* — the reason and
    the way out in the same place, never a disabled button with no explanation.
    """
    classes = {"warn": "notice", "ok": "notice ok", "danger": "notice danger",
               "info": "notice info"}
    return html.Div(
        [
            html.Div(icone(icone_nome), className="notice-icon"),
            html.Div(
                [
                    html.P(titulo, className="notice-title"),
                    html.Div(texto, className="notice-text"),
                    html.Div(acoes, className="notice-actions") if acoes else None,
                ]
            ),
        ],
        className=classes[tipo],
    )


def _cartao_kpi(rotulo: str, valor: str, nota: str, icone_nome: str, tom: str = ""):
    return html.Div(
        [
            html.Div(
                [
                    html.P(rotulo, className="stat-label"),
                    html.P(html.Span(valor, className="num-strong"), className="stat-value"),
                    html.P([icone(icone_nome), nota], className="stat-note"),
                ],
                className="stat-body",
            ),
            html.Div(icone(icone_nome), className=f"stat-icon {tom}".strip()),
        ],
        className="stat-card",
    )


def _painel(titulo: str, icone_nome: str, corpo, *, subtitulo: str = "",
            acoes=None, rodape=None, rodape_classe: str = "", flush: bool = False):
    return html.Section(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H2([icone(icone_nome), titulo], className="panel-title"),
                            html.P(subtitulo, className="panel-subtitle") if subtitulo else None,
                        ]
                    ),
                    html.Div(acoes, className="page-actions") if acoes else None,
                ],
                className="panel-head",
            ),
            html.Div(corpo, className="panel-body flush" if flush else "panel-body"),
            html.Div(rodape, className=f"panel-foot {rodape_classe}".strip()) if rodape else None,
        ],
        className="panel mt-lg",
    )


# --------------------------------------------------------------- Reequilíbrio


def tela_reequilibrio(
    contrato: dict | None, tabelas: dict, pendencias: list[str], lucro: float = DEFAULT_LUCRO
):
    """The calculation matrix, one panel per product, plus the download button."""
    if contrato is None:
        return _aviso(
            "Nenhum contrato selecionado",
            "Escolha um contrato acima. Se a lista está vazia, envie os PDFs das "
            "medições na página do extrator.",
            tipo="info",
            icone_nome="info",
            acoes=[
                html.A([icone("upload_file"), "Ir para o Upload"], href="/",
                       className="btn btn-primary")
            ],
        )

    liberado = bool(tabelas and not pendencias)
    total = sum(df["REF sem Lucro"].sum() for df in tabelas.values())
    total_pi = sum(df["Valor a PI"].sum() for df in tabelas.values())
    total_r = sum(df["Reajustamento da Medição (R)"].sum() for df in tabelas.values())
    total_bruto = sum(df["REF Bruto com Lucro"].sum() for df in tabelas.values())

    return html.Div(
        [
            _faixa_contrato(contrato),
            _bloco_de_exportacao(contrato["numero"], liberado, pendencias, lucro),
            html.Div(
                [
                    _cartao_kpi("Valor total medido a PI", _brl(total_pi),
                                "Coluna D da planilha", "payments"),
                    _cartao_kpi("Reajustamento contratual (R)", _brl(total_r),
                                "Coluna F, já calculada no PDF", "sync_alt"),
                    _cartao_kpi("REF bruto com lucro", _brl(total_bruto),
                                "Coluna I, art. 16", "trending_up"),
                    _cartao_kpi("REF sem lucro", _brl(total), "Coluna J — o pedido",
                                "verified", "ok" if liberado else "warn"),
                ],
                className="card-grid mt-lg",
            ),
            *[
                _painel(
                    produto,
                    "table_view",
                    _matriz(indice, df),
                    subtitulo="Agrupado por produto; o subtotal repete o da planilha.",
                    rodape=[
                        html.Span("Subtotal REF sem lucro", className="label-md label-caps"),
                        html.Span(_brl(df["REF sem Lucro"].sum()), className="num-strong"),
                    ],
                    rodape_classe="subtotal",
                    flush=True,
                )
                for indice, (produto, df) in enumerate(tabelas.items())
            ],
            html.Div(
                [
                    html.Span("Total geral REF consolidado",
                              className="label-md label-caps"),
                    html.Span(_brl(total), className="num-strong"),
                ],
                className="batch-actions mt-lg grand-total",
            ),
            _painel(
                "Memória de cálculo",
                "functions",
                html.Div([html.P(linha, className="body-md muted") for linha in LEGENDA]),
                subtitulo="A mesma legenda que acompanha a equação no template.",
            ),
        ]
    )


def _faixa_contrato(contrato: dict):
    """The export's header block, on screen, so the two can be compared."""
    itens = [("Contrato", contrato["numero"])]
    for campo in CAMPOS_CADASTRO:
        itens.append((ROTULOS_CADASTRO[campo], contrato.get(campo) or "—"))
    itens.append(("Processo", contrato.get("numero_processo") or "—"))
    data_base = contrato.get("data_base")
    itens.append(("Data Base", data_base.strftime("%m/%Y") if data_base else "—"))
    for familia in FAMILIAS:
        regiao = (contrato.get("regioes") or {}).get(familia)
        itens.append((f"Região ANP ({familia})", regiao or "—"))

    return html.Div(
        [
            html.Div(
                [
                    html.P(rotulo, className="stat-label"),
                    html.P(str(valor), className="num" if rotulo != "Contratada" else "body-md"),
                ],
                className="field",
            )
            for rotulo, valor in itens
        ],
        className="field-grid panel-body panel",
    )


def _matriz(indice: int, df):
    """The dense table. Two header rows: the spreadsheet column, then the name."""
    colunas = []
    for nome in COLUNAS:
        letra, papel = COLUNA_PLANILHA[nome]
        topo = f"COL {letra}" + (f" · {papel}" if papel else "")
        colunas.append({"name": [topo, nome], "id": nome})

    return dash_table.DataTable(
        id={"tipo": "tabela-produto", "indice": indice},
        columns=colunas,
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


def _bloco_de_exportacao(numero: str, liberado: bool, pendencias: list[str], lucro: float):
    """The export, with the reason it is blocked and the screens that unblock it.

    A plain link rather than a button with a callback: the file is served by
    ``/reequilibrio/planilha``, so the browser downloads it directly instead of
    the bytes travelling through a Dash callback.
    """
    campo = html.Div(
        [
            html.Div(
                [
                    html.Span("Lucro (somente na tela)", className="field-label"),
                    html.Span("a planilha mantém 5,11%", className="field-hint"),
                ],
                className="field-head",
            ),
            dbc.Input(id="lucro", type="number", value=lucro, step=0.0001,
                      style={**STYLE_INPUT, "width": "140px"}),
        ],
        className="field",
    )

    if not liberado:
        motivos = pendencias or [
            "Nenhum item de medição confirmado entrou no cálculo deste contrato."
        ]
        return html.Div(
            [
                _aviso(
                    "Cálculo incompleto — exportação bloqueada",
                    html.Ul([html.Li(m) for m in motivos]),
                    acoes=[
                        html.A(
                            [icone("rule"), "Resolver Códigos Pendentes"],
                            href="/dashboard/?aba=pendencias",
                            className="btn",
                        ),
                        html.A(
                            [icone("fact_check"), "Definir Região ANP"],
                            href="/dashboard/?aba=cadastro",
                            className="btn",
                        ),
                        html.A(
                            [icone("monitoring"), "Conferir Índices"],
                            href="/dashboard/?aba=indices",
                            className="btn",
                        ),
                        html.Span([icone("lock"), "Baixar Planilha Excel"],
                                  className="btn disabled"),
                    ],
                ),
                html.Div(campo, className="batch-actions mt-md"),
            ]
        )

    return html.Div(
        [
            _aviso(
                "Cálculo completo",
                "Nenhuma pendência. As colunas F, H, I e J saem como fórmulas; só o "
                "ΔP é gravado como valor.",
                tipo="ok",
                icone_nome="check_circle",
            ),
            html.Div(
                [
                    campo,
                    html.A(
                        [icone("download"), "Baixar Planilha Excel com Fórmulas"],
                        href=f"/reequilibrio/planilha?contrato={numero}",
                        target="_blank",
                        className="btn btn-primary",
                    ),
                ],
                className="batch-actions mt-md",
            ),
        ]
    )


# ------------------------------------------------------------------- Cadastro


def tela_cadastro(contrato: dict | None):
    """The fields no PDF carries, plus the ANP region of each family."""
    if contrato is None:
        return _aviso("Nenhum contrato selecionado",
                      "Escolha um contrato acima para cadastrar os dados.",
                      tipo="info", icone_nome="info")

    vazios = [ROTULOS_CADASTRO[c] for c in CAMPOS_CADASTRO if not contrato.get(c)]

    campos = [
        html.Div(
            [
                html.Div(
                    [
                        html.Span(ROTULOS_CADASTRO[campo], className="field-label"),
                        html.Span(
                            [icone("priority_high"), DICAS_CADASTRO[campo]],
                            className="field-hint",
                        ) if campo == "segmento" else
                        html.Span(DICAS_CADASTRO[campo], className="field-hint"),
                    ],
                    className="field-head",
                ),
                dbc.Input(
                    id={"tipo": "campo-cadastro", "campo": campo},
                    value=contrato.get(campo) if contrato.get(campo) is not None else "",
                    style=STYLE_INPUT,
                ),
            ],
            className="field",
        )
        for campo in CAMPOS_CADASTRO
    ]

    # Read-only on purpose: both come from the PDF, and the Data Base is what
    # anchors the ΔP — a typo here would move every calculation.
    imutaveis = [
        html.Div(
            [
                html.Div(
                    [
                        html.Span(rotulo, className="field-label"),
                        html.Span([icone("lock"), "Imutável"], className="field-hint"),
                    ],
                    className="field-head",
                ),
                dbc.Input(value=str(valor or "—"), disabled=True, style=STYLE_INPUT),
            ],
            className="field",
        )
        for rotulo, valor in (
            ("Data Base (do PDF)", contrato.get("data_base")),
            ("Processo (do PDF)", contrato.get("numero_processo")),
        )
    ]

    return html.Div(
        [
            _aviso(
                f"{len(vazios)} campo(s) do cadastro em branco",
                "A planilha é gerada, mas estes campos saem vazios no cabeçalho do "
                "documento: " + ", ".join(vazios) + ".",
                acoes=None,
            ) if vazios else _aviso("Cadastro completo",
                                    "Todos os campos do cabeçalho estão preenchidos.",
                                    tipo="ok", icone_nome="check_circle"),
            _painel(
                "Dados oficiais do contrato",
                "fact_check",
                html.Div(campos + imutaveis, className="field-grid"),
                subtitulo=f"Contrato {contrato['numero']}",
                acoes=[
                    dbc.Button([icone("save"), "Salvar Alterações do Contrato"],
                               id="salvar-cadastro", className="btn btn-primary")
                ],
                rodape=html.Div(id="aviso-cadastro"),
            ),
            _painel(
                "Associação de famílias betuminosas à região ANP",
                "public",
                html.Div(
                    [
                        html.P(
                            "As regiões são independentes: o CAP pode ser cotado numa "
                            "região e as emulsões noutra. Sem região definida, o ΔP "
                            "daquela família não é calculado e a exportação fica "
                            "bloqueada.",
                            className="body-md muted",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Span(f"Família {familia}",
                                                          className="field-label"),
                                                html.Span(
                                                    [icone("check_circle"), "Região definida"],
                                                    className="badge badge-ok",
                                                )
                                                if (contrato.get("regioes") or {}).get(familia)
                                                else html.Span(
                                                    [icone("warning"), "Não definida — bloqueia o cálculo"],
                                                    className="badge badge-warn",
                                                ),
                                            ],
                                            className="field-head",
                                        ),
                                        dcc.Dropdown(
                                            id={"tipo": "regiao-familia", "familia": familia},
                                            options=[{"label": r, "value": r} for r in REGIOES],
                                            value=(contrato.get("regioes") or {}).get(familia),
                                            placeholder="Escolha a região",
                                            className="dash-dropdown",
                                        ),
                                    ],
                                    className="field",
                                )
                                for familia in FAMILIAS
                            ],
                            className="field-grid mt-md",
                        ),
                    ]
                ),
            ),
        ]
    )


# ----------------------------------------------------------------- Pendências


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
        return _aviso(
            "Nenhum código pendente",
            "Todos os códigos de serviço vistos nos PDFs estão homologados e "
            "entram no cálculo.",
            tipo="ok",
            icone_nome="check_circle",
        )

    opcoes = [
        {"label": f"{p['descricao_export']} ({p['familia']})", "value": p["id"]}
        for p in produtos
    ]

    linhas = [
        html.Tr(
            [
                html.Td(html.Span(p["codigo_servico"], className="num-strong"), className="left"),
                html.Td(
                    [
                        html.Span(p.get("descricao_pdf") or "—", className="cell-title"),
                        html.Span(f"família sugerida: {p.get('familia') or '—'}",
                                  className="cell-note"),
                    ],
                    className="left",
                ),
                html.Td(
                    dcc.Dropdown(
                        id={"tipo": "produto-pendencia", "codigo": p["codigo_servico"]},
                        options=opcoes,
                        value=p.get("produto_id"),
                        placeholder="Produto de exportação",
                        className="dash-dropdown",
                        style={"minWidth": "320px"},
                    ),
                    className="left",
                ),
                html.Td(
                    dbc.Button(
                        [icone("check"), "Confirmar Associação"],
                        id={"tipo": "confirmar-codigo", "codigo": p["codigo_servico"]},
                        className="btn btn-ok btn-sm",
                    ),
                    className="left",
                ),
            ]
        )
        for p in pendencias
    ]

    tabela = html.Div(
        html.Table(
            [
                html.Thead(
                    html.Tr(
                        [
                            html.Th("Código no PDF", className="left"),
                            html.Th("Descrição no resumo", className="left"),
                            html.Th("Produto ANP destino", className="left"),
                            html.Th("Ação", className="left"),
                        ]
                    )
                ),
                html.Tbody(linhas),
            ],
            className="data-table",
        ),
        className="table-scroll",
    )

    return html.Div(
        [
            _aviso(
                f"{len(pendencias)} código(s) de serviço pendente(s) de homologação",
                "Um código não confirmado fica fora do cálculo: nada é classificado "
                "errado em silêncio, mas o valor correspondente também não entra no "
                "REF até a confirmação.",
            ),
            _painel(
                "Fila de homologação ativa",
                "rule",
                tabela,
                subtitulo="Confira o produto sugerido antes de confirmar — vários "
                          "códigos podem apontar para o mesmo produto.",
                rodape=html.Div(id="aviso-pendencias"),
                flush=True,
            ),
        ]
    )


# -------------------------------------------------------- Templates e backup


def tela_administracao(templates: list[dict], backups: list[dict]):
    """Templates and backups.

    Both are here rather than on the filesystem because the application runs in
    Docker and the user has no practical access to the container's files.
    """
    return html.Div(
        [
            _painel(
                "Template da planilha",
                "description",
                html.Div(
                    [
                        html.P(
                            "O template define o layout, o logotipo e a memória de "
                            "cálculo. Edite-o no Excel e envie de volta — um arquivo "
                            "sem a equação ou com o cabeçalho deslocado é recusado.",
                            className="body-md muted",
                        ),
                        html.Div(id="aviso-template", className="mt-sm"),
                        _lista_templates(templates),
                    ]
                ),
                acoes=[
                    dcc.Upload(
                        id="enviar-template",
                        children=html.Span(
                            [icone("upload"), "Enviar template (.xlsx)"],
                            className="btn btn-primary",
                        ),
                        multiple=False,
                    )
                ],
            ),
            _painel(
                "Backups do banco",
                "settings_backup_restore",
                html.Div(
                    [
                        html.P(
                            "Um único arquivo cobre tudo o que é do usuário: índices, "
                            "contratos, itens de medição e os templates.",
                            className="body-md muted",
                        ),
                        html.Div(id="aviso-backup", className="mt-sm"),
                        _lista_backups(backups),
                    ]
                ),
                acoes=[
                    dbc.Button([icone("play_arrow"), "Gerar backup agora"],
                               id="gerar-backup", className="btn btn-primary"),
                    dcc.Upload(
                        id="enviar-backup",
                        children=html.Span([icone("upload"), "Enviar backup (.dump)"],
                                           className="btn"),
                        multiple=False,
                    ),
                ],
            ),
        ]
    )


def _tabela(cabecalhos: list[str], linhas: list):
    return html.Div(
        html.Table(
            [
                html.Thead(html.Tr([html.Th(c, className="left") for c in cabecalhos])),
                html.Tbody(linhas),
            ],
            className="data-table",
        ),
        className="table-scroll mt-md",
    )


def _lista_templates(templates: list[dict]):
    if not templates:
        return _aviso("Nenhum template cadastrado",
                      "Sem template não há exportação. Envie um arquivo .xlsx.")
    linhas = [
        html.Tr(
            [
                html.Td(
                    [
                        html.Span(t["nome"], className="file-row-name"),
                        html.Span(t["criado_em"].strftime("%d/%m/%Y %H:%M"),
                                  className="file-row-note"),
                    ],
                    className="left",
                ),
                html.Td(
                    html.Span([icone("check_circle"), "Ativo"], className="badge badge-ok")
                    if t["ativo"] else html.Span("Histórico", className="badge"),
                    className="left",
                ),
                html.Td(
                    [
                        html.A([icone("download"), "Baixar"],
                               href=f"/admin/templates/{t['id']}/download",
                               className="btn btn-sm"),
                        dbc.Button([icone("task_alt"), "Ativar"],
                                   id={"tipo": "ativar-template", "id": t["id"]},
                                   className="btn btn-sm", disabled=t["ativo"]),
                        # The active template cannot be deleted; showing it
                        # disabled explains why without a failed click.
                        dbc.Button([icone("delete"), "Excluir"],
                                   id={"tipo": "excluir-template", "id": t["id"]},
                                   className="btn btn-sm btn-danger", disabled=t["ativo"]),
                    ],
                    className="left",
                ),
            ]
        )
        for t in templates
    ]
    return _tabela(["Arquivo", "Situação", "Ações"], linhas)


def _lista_backups(backups: list[dict]):
    if not backups:
        return _aviso("Nenhum backup gerado ainda",
                      "Gere o primeiro dump para ter de onde voltar.")
    linhas = [
        html.Tr(
            [
                html.Td(
                    [
                        html.Span(b["nome"], className="file-row-name"),
                        html.Span(b["criado_em"].strftime("%d/%m/%Y %H:%M"),
                                  className="file-row-note"),
                    ],
                    className="left",
                ),
                html.Td(f"{b['tamanho'] / 1024:,.0f} kB".replace(",", "."), className="left"),
                html.Td(
                    [
                        html.A([icone("download"), "Baixar"],
                               href=f"/admin/backups/{b['nome']}/download",
                               className="btn btn-sm"),
                        dbc.Button([icone("restore"), "Restaurar"],
                                   id={"tipo": "restaurar-backup", "nome": b["nome"]},
                                   className="btn btn-sm btn-danger"),
                        dbc.Button([icone("delete"), "Excluir"],
                                   id={"tipo": "excluir-backup", "nome": b["nome"]},
                                   className="btn btn-sm btn-danger"),
                    ],
                    className="left",
                ),
            ]
        )
        for b in backups
    ]
    return html.Div([_tabela(["Arquivo", "Tamanho", "Ações"], linhas),
                     _confirmacao_de_restauracao()])


def _confirmacao_de_restauracao():
    """Restoring replaces the whole database, so it asks for the name typed out.

    The service checks the confirmation again, so this field is the explanation,
    not the protection. Visually it is a destructive block, distinct from the
    ordinary actions above it.
    """
    return html.Div(
        [
            html.Div(icone("warning"), className="notice-icon"),
            html.Div(
                [
                    html.P("Restauração — ação destrutiva", className="notice-title"),
                    html.P(
                        "Restaurar substitui todo o conteúdo do banco. Digite o nome "
                        "do backup para confirmar; um dump do estado atual é gerado "
                        "antes de qualquer escrita.",
                        className="notice-text",
                    ),
                    dbc.Input(id="confirmacao-restauracao",
                              placeholder="nome do backup",
                              style=STYLE_INPUT, className="mt-sm"),
                ]
            ),
        ],
        className="notice danger mt-md",
    )


# -------------------------------------------------------------------- Índices


def tela_indices(cobertura: dict):
    """What the índices tables currently cover.

    The ΔP is only as current as these two series, and the user is the one who
    feeds them, so the coverage is shown rather than left to be discovered by a
    failed export.
    """
    anp = cobertura.get("anp") or {}
    igp = cobertura.get("igp_di") or {}
    regioes_cobertas = set(cobertura.get("regioes") or [])

    return html.Div(
        [
            html.Div(
                [
                    _cartao_kpi("ANP — preços semanais", str(anp.get("registros", 0)),
                                f"{anp.get('de') or '—'} até {anp.get('ate') or '—'}",
                                "local_gas_station"),
                    _cartao_kpi("Regiões cotadas", str(len(regioes_cobertas)),
                                ", ".join(sorted(regioes_cobertas)) or "—", "public"),
                    _cartao_kpi("IGP-DI — índices mensais", str(igp.get("registros", 0)),
                                f"{igp.get('de') or '—'} até {igp.get('ate') or '—'}",
                                "monitoring"),
                ],
                className="card-grid",
            ),
            html.Div(
                [
                    html.Span(
                        [icone("check_circle" if regiao in regioes_cobertas else "warning"),
                         regiao],
                        className="badge badge-ok" if regiao in regioes_cobertas else "badge badge-warn",
                    )
                    for regiao in REGIOES
                ],
                className="batch-actions-group mt-md",
            ),
            _painel(
                "Acrescentar preço semanal da ANP",
                "add_chart",
                _formulario_anp(),
                subtitulo="O preço do mês é o da vigência que contém o dia 15.",
                rodape=html.Div(id="aviso-anp"),
            ),
            _painel(
                "Acrescentar índice mensal",
                "timeline",
                _formulario_mensal(),
                subtitulo="O IGP-DI entra no ΔP das emulsões, com peso de 25%.",
                rodape=html.Div(id="aviso-mensal"),
            ),
        ]
    )


def _campo(rotulo: str, controle):
    return html.Div(
        [html.Span(rotulo, className="field-label"), controle], className="field"
    )


def _formulario_anp():
    """Entry of one weekly ANP price, per region.

    One region at a time: the published table has a column per region, but a user
    typically adds the region their contract uses.
    """
    return html.Div(
        [
            _campo("Início da vigência",
                   dcc.DatePickerSingle(id="anp-inicio", display_format="DD/MM/YYYY",
                                        placeholder="Início")),
            _campo("Fim da vigência",
                   dcc.DatePickerSingle(id="anp-fim", display_format="DD/MM/YYYY",
                                        placeholder="Fim")),
            _campo("Região",
                   dcc.Dropdown(id="anp-regiao",
                                options=[{"label": r, "value": r} for r in REGIOES],
                                placeholder="Região", className="dash-dropdown",
                                style={"minWidth": "180px"})),
            _campo("Preço (R$/kg)",
                   dbc.Input(id="anp-preco", type="number", step=0.0001,
                             placeholder="0,0000",
                             style={**STYLE_INPUT, "width": "140px"})),
            dbc.Button([icone("save"), "Gravar"], id="gravar-anp",
                       className="btn btn-primary"),
        ],
        className="inline-form",
    )


def _formulario_mensal():
    return html.Div(
        [
            _campo("Índice",
                   dbc.Input(id="mensal-indice", value="IGP - DI",
                             style={**STYLE_INPUT, "width": "180px"})),
            _campo("Mês de referência",
                   dcc.DatePickerSingle(id="mensal-mes", display_format="MM/YYYY",
                                        placeholder="Mês")),
            _campo("Valor",
                   dbc.Input(id="mensal-valor", type="number", step=0.0001,
                             placeholder="0,0000",
                             style={**STYLE_INPUT, "width": "140px"})),
            dbc.Button([icone("save"), "Gravar"], id="gravar-mensal",
                       className="btn btn-primary"),
        ],
        className="inline-form",
    )
