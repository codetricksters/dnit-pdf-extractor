"""Modelos de resposta e de entrada da API.

``Decimal`` sai como string no JSON (Pydantic 2): o usuário confere esses números
contra a planilha, e um float binário não é o valor que está no banco.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

Familia = Literal["CAP", "EMULSOES"]

CODIGO_SERVICO = r"^\d{4,}$"


class ContratoResumo(BaseModel):
    id: int
    numero: str
    data_base: date | None
    contratada: str | None
    rodovia: str | None
    regioes: dict[str, str]
    itens: int
    medicoes: int
    primeiro_mes: date | None
    ultimo_mes: date | None
    faltantes: list[str]


class Contrato(BaseModel):
    id: int
    numero: str
    numero_processo: str | None
    data_base: date | None
    edital: str | None
    rodovia: str | None
    trecho: str | None
    subtrecho: str | None
    segmento: str | None
    extensao: Decimal | None
    contratada: str | None
    regioes: dict[str, str]
    faltantes: list[str]
    atualizado_em: datetime


class ContratoPatch(BaseModel):
    """Só os campos enviados são gravados (``exclude_unset``)."""

    model_config = ConfigDict(extra="forbid")

    edital: str | None = None
    rodovia: str | None = None
    trecho: str | None = None
    subtrecho: str | None = None
    segmento: str | None = None
    extensao: Decimal | str | None = None
    contratada: str | None = None
    data_base: str | None = None
    regioes: dict[str, str] | None = None


class Produto(BaseModel):
    id: int
    descricao_export: str
    familia: Familia
    ordem: int
    codigos: int


class ProdutoNovo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descricao_export: str
    familia: Familia
    ordem: int = 0


class ProdutoPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descricao_export: str | None = None
    familia: Familia | None = None
    ordem: int | None = None


class Codigo(BaseModel):
    codigo: str
    descricao_pdf: str | None
    contratos: int
    ocorrencias: int
    produto_id: int | None
    descricao_export: str | None
    familia: Familia | None


class CodigoAssociado(BaseModel):
    codigo_servico: str
    descricao_pdf: str | None
    produto_id: int
    descricao_export: str
    familia: Familia


class Associacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produto_id: int
