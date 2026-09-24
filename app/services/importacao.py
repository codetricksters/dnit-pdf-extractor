"""O que uma importação de índices faz com o banco.

``importadores`` diz se o arquivo é válido; este módulo compara com o que está
gravado e decide o que regravar: valores iguais ficam como estão (origem e data
preservadas), valores ``origem = 'manual'`` só são sobrescritos quando o usuário
pede, e ``simular`` devolve o mesmo relatório sem gravar — a prévia que a tela
mostra antes da pergunta "Deseja sobrescrever as N alterações manuais?".
"""

from dataclasses import dataclass, field

from . import importadores, indices_repo
from .importadores import ArquivoInvalido, Leitura


@dataclass
class Plano:
    gravar: list[dict] = field(default_factory=list)
    inseridos: int = 0
    atualizados: list[dict] = field(default_factory=list)
    inalterados: int = 0
    conflitos_manuais: list[dict] = field(default_factory=list)


def planejar(novos, existentes, *, chave, comparavel, valor, mostrar, sobrescrever_manuais) -> Plano:
    """Classifica cada registro do arquivo contra o banco."""
    plano = Plano()
    for registro in novos:
        atual = existentes.get(chave(registro))
        if atual is None:
            plano.inseridos += 1
            plano.gravar.append(registro)
            continue
        if comparavel(atual) == comparavel(registro):
            plano.inalterados += 1
            continue
        if atual["origem"] == indices_repo.ORIGEM_MANUAL:
            plano.conflitos_manuais.append(
                {
                    "chave": mostrar(registro),
                    "valor_banco": valor(atual),
                    "valor_arquivo": valor(registro),
                    "atualizado_em": atual["atualizado_em"],
                }
            )
            if not sobrescrever_manuais:
                continue
        plano.atualizados.append(
            {"chave": mostrar(registro), "antes": valor(atual), "depois": valor(registro)}
        )
        plano.gravar.append(registro)
    return plano


def _resposta(arquivo, simular, sobrescrever_manuais, plano: Plano, avisos, de, ate) -> dict:
    return {
        "arquivo": arquivo,
        "simulacao": simular,
        "periodo": {"de": de, "ate": ate},
        "inseridos": plano.inseridos,
        "atualizados": plano.atualizados,
        "inalterados": plano.inalterados,
        "conflitos_manuais": plano.conflitos_manuais,
        "manuais_preservados": 0 if sobrescrever_manuais else len(plano.conflitos_manuais),
        "avisos": list(avisos),
    }


def importar_precos(
    leitura: Leitura, *, arquivo: str, simular: bool = False,
    sobrescrever_manuais: bool = False, origem: str | None = None,
) -> dict:
    novos = leitura.registros
    existentes = indices_repo.precos_anp_por_chave({r["produto"] for r in novos})
    conflitos = importadores.sobreposicoes(novos, existentes)
    if conflitos:
        raise ArquivoInvalido(
            f"O arquivo tem {len(conflitos)} semana(s) sobreposta(s); nada foi gravado.",
            importadores.limitar(conflitos),
        )
    plano = planejar(
        novos,
        existentes,
        chave=lambda r: (r["produto"], r["vigencia_inicio"], r["regiao"]),
        comparavel=lambda r: (r["vigencia_fim"], r["preco"]),
        valor=lambda r: r["preco"],
        mostrar=lambda r: {
            "produto": r["produto"],
            "regiao": r["regiao"],
            "vigencia_inicio": r["vigencia_inicio"].isoformat(),
            "vigencia_fim": r["vigencia_fim"].isoformat(),
        },
        sobrescrever_manuais=sobrescrever_manuais,
    )
    if not simular:
        indices_repo.gravar_precos_anp(
            plano.gravar, origem=origem or indices_repo.origem_upload(arquivo)
        )
    return _resposta(
        arquivo, simular, sobrescrever_manuais, plano, leitura.avisos,
        min(r["vigencia_inicio"] for r in novos), max(r["vigencia_fim"] for r in novos),
    )


def importar_indices(
    leitura: Leitura, *, arquivo: str, simular: bool = False,
    sobrescrever_manuais: bool = False, origem: str | None = None,
) -> dict:
    novos = leitura.registros
    plano = planejar(
        novos,
        indices_repo.indices_por_mes(),
        chave=lambda r: r["mes_ref"],
        comparavel=lambda r: r["valor"],
        valor=lambda r: r["valor"],
        mostrar=lambda r: {"mes": f"{r['mes_ref']:%Y-%m}"},
        sobrescrever_manuais=sobrescrever_manuais,
    )
    if not simular:
        indices_repo.gravar_indices_mensais(
            plano.gravar, origem=origem or indices_repo.origem_upload(arquivo)
        )
    return _resposta(
        arquivo, simular, sobrescrever_manuais, plano, leitura.avisos,
        min(r["mes_ref"] for r in novos), max(r["mes_ref"] for r in novos),
    )


def importar_anp(conteudo: bytes, arquivo: str, **opcoes) -> dict:
    return importar_precos(importadores.ler_anp(conteudo), arquivo=arquivo, **opcoes)


def importar_igp_di(conteudo: bytes, arquivo: str, **opcoes) -> dict:
    return importar_indices(importadores.ler_igp_di(conteudo), arquivo=arquivo, **opcoes)
