"""scripts/seed_indices.py: casca de linha de comando sobre a importação."""

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.services import importacao, importadores, indices_repo
from app.services.delta_p import ANP_PRODUTO_CAP

from .indices_factory import linha_anp, linhas_anp

SCRIPT = Path("scripts/seed_indices.py")


def _seed():
    spec = importlib.util.spec_from_file_location("seed_indices", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture()
def anp_pequeno(monkeypatch):
    """Troca a leitura do .xls oficial (60 mil registros) por uma semana só.

    O resto do caminho — plano, gravação e ``origem`` — é o real.
    """
    leitura = importadores.ler_linhas_anp(
        linhas_anp([linha_anp(ANP_PRODUTO_CAP, date(2023, 1, 9), [3.1, 3.28568, 3.2, 3.45, 3.3, 3.9])])
    )

    def importar_anp(conteudo, arquivo, **opcoes):
        return importacao.importar_precos(leitura, arquivo=arquivo, **opcoes)

    monkeypatch.setattr(importacao, "importar_anp", importar_anp)


def test_seed_grava_anp_e_igp_com_origem_seed(tmp_path, anp_pequeno):
    anp = tmp_path / "anp.xls"
    anp.write_bytes(b"conteudo irrelevante: a leitura foi trocada")
    igp = tmp_path / "igp.xlsx"
    igp.write_bytes(
        importadores.gerar_template_igp_di(
            [{"mes_ref": date(2022, 1, 1), "valor": Decimal("1110.398")}]
        )
    )

    assert _seed().executar(anp, igp) == 0

    precos = indices_repo.listar_precos_anp()
    assert len(precos) == 6
    assert {p["origem"] for p in precos} == {indices_repo.ORIGEM_SEED}
    (indice,) = indices_repo.listar_indices_mensais()
    assert indice["valor"] == Decimal("1110.398")
    assert indice["origem"] == indices_repo.ORIGEM_SEED


def test_seed_preserva_correcao_manual(tmp_path, anp_pequeno):
    indices_repo.gravar_indice_manual(date(2022, 1, 1), Decimal("1000"))
    igp = tmp_path / "igp.xlsx"
    igp.write_bytes(
        importadores.gerar_template_igp_di(
            [{"mes_ref": date(2022, 1, 1), "valor": Decimal("1110.398")}]
        )
    )

    assert _seed().executar(None, igp) == 0

    (indice,) = indices_repo.listar_indices_mensais()
    assert indice["valor"] == Decimal("1000")
    assert indice["origem"] == indices_repo.ORIGEM_MANUAL


def test_sem_igp_orienta_pelo_template(capsys, tmp_path, anp_pequeno):
    anp = tmp_path / "anp.xls"
    anp.write_bytes(b"x")
    assert _seed().executar(anp, None) == 0
    assert "/api/v1/indices/igp-di/template" in capsys.readouterr().out


def test_arquivo_inexistente_e_erro(capsys, tmp_path):
    assert _seed().executar(tmp_path / "nao-existe.xls", None) == 1
    assert "arquivo não encontrado" in capsys.readouterr().err
    assert indices_repo.listar_precos_anp() == []


def test_arquivo_invalido_e_erro_sem_gravar(capsys, tmp_path):
    igp = tmp_path / "igp.xlsx"
    igp.write_bytes(b"isto nao e um xlsx")
    assert _seed().executar(None, igp) == 1
    assert capsys.readouterr().err
    assert indices_repo.listar_indices_mensais() == []


def test_seed_nao_le_a_planilha_de_referencia():
    assert "Reequilíbrio" not in SCRIPT.read_text(encoding="utf-8")
