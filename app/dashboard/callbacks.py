"""Dashboard wiring.

Only callbacks live here: they read the database, hand plain data to ``views.py``
and write back through the service modules. Nothing is computed in this file —
ΔP, grouping and the REF columns belong to the services, so the screen and the
exported spreadsheet cannot disagree.

Every write bumps the ``recarregar`` store, which is what makes the screens
re-render from the database rather than from what was on screen before the click.
"""

import base64
import binascii
from urllib.parse import parse_qs

from dash import ALL, Input, Output, State, callback_context, html, no_update
import dash_bootstrap_components as dbc

from ..services import (
    backup,
    catalogo,
    contratos_repo,
    indices_repo,
    progresso,
    template_repo,
)
from ..services.xlsx_drawings import TemplateInvalido
from . import layout, views
from .data_loader import DEFAULT_LUCRO, compute_ref_columns, load_reequilibrio_data


def _aviso(mensagem: str, cor: str = "success"):
    return dbc.Alert(mensagem, color=cor, dismissable=True)


def _disparado() -> dict | None:
    """The id dict of the component that fired, for the pattern-matching ids."""
    acionado = callback_context.triggered_id
    return acionado if isinstance(acionado, dict) else None


def _decodificar(conteudo: str) -> bytes:
    """Bytes out of a dcc.Upload payload ("data:<mime>;base64,<...>")."""
    try:
        return base64.b64decode(conteudo.split(",", 1)[1])
    except (IndexError, binascii.Error) as e:
        raise ValueError("Não foi possível ler o arquivo enviado.") from e


def register_callbacks(app):
    @app.callback(
        Output("contrato", "options"),
        Output("contrato", "value"),
        Input("recarregar", "data"),
        State("contrato", "value"),
    )
    def carregar_contratos(_recarregar, atual):
        contratos = contratos_repo.listar()
        opcoes = [
            {
                "label": f"{c['numero']} — {c['itens']} itens",
                "value": c["numero"],
            }
            for c in contratos
        ]
        numeros = [c["numero"] for c in contratos]
        # Selecting the only contract saves a click in the common case.
        escolhido = atual if atual in numeros else (numeros[0] if len(numeros) == 1 else atual)
        return opcoes, escolhido

    @app.callback(
        Output("aba", "data"),
        Input({"tipo": "nav-aba", "aba": ALL}, "n_clicks"),
        Input("url", "search"),
        State("aba", "data"),
    )
    def escolher_aba(_cliques, busca, atual):
        """Which screen is showing: a sidebar click, or ``?aba=…`` on the URL.

        The deep link matters because the upload page and the step trail point
        straight at the screen that resolves each pendência.
        """
        acionado = _disparado()
        if acionado:
            return acionado["aba"]
        pedido = parse_qs((busca or "").lstrip("?")).get("aba", [None])[0]
        validas = {aba for aba, _ in layout.ABAS}
        return pedido if pedido in validas else atual

    @app.callback(
        Output({"tipo": "nav-aba", "aba": ALL}, "className"),
        Input("aba", "data"),
        State({"tipo": "nav-aba", "aba": ALL}, "id"),
    )
    def marcar_navegacao(aba, ids):
        return [
            "nav-item active" if i["aba"] == aba else "nav-item" for i in ids
        ]

    @app.callback(
        Output("trilha", "children"),
        Output("painel-contrato", "children"),
        Output("rodape-itens", "children"),
        Input("contrato", "value"),
        Input("recarregar", "data"),
    )
    def desenhar_casca(numero, _recarregar):
        resumo = progresso.resumo(numero)
        return layout.trilha(resumo), layout.painel_contrato(resumo), resumo.medicoes

    @app.callback(
        Output("titulo-pagina", "children"),
        Output("subtitulo-pagina", "children"),
        Output("crumb-atual", "children"),
        Input("aba", "data"),
    )
    def desenhar_cabecalho(aba):
        titulo, subtitulo = layout.TITULOS[aba]
        return titulo, subtitulo, titulo

    @app.callback(
        Output("conteudo", "children"),
        Input("aba", "data"),
        Input("contrato", "value"),
        Input("recarregar", "data"),
    )
    def desenhar(aba, numero, _recarregar):
        contrato = contratos_repo.buscar(numero) if numero else None

        if aba == "cadastro":
            return views.tela_cadastro(contrato)
        if aba == "pendencias":
            return views.tela_pendencias(
                catalogo.listar_pendencias(), catalogo.listar_produtos()
            )
        if aba == "indices":
            return views.tela_indices(indices_repo.cobertura())
        if aba == "administracao":
            return views.tela_administracao(template_repo.listar(), backup.listar())

        if contrato is None:
            return views.tela_reequilibrio(None, {}, [])
        tabelas, pendencias = load_reequilibrio_data(numero)
        return views.tela_reequilibrio(contrato, tabelas, pendencias)

    @app.callback(
        Output({"tipo": "tabela-produto", "indice": ALL}, "data"),
        Input("lucro", "value"),
        State("contrato", "value"),
    )
    def recalcular_lucro(lucro, numero):
        """Recompute the on-screen tables for a different lucro.

        Only the derived columns change: ΔP comes from the índices and is not
        something the user types any more.
        """
        if not numero:
            return no_update
        taxa = float(lucro) if lucro is not None else DEFAULT_LUCRO
        tabelas, _ = load_reequilibrio_data(numero)
        return [
            compute_ref_columns(df, taxa).to_dict("records")
            for df in tabelas.values()
        ]

    @app.callback(
        Output("aviso-cadastro", "children"),
        Output("recarregar", "data", allow_duplicate=True),
        Input("salvar-cadastro", "n_clicks"),
        State("contrato", "value"),
        State({"tipo": "campo-cadastro", "campo": ALL}, "value"),
        State({"tipo": "campo-cadastro", "campo": ALL}, "id"),
        State({"tipo": "regiao-familia", "familia": ALL}, "value"),
        State({"tipo": "regiao-familia", "familia": ALL}, "id"),
        State("recarregar", "data"),
        prevent_initial_call=True,
    )
    def salvar_cadastro(_clicks, numero, valores, ids, regioes, ids_regiao, recarregar):
        if not numero:
            return _aviso("Selecione um contrato.", "warning"), no_update
        dados = {
            identificador["campo"]: (valor or None)
            for identificador, valor in zip(ids, valores)
        }
        contratos_repo.salvar_cadastro(numero, dados)
        for identificador, regiao in zip(ids_regiao, regioes):
            if regiao:
                contratos_repo.definir_regiao(numero, identificador["familia"], regiao)
        return _aviso("Cadastro salvo."), recarregar + 1

    @app.callback(
        Output("aviso-pendencias", "children"),
        Output("recarregar", "data", allow_duplicate=True),
        Input({"tipo": "confirmar-codigo", "codigo": ALL}, "n_clicks"),
        State({"tipo": "produto-pendencia", "codigo": ALL}, "value"),
        State({"tipo": "produto-pendencia", "codigo": ALL}, "id"),
        State("recarregar", "data"),
        prevent_initial_call=True,
    )
    def confirmar_codigo(_clicks, produtos, ids, recarregar):
        acionado = _disparado()
        if acionado is None:
            return no_update, no_update
        codigo = acionado["codigo"]
        produto_id = next(
            (p for p, i in zip(produtos, ids) if i["codigo"] == codigo), None
        )
        if not produto_id:
            return _aviso("Escolha o produto antes de confirmar.", "warning"), no_update
        catalogo.registrar_codigo(codigo, produto_id, confirmado=True)
        return _aviso(f"Código {codigo} confirmado."), recarregar + 1

    @app.callback(
        Output("aviso-anp", "children"),
        Output("recarregar", "data", allow_duplicate=True),
        Input("gravar-anp", "n_clicks"),
        State("anp-inicio", "date"),
        State("anp-fim", "date"),
        State("anp-regiao", "value"),
        State("anp-preco", "value"),
        State("recarregar", "data"),
        prevent_initial_call=True,
    )
    def gravar_anp(_clicks, inicio, fim, regiao, preco, recarregar):
        if not (inicio and fim and regiao and preco is not None):
            return _aviso("Preencha a vigência, a região e o preço.", "warning"), no_update
        indices_repo.gravar_precos_anp(
            [
                {
                    "produto": indices_repo.ANP_PRODUTO_CAP,
                    "vigencia_inicio": inicio,
                    "vigencia_fim": fim,
                    "regiao": regiao,
                    "preco": preco,
                }
            ]
        )
        return _aviso("Preço gravado."), recarregar + 1

    @app.callback(
        Output("aviso-mensal", "children"),
        Output("recarregar", "data", allow_duplicate=True),
        Input("gravar-mensal", "n_clicks"),
        State("mensal-indice", "value"),
        State("mensal-mes", "date"),
        State("mensal-valor", "value"),
        State("recarregar", "data"),
        prevent_initial_call=True,
    )
    def gravar_mensal(_clicks, indice, mes, valor, recarregar):
        if not (indice and mes and valor is not None):
            return _aviso("Preencha o índice, o mês e o valor.", "warning"), no_update
        indices_repo.gravar_indices_mensais(
            [{"indice": indice, "mes_ref": mes, "valor": valor}]
        )
        return _aviso("Índice gravado."), recarregar + 1

    @app.callback(
        Output("aviso-template", "children"),
        Output("recarregar", "data", allow_duplicate=True),
        Input("enviar-template", "contents"),
        State("enviar-template", "filename"),
        State("recarregar", "data"),
        prevent_initial_call=True,
    )
    def enviar_template(conteudo, nome, recarregar):
        if not conteudo:
            return no_update, no_update
        try:
            template_repo.salvar(nome or "template.xlsx", _decodificar(conteudo))
        except (TemplateInvalido, ValueError) as e:
            # The service's message names what is wrong with the file, which is
            # the whole point of validating it.
            return _aviso(str(e), "danger"), no_update
        return _aviso(f"Template '{nome}' enviado e ativado."), recarregar + 1

    @app.callback(
        Output("aviso-template", "children", allow_duplicate=True),
        Output("recarregar", "data", allow_duplicate=True),
        Input({"tipo": "ativar-template", "id": ALL}, "n_clicks"),
        Input({"tipo": "excluir-template", "id": ALL}, "n_clicks"),
        State("recarregar", "data"),
        prevent_initial_call=True,
    )
    def gerir_template(_ativar, _excluir, recarregar):
        acionado = _disparado()
        if acionado is None:
            return no_update, no_update
        try:
            if acionado["tipo"] == "ativar-template":
                template_repo.ativar(acionado["id"])
                mensagem = "Template ativado."
            else:
                template_repo.excluir(acionado["id"])
                mensagem = "Template excluído."
        except TemplateInvalido as e:
            return _aviso(str(e), "danger"), no_update
        return _aviso(mensagem), recarregar + 1

    @app.callback(
        Output("aviso-backup", "children"),
        Output("recarregar", "data", allow_duplicate=True),
        Input("gerar-backup", "n_clicks"),
        State("recarregar", "data"),
        prevent_initial_call=True,
    )
    def gerar_backup(_clicks, recarregar):
        try:
            caminho = backup.gerar("manual")
        except backup.BackupIndisponivel as e:
            return _aviso(str(e), "danger"), no_update
        return _aviso(f"Backup '{caminho.name}' gerado."), recarregar + 1

    @app.callback(
        Output("aviso-backup", "children", allow_duplicate=True),
        Output("recarregar", "data", allow_duplicate=True),
        Input("enviar-backup", "contents"),
        State("enviar-backup", "filename"),
        State("recarregar", "data"),
        prevent_initial_call=True,
    )
    def enviar_backup(conteudo, nome, recarregar):
        if not conteudo:
            return no_update, no_update
        try:
            caminho = backup.receber_envio(nome or "backup.dump", _decodificar(conteudo))
        except (backup.BackupIndisponivel, ValueError) as e:
            return _aviso(str(e), "danger"), no_update
        return _aviso(f"Backup '{caminho.name}' recebido e validado."), recarregar + 1

    @app.callback(
        Output("aviso-backup", "children", allow_duplicate=True),
        Output("recarregar", "data", allow_duplicate=True),
        Input({"tipo": "restaurar-backup", "nome": ALL}, "n_clicks"),
        Input({"tipo": "excluir-backup", "nome": ALL}, "n_clicks"),
        State("confirmacao-restauracao", "value"),
        State("recarregar", "data"),
        prevent_initial_call=True,
    )
    def gerir_backup(_restaurar, _excluir, confirmacao, recarregar):
        acionado = _disparado()
        if acionado is None:
            return no_update, no_update
        nome = acionado["nome"]
        try:
            if acionado["tipo"] == "restaurar-backup":
                resultado = backup.restaurar(nome, confirmacao or "")
                mensagem = (
                    f"Banco restaurado a partir de '{nome}'. O estado anterior "
                    f"ficou salvo em '{resultado['seguranca']}'."
                )
            else:
                backup.excluir(nome)
                mensagem = f"Backup '{nome}' excluído."
        except backup.BackupIndisponivel as e:
            return _aviso(str(e), "danger"), no_update
        return _aviso(mensagem, "warning"), recarregar + 1
