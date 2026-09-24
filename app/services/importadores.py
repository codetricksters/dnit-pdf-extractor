"""Leitura dos arquivos de índices: o .xls semanal da ANP e o template do IGP-DI.

Módulo puro: recebe bytes, devolve registros validados ou ``ArquivoInvalido``
com a lista de erros por linha. Não toca o banco — a comparação e a gravação são
de ``importacao``. Seed, API e testes passam por aqui, então o arquivo aceito
pelo seed é exatamente o aceito pela tela.
"""

import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

import openpyxl
import xlrd
from openpyxl.styles import Font

from .delta_p import BASE_IGP_DI, INDICE_IGP_DI, inicio_do_mes

# Layout do arquivo "precos-medios-ponderados-semanais-2013.xls" da ANP. Linhas
# em base 0, como o xlrd as devolve; as mensagens usam a numeração do Excel.
ABA_ANP = "Preços Produtor e Importador"
LINHA_CABECALHO_ANP = 7
LINHA_REGIOES_ANP = 8
PRIMEIRA_LINHA_ANP = 9
REGIOES_ANP = ("Norte", "Nordeste", "Centro-Oeste", "Sul", "Sudeste", "Brasil")
COL_PRIMEIRA_REGIAO = 3
EPOCA_EXCEL = date(1899, 12, 30)
CASAS_ANP = Decimal("0.00001")
SEM_COTACAO = "***"
LAYOUT_ANP_ERRADO = "Este não é o arquivo de preços semanais da ANP: {motivo}."

ABA_IGP = "IGP-DI"
ABA_INSTRUCOES = "Instruções"
CABECALHO_IGP = ("Mês", "Valor")
INSTRUCOES_IGP = (
    "Template de importação do IGP-DI (FGV).",
    "",
    f"Aba '{ABA_IGP}': uma linha por mês, a partir da linha 2.",
    "Coluna A (Mês): data (qualquer dia do mês) ou texto MM/AAAA.",
    "Coluna B (Valor): o número-índice publicado pela FGV, maior que zero.",
    f"Base do índice: {BASE_IGP_DI}.",
    "Linhas em branco são ignoradas; um mês repetido recusa o arquivo.",
    "Qualquer linha inválida recusa o arquivo inteiro: nada é gravado.",
)

MAX_ERROS = 50
_MES_TEXTO = re.compile(r"^\s*(\d{1,2})/(\d{4})\s*$")


class ArquivoInvalido(ValueError):
    """Arquivo recusado; ``erros`` lista os problemas linha a linha."""

    def __init__(self, mensagem: str, erros: list[str] | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.erros = list(erros or [])


@dataclass
class Leitura:
    registros: list[dict]
    avisos: list[str] = field(default_factory=list)


def limitar(erros: list[str]) -> list[str]:
    """No máximo ``MAX_ERROS`` linhas de erro, e quantas ficaram de fora."""
    if len(erros) <= MAX_ERROS:
        return erros
    return erros[:MAX_ERROS] + [f"… e mais {len(erros) - MAX_ERROS} erro(s)."]


def _recusar(erros: list[str]) -> ArquivoInvalido:
    return ArquivoInvalido(
        f"O arquivo tem {len(erros)} erro(s); nada foi gravado.", limitar(erros)
    )


def _semana(inicio: date, fim: date) -> str:
    return f"{inicio:%d/%m/%Y}–{fim:%d/%m/%Y}"


# --- ANP -----------------------------------------------------------------------

def _layout(motivo: str) -> ArquivoInvalido:
    return ArquivoInvalido(LAYOUT_ANP_ERRADO.format(motivo=motivo))


def _textos(linha, tamanho: int = 10) -> list[str]:
    return [str(c).strip() for c in list(linha) + [""] * tamanho][:tamanho]


def _conferir_layout_anp(linhas: list[list]) -> None:
    if len(linhas) <= PRIMEIRA_LINHA_ANP:
        raise _layout("o arquivo tem menos linhas que o cabeçalho da ANP")
    cab = _textos(linhas[LINHA_CABECALHO_ANP])
    if (cab[0], cab[1], cab[3], cab[8]) != ("Produto", "Período", "Região", "Brasil"):
        raise _layout("a linha 8 não traz as colunas Produto, Período, Região e Brasil")
    regioes = _textos(linhas[LINHA_REGIOES_ANP])
    if tuple(regioes[COL_PRIMEIRA_REGIAO:COL_PRIMEIRA_REGIAO + 5]) != REGIOES_ANP[:5]:
        raise _layout("a linha 9 não lista Norte, Nordeste, Centro-Oeste, Sul e Sudeste")


def _serial(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor > 0


def _data(serial: float) -> date:
    return EPOCA_EXCEL + timedelta(days=int(serial))


def _preco(valor) -> Decimal | None:
    if isinstance(valor, str):
        texto = valor.strip()
        if texto in ("", SEM_COTACAO):
            return None
        raise ValueError(f"preço {texto!r} não é um número")
    preco = Decimal(str(valor))
    if preco <= 0:
        raise ValueError(f"preço deve ser maior que zero ({preco})")
    return preco.quantize(CASAS_ANP)


def ler_linhas_anp(linhas: list[list]) -> Leitura:
    """Registros semanais de uma aba ANP já lida como lista de linhas.

    Separado de ``ler_anp`` para que os testes montem abas mínimas sem precisar
    escrever um .xls (o xlwt não é dependência).
    """
    _conferir_layout_anp(linhas)
    registros: list[dict] = []
    erros: list[str] = []
    inicios: dict[str, Counter] = defaultdict(Counter)

    for i in range(PRIMEIRA_LINHA_ANP, len(linhas)):
        linha = list(linhas[i]) + [""] * 10
        produto = str(linha[0]).strip()
        # O rodapé ("Notas: …") tem texto na coluna A mas nenhuma data serial.
        if not produto or not (_serial(linha[1]) and _serial(linha[2])):
            break
        numero = i + 1
        inicio, fim = _data(linha[1]), _data(linha[2])
        if fim < inicio:
            erros.append(
                f"linha {numero}: a semana termina ({fim:%d/%m/%Y}) antes de "
                f"começar ({inicio:%d/%m/%Y})."
            )
            continue
        inicios[produto][inicio] += 1
        for k, regiao in enumerate(REGIOES_ANP):
            try:
                preco = _preco(linha[COL_PRIMEIRA_REGIAO + k])
            except ValueError as e:
                erros.append(f"linha {numero}, {regiao}: {e}.")
                continue
            registros.append(
                {
                    "produto": produto,
                    "vigencia_inicio": inicio,
                    "vigencia_fim": fim,
                    "regiao": regiao,
                    "preco": preco,
                }
            )

    if erros:
        raise _recusar(erros)

    # Semanas repetidas num produto são séries distintas publicadas sob o mesmo
    # nome (no arquivo oficial, só o GLP). Não há como escolher uma: o produto
    # fica de fora, e os demais — entre eles o CAP — são importados.
    avisos = []
    excluidos = set()
    for produto, contagem in inicios.items():
        repetidas = sum(1 for n in contagem.values() if n > 1)
        if repetidas:
            excluidos.add(produto)
            avisos.append(
                f"{produto}: {repetidas} semana(s) aparecem mais de uma vez no "
                "arquivo — séries distintas sob o mesmo nome; o produto não foi "
                "importado."
            )
    registros = [r for r in registros if r["produto"] not in excluidos]
    if not registros:
        raise ArquivoInvalido("O arquivo não tem nenhuma semana de preços.")
    return Leitura(registros, avisos)


def ler_anp(conteudo: bytes) -> Leitura:
    try:
        livro = xlrd.open_workbook(file_contents=conteudo)
    except Exception as e:
        raise _layout("não é uma planilha .xls legível") from e
    if ABA_ANP not in livro.sheet_names():
        raise _layout(f"falta a aba '{ABA_ANP}'")
    aba = livro.sheet_by_name(ABA_ANP)
    return ler_linhas_anp([aba.row_values(i) for i in range(aba.nrows)])


# Uma entrada de sobreposição carrega de onde ela vem, porque a mensagem (e se
# ela é reportada) depende disso: duas semanas cadastradas que já se sobrepõem
# não são deste import (o banco já as impede); uma semana manual preservada
# ainda precisa aparecer, porque é o único jeito de o usuário saber que ela vai
# colidir com o que está para ser gravado.
TAG_ARQUIVO = "arquivo"
TAG_EXISTENTE = "existente"
TAG_MANUAL = "manual"


def _mensagem_sobreposicao(produto: str, regiao: str, anterior: tuple, atual: tuple) -> str | None:
    a_ini, a_fim, a_tag = anterior
    ini, fim, tag = atual
    if TAG_ARQUIVO not in (a_tag, tag):
        return None  # nenhuma das duas é do arquivo: o banco já impede isso.
    if TAG_MANUAL in (a_tag, tag):
        manual_ini, manual_fim = (a_ini, a_fim) if a_tag == TAG_MANUAL else (ini, fim)
        arquivo_ini, arquivo_fim = (ini, fim) if tag == TAG_ARQUIVO else (a_ini, a_fim)
        texto = (
            f"a semana {_semana(arquivo_ini, arquivo_fim)} do arquivo se sobrepõe à "
            f"semana {_semana(manual_ini, manual_fim)}, que tem valor cadastrado "
            "manualmente e seria preservada. Para substituí-la, importe novamente "
            "com sobrescrever_manuais=true."
        )
    elif tag == TAG_ARQUIVO and a_tag == TAG_ARQUIVO:
        texto = (f"a semana {_semana(ini, fim)} se sobrepõe à semana "
                 f"{_semana(a_ini, a_fim)} do próprio arquivo.")
    elif tag == TAG_ARQUIVO:
        texto = (f"a semana {_semana(ini, fim)} se sobrepõe à semana "
                 f"{_semana(a_ini, a_fim)} já cadastrada.")
    else:
        texto = (f"a semana {_semana(a_ini, a_fim)} do arquivo se sobrepõe "
                 f"à semana {_semana(ini, fim)} já cadastrada.")
    return f"{produto}, {regiao}: {texto}"


def sobreposicoes_marcadas(entradas: list[tuple]) -> list[str]:
    """Sobreposições entre semanas já rotuladas (``TAG_ARQUIVO``/``TAG_EXISTENTE``/
    ``TAG_MANUAL``) de um mesmo produto e região.

    *entradas* é uma lista de ``(produto, regiao, inicio, fim, tag)``, no máximo
    uma por ``(produto, regiao, inicio)`` — é quem chama que decide o que uma
    mesma semana representa quando há mais de uma fonte para ela. Usada por
    ``sobreposicoes`` (verificação preliminar) e por ``importacao`` (verificação
    contra o estado que o plano de fato vai gravar, que pode preservar um valor
    manual em vez de sobrescrevê-lo).
    """
    semanas: dict[tuple[str, str], dict[date, tuple[date, str]]] = defaultdict(dict)
    for produto, regiao, inicio, fim, tag in entradas:
        semanas[(produto, regiao)][inicio] = (fim, tag)

    erros = []
    for (produto, regiao), por_inicio in semanas.items():
        anterior: tuple[date, date, str] | None = None  # a de maior fim até aqui
        for inicio in sorted(por_inicio):
            fim, tag = por_inicio[inicio]
            if anterior and inicio <= anterior[1]:
                erro = _mensagem_sobreposicao(produto, regiao, anterior, (inicio, fim, tag))
                if erro:
                    erros.append(erro)
            if anterior is None or fim > anterior[1]:
                anterior = (inicio, fim, tag)
    return erros



# --- IGP-DI ----------------------------------------------------------------------

def _mes(valor) -> date | None:
    # datetime antes de date: datetime é subclasse de date.
    if isinstance(valor, datetime):
        return inicio_do_mes(valor.date())
    if isinstance(valor, date):
        return inicio_do_mes(valor)
    if isinstance(valor, str):
        m = _MES_TEXTO.match(valor)
        if m and 1 <= int(m.group(1)) <= 12:
            return date(int(m.group(2)), int(m.group(1)), 1)
    return None


def _valor_igp(valor) -> Decimal | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float, Decimal)):
        return None
    numero = Decimal(str(valor))
    return numero if numero > 0 else None


def _vazia(celulas) -> bool:
    return all(c is None or (isinstance(c, str) and not c.strip()) for c in celulas)


def ler_linhas_igp_di(linhas: list[list]) -> Leitura:
    cabecalho = [str(c or "").strip().casefold() for c in (list(linhas[0]) if linhas else [])[:2]]
    if cabecalho != [c.casefold() for c in CABECALHO_IGP]:
        raise ArquivoInvalido(
            f"A aba '{ABA_IGP}' deve ter Mês e Valor nas colunas A e B da linha 1."
        )
    registros: list[dict] = []
    erros: list[str] = []
    vistos: dict[date, int] = {}
    for numero, linha in enumerate(linhas[1:], start=2):
        bruto_mes, bruto_valor = (list(linha) + [None, None])[:2]
        if _vazia((bruto_mes, bruto_valor)):
            continue
        mes = _mes(bruto_mes)
        if mes is None:
            erros.append(f"linha {numero}: mês {bruto_mes!r} ilegível; use uma data ou MM/AAAA.")
            continue
        valor = _valor_igp(bruto_valor)
        if valor is None:
            erros.append(f"linha {numero}: valor {bruto_valor!r} não é um número maior que zero.")
            continue
        if mes in vistos:
            erros.append(f"linha {numero}: o mês {mes:%m/%Y} já aparece na linha {vistos[mes]}.")
            continue
        vistos[mes] = numero
        registros.append(
            {"indice": INDICE_IGP_DI, "mes_ref": mes, "valor": valor, "base_label": BASE_IGP_DI}
        )
    if erros:
        raise _recusar(erros)
    if not registros:
        raise ArquivoInvalido("O arquivo não tem nenhum mês preenchido.")
    return Leitura(registros)


def ler_igp_di(conteudo: bytes) -> Leitura:
    try:
        livro = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as e:
        raise ArquivoInvalido("O arquivo não é uma planilha .xlsx legível.") from e
    try:
        if ABA_IGP not in livro.sheetnames:
            raise ArquivoInvalido(
                f"O arquivo não tem a aba '{ABA_IGP}'. Use o template de importação do IGP-DI."
            )
        linhas = [list(r) for r in livro[ABA_IGP].iter_rows(values_only=True)]
    finally:
        livro.close()
    return ler_linhas_igp_di(linhas)


def gerar_template_igp_di(registros: list[dict]) -> bytes:
    """O template de importação, preenchido com *registros* (``mes_ref``, ``valor``).

    O mesmo arquivo serve de exportação: reimportá-lo não altera nada.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = ABA_IGP
    ws.append(list(CABECALHO_IGP))
    for celula in ws[1]:
        celula.font = Font(bold=True)
    for r in sorted(registros, key=lambda r: r["mes_ref"]):
        ws.append([r["mes_ref"], float(r["valor"])])
        ws.cell(ws.max_row, 1).number_format = "mmm/yyyy"
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 14

    instrucoes = wb.create_sheet(ABA_INSTRUCOES)
    for texto in INSTRUCOES_IGP:
        instrucoes.append([texto])
    instrucoes.column_dimensions["A"].width = 90

    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()
