"""Importação contra o banco: prévia, inalterados, conflito manual, tudo ou nada."""

from datetime import date
from decimal import Decimal

import pytest

from app.services import importacao, importadores, indices_repo
from app.services.delta_p import ANP_PRODUTO_CAP
from app.services.importadores import ArquivoInvalido, Leitura

from .indices_factory import mes_igp, semana

CAP = ANP_PRODUTO_CAP


def _leitura(*semanas):
    return Leitura(list(semanas))


def _anp(leitura, **opcoes):
    return importacao.importar_precos(leitura, arquivo="anp.xls", **opcoes)


async def test_primeira_importacao_insere_e_a_segunda_nao_muda_nada():
    leitura = _leitura(semana(date(2023, 1, 9), "3.28568"), semana(date(2023, 1, 16), "3.3"))
    primeira = _anp(leitura)
    assert primeira["inseridos"] == 2 and primeira["inalterados"] == 0
    assert primeira["periodo"] == {"de": date(2023, 1, 9), "ate": date(2023, 1, 22)}
    assert indices_repo.listar_precos_anp()[0]["origem"] == "upload:anp.xls"

    segunda = importacao.importar_precos(leitura, arquivo="outro.xls")
    assert segunda["inseridos"] == 0 and segunda["inalterados"] == 2
    assert segunda["atualizados"] == []
    assert {l["origem"] for l in indices_repo.listar_precos_anp()} == {"upload:anp.xls"}


async def test_simulacao_nao_grava():
    resposta = _anp(_leitura(semana(date(2023, 1, 9), "3.28")), simular=True)
    assert resposta["simulacao"] is True and resposta["inseridos"] == 1
    assert indices_repo.listar_precos_anp() == []


async def test_atualizacao_lista_antes_e_depois():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")], origem="seed")
    resposta = _anp(_leitura(semana(date(2023, 1, 9), "3.30")))
    (alteracao,) = resposta["atualizados"]
    assert alteracao["antes"] == Decimal("3.28") and alteracao["depois"] == Decimal("3.30")
    assert alteracao["chave"] == {
        "produto": CAP, "regiao": "Nordeste",
        "vigencia_inicio": "2023-01-09", "vigencia_fim": "2023-01-15",
    }


async def test_valor_manual_e_preservado_por_padrao():
    indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Nordeste", "preco": "9.99"}
    )
    resposta = _anp(_leitura(semana(date(2023, 1, 9), "3.28"), semana(date(2023, 1, 16), "3.3")))
    assert resposta["manuais_preservados"] == 1 and resposta["inseridos"] == 1
    (conflito,) = resposta["conflitos_manuais"]
    assert conflito["valor_banco"] == Decimal("9.99") and conflito["valor_arquivo"] == Decimal("3.28")
    assert conflito["atualizado_em"] is not None
    salvo = indices_repo.buscar_semana(CAP, "Nordeste", date(2023, 1, 9))
    assert salvo["preco"] == Decimal("9.99") and salvo["origem"] == indices_repo.ORIGEM_MANUAL


async def test_sobrescrever_manuais_faz_o_arquivo_vencer():
    indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Nordeste", "preco": "9.99"}
    )
    resposta = _anp(_leitura(semana(date(2023, 1, 9), "3.28")), sobrescrever_manuais=True)
    assert resposta["manuais_preservados"] == 0
    assert len(resposta["conflitos_manuais"]) == 1 and len(resposta["atualizados"]) == 1
    salvo = indices_repo.buscar_semana(CAP, "Nordeste", date(2023, 1, 9))
    assert salvo["preco"] == Decimal("3.28") and salvo["origem"] == "upload:anp.xls"


async def test_sobreposicao_recusa_o_arquivo_sem_gravar_nada():
    indices_repo.gravar_precos_anp([semana(date(2023, 1, 9), "3.28")])
    with pytest.raises(ArquivoInvalido) as erro:
        _anp(_leitura(semana(date(2023, 1, 30), "3.1"), semana(date(2023, 1, 12), "3.3")))
    assert "sobreposta" in erro.value.mensagem
    assert len(indices_repo.listar_precos_anp()) == 1


async def test_semana_manual_preservada_causa_sobreposicao_com_semana_nova():
    """Sem sobrescrever_manuais, a semana manual 09-15 não é substituída pela
    09-12 do arquivo — continua com fim em 15, que colide com a 13-19 nova.
    A prévia (simular=True) tem de recusar exatamente como a gravação real."""
    indices_repo.gravar_semana_manual(
        {"vigencia_inicio": date(2023, 1, 9), "vigencia_fim": date(2023, 1, 15),
         "regiao": "Nordeste", "preco": "9.99"}
    )
    leitura = _leitura(semana(date(2023, 1, 9), "3.28", dias=3), semana(date(2023, 1, 13), "3.30"))

    with pytest.raises(ArquivoInvalido) as previa:
        _anp(leitura, simular=True)
    assert any("manual" in e for e in previa.value.erros)

    with pytest.raises(ArquivoInvalido) as grava:
        _anp(leitura)
    assert any("manual" in e for e in grava.value.erros)

    salvas = indices_repo.listar_precos_anp(regiao="Nordeste")
    assert len(salvas) == 1 and salvas[0]["preco"] == Decimal("9.99")

    resposta = _anp(leitura, sobrescrever_manuais=True)
    assert resposta["conflitos_manuais"] and resposta["atualizados"]
    salvas = indices_repo.listar_precos_anp(regiao="Nordeste")
    assert {s["vigencia_inicio"] for s in salvas} == {date(2023, 1, 9), date(2023, 1, 13)}


async def test_origem_explicita_para_o_seed():
    _anp(_leitura(semana(date(2023, 1, 9), "3.28")), origem=indices_repo.ORIGEM_SEED)
    assert indices_repo.listar_precos_anp()[0]["origem"] == "seed"


async def test_importar_igp_di_do_template():
    indices_repo.gravar_indice_manual(date(2023, 1, 1), "1000")
    conteudo = importadores.gerar_template_igp_di(
        [mes_igp(date(2022, 1, 1), "1110.398"), mes_igp(date(2023, 1, 1), "1143.861")]
    )
    resposta = importacao.importar_igp_di(conteudo, "igp.xlsx")
    assert resposta["inseridos"] == 1 and resposta["manuais_preservados"] == 1
    assert resposta["conflitos_manuais"][0]["chave"] == {"mes": "2023-01"}
    assert resposta["periodo"] == {"de": date(2022, 1, 1), "ate": date(2023, 1, 1)}
    assert indices_repo.buscar_indice(date(2022, 1, 1))["origem"] == "upload:igp.xlsx"
    assert indices_repo.buscar_indice(date(2023, 1, 1))["valor"] == Decimal("1000")


async def test_importar_anp_repassa_o_erro_de_leitura():
    with pytest.raises(ArquivoInvalido):
        importacao.importar_anp(b"lixo", "x.xls")
