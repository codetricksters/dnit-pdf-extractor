"""Where a contract stands on the way to the spreadsheet.

The interface proposed in ``DESIGN.md`` shows a six-step trail in the header of
every screen, in both halves of the application. The state of that trail is not
decoration: it answers the question the user actually has — why the export is
still blocked — so it is computed from the database, never hardcoded in the
markup.

Deliberately cheap: everything here is a count or a field test. Steps 5 and 6
depend on the ΔP, which costs a full calculation, so they are reported as
reachable once steps 1 to 4 are done rather than being computed twice (the
reequilíbrio screen and the export do compute it, and they report the real
missing índices).
"""

from dataclasses import dataclass, field

from ..db import acquire_sync
from . import contratos_repo
from .delta_p import FAMILIAS

# The status names are also the CSS suffixes (``step-done``, …), so the template
# and the Dash shell render the same trail from the same vocabulary.
CONCLUIDA = "done"
ATUAL = "current"
PENDENTE = "pending"
BLOQUEADA = "blocked"

ICONE = {
    CONCLUIDA: "check_circle",
    ATUAL: "pending",
    PENDENTE: "radio_button_unchecked",
    BLOQUEADA: "lock",
}


@dataclass
class Etapa:
    numero: int
    rotulo: str
    status: str
    destino: str
    detalhe: str = ""

    @property
    def icone(self) -> str:
        return ICONE[self.status]


@dataclass
class Resumo:
    """Everything the shell needs: the trail, the active contract, the counters."""

    contrato: dict | None = None
    etapas: list[Etapa] = field(default_factory=list)
    contratos: int = 0
    medicoes: int = 0
    itens: int = 0
    pendencias: int = 0
    faltantes: list[str] = field(default_factory=list)

    @property
    def liberado(self) -> bool:
        """True when nothing this module can see blocks the export."""
        return bool(self.contrato) and not self.faltantes and not self.pendencias

    @property
    def rotulo_contrato(self) -> str:
        if not self.contrato:
            return "Nenhum contrato selecionado"
        return self.contrato["numero"]

    @property
    def descricao_contrato(self) -> str:
        if not self.contrato:
            return "Envie os PDFs das medições para começar"
        partes = [
            self.contrato.get("rodovia"),
            self.contrato.get("contratada"),
        ]
        return " — ".join(p for p in partes if p) or "Cadastro incompleto"


def _contagens() -> dict:
    with acquire_sync() as conn:
        cur = conn.execute(
            "SELECT (SELECT COUNT(*) FROM contrato) AS contratos, "
            "       (SELECT COUNT(DISTINCT source_file) FROM medicao_item) AS medicoes, "
            "       (SELECT COUNT(*) FROM medicao_item) AS itens"
        )
        return dict(cur.fetchone())


def _etapas(contrato: dict | None, itens: int, pendencias: int, faltantes: list[str]) -> list[Etapa]:
    cadastro_ok = contrato is not None and not [
        c for c in faltantes if not c.startswith("regiao_")
    ]
    regioes = (contrato or {}).get("regioes") or {}
    regioes_ok = all(f in regioes for f in FAMILIAS)
    codigos_ok = pendencias == 0

    def estado(pronto: bool, anteriores_ok: bool) -> str:
        if pronto:
            return CONCLUIDA
        return ATUAL if anteriores_ok else PENDENTE

    upload_ok = itens > 0
    etapas = [
        Etapa(1, "Upload dos PDFs", CONCLUIDA if upload_ok else ATUAL, "/",
              f"{itens} itens extraídos" if upload_ok else "Nenhuma medição no banco"),
        Etapa(2, "Cadastro", estado(cadastro_ok, upload_ok), "/dashboard/?aba=cadastro",
              "Completo" if cadastro_ok else "Campos do contrato em branco"),
        Etapa(3, "Regiões ANP", estado(regioes_ok, cadastro_ok), "/dashboard/?aba=cadastro",
              "Definidas por família" if regioes_ok else "Uma região por família"),
        Etapa(4, "Códigos pendentes", estado(codigos_ok, regioes_ok),
              "/dashboard/?aba=pendencias",
              "Nenhum pendente" if codigos_ok
              else f"{pendencias} fora do cálculo até confirmar"),
    ]
    pronto = upload_ok and cadastro_ok and regioes_ok and codigos_ok
    etapas.append(
        Etapa(5, "Memória de cálculo", ATUAL if pronto else PENDENTE,
              "/dashboard/?aba=reequilibrio",
              "Cálculo disponível" if pronto else "Depende das etapas anteriores")
    )
    etapas.append(
        Etapa(6, "Exportação", CONCLUIDA if pronto else BLOQUEADA,
              "/dashboard/?aba=reequilibrio",
              "Planilha liberada" if pronto else "Bloqueada por pendência")
    )
    return etapas


def resumo(numero: str | None = None) -> Resumo:
    """The trail and the counters for *numero*, or for the only contract there is.

    Falling back to the single contract is what lets the upload page — which has
    no contract selector — still show a truthful trail in the common case of one
    contract at a time.
    """
    contagens = _contagens()
    contratos = contratos_repo.listar()
    contrato = None
    if numero:
        contrato = contratos_repo.buscar(numero)
    elif len(contratos) == 1:
        contrato = contratos_repo.buscar(contratos[0]["numero"])

    faltantes = contratos_repo.campos_faltantes(contrato) if contrato else []
    # Códigos sem associação deixaram de ser pendência (subprojeto A); a
    # trilha inteira é revista no subprojeto B.
    pendencias = 0

    return Resumo(
        contrato=contrato,
        etapas=_etapas(contrato, contagens["itens"], pendencias, faltantes),
        contratos=contagens["contratos"],
        medicoes=contagens["medicoes"],
        itens=contagens["itens"],
        pendencias=pendencias,
        faltantes=faltantes,
    )
