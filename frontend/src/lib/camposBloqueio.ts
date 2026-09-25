// Os três campos do cadastro que bloqueiam o cálculo — mesma lista de chaves
// que `contratos_repo.campos_faltantes` pode devolver como bloqueante.
// `situacao.ts` (lista de contratos) e `bloqueio.ts` (aba Cálculo) mostram o
// mesmo campo com textos diferentes; esta é a única lista de chaves, para que
// as duas telas não possam divergir sobre quais campos bloqueiam.
export type CampoBloqueio = 'data_base' | 'regiao_cap' | 'regiao_emulsoes'

export const CAMPOS_BLOQUEIO: Record<CampoBloqueio, { rotulo: string; mensagem: string }> = {
  data_base: { rotulo: 'Data Base', mensagem: 'Falta a Data Base do contrato.' },
  regiao_cap: { rotulo: 'região CAP', mensagem: 'Falta a região ANP do CAP.' },
  regiao_emulsoes: { rotulo: 'região Emulsões', mensagem: 'Falta a região ANP das Emulsões.' },
}

export function ehCampoBloqueio(campo: string): campo is CampoBloqueio {
  return campo in CAMPOS_BLOQUEIO
}
