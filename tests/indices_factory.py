"""Construtores de índices para os testes: registros e planilhas ANP mínimas."""

from datetime import date, timedelta
from decimal import Decimal

from app.services.delta_p import ANP_PRODUTO_CAP, BASE_IGP_DI, INDICE_IGP_DI

EPOCA_EXCEL = date(1899, 12, 30)


def semana(inicio: date, preco, *, regiao="Nordeste", produto=ANP_PRODUTO_CAP, dias=6) -> dict:
    return {
        "produto": produto,
        "vigencia_inicio": inicio,
        "vigencia_fim": inicio + timedelta(days=dias),
        "regiao": regiao,
        "preco": None if preco is None else Decimal(str(preco)),
    }


def mes_igp(mes: date, valor) -> dict:
    return {
        "indice": INDICE_IGP_DI,
        "mes_ref": mes,
        "valor": Decimal(str(valor)),
        "base_label": BASE_IGP_DI,
    }


def serial(d: date) -> float:
    """Data como o xlrd a devolve: número serial do Excel."""
    return float((d - EPOCA_EXCEL).days)


def linha_anp(produto: str, inicio: date, precos: list, dias: int = 6) -> list:
    """Uma linha de dados da aba ANP: produto, início, fim e seis preços."""
    return [produto, serial(inicio), serial(inicio + timedelta(days=dias)), *precos]


def linhas_anp(dados: list[list]) -> list[list]:
    """A aba ANP como lista de linhas, com o cabeçalho e o rodapé do arquivo oficial."""
    cabecalho = [
        ["Produto", "Período", "", "Região", "", "", "", "", "Brasil", ""],
        ["", "(A partir de 2013)", "", "Norte", "Nordeste", "Centro-Oeste", "Sul", "Sudeste", "", ""],
    ]
    return (
        [[""] * 10 for _ in range(7)]
        + cabecalho
        + [list(linha) for linha in dados]
        + [["Notas: não inclui ICMS.", ""]]
    )
