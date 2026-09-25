import type { Cobertura, Contrato, ContratoResumo } from '../src/api/tipos'

export function umContrato(parcial: Partial<Contrato> = {}): Contrato {
  return {
    id: 1,
    numero: '15 00716/2022',
    numero_processo: '50600.000123/2021-11',
    data_base: '2022-01-01',
    edital: '0123/2021-15',
    rodovia: 'BR-230',
    trecho: 'Div. PB/PE',
    subtrecho: 'Entr. BR-104',
    segmento: 'km 10,0 ao km 55,7',
    extensao: '45.7',
    contratada: 'HWN ENGENHARIA LTDA',
    regioes: { CAP: 'Nordeste', EMULSOES: 'Nordeste' },
    faltantes: [],
    atualizado_em: '2026-09-24T10:02:00+00:00',
    ...parcial,
  }
}

export function umResumo(parcial: Partial<ContratoResumo> = {}): ContratoResumo {
  return {
    id: 1,
    numero: '15 00716/2022',
    data_base: '2022-01-01',
    contratada: 'HWN ENGENHARIA LTDA',
    rodovia: 'BR-230',
    regioes: { CAP: 'Nordeste', EMULSOES: 'Nordeste' },
    itens: 48,
    medicoes: 2,
    primeiro_mes: '2023-02-01',
    ultimo_mes: '2023-03-01',
    faltantes: [],
    ...parcial,
  }
}

export function umaCobertura(parcial: Partial<Cobertura> = {}): Cobertura {
  return {
    anp: { de: '2013-01-06', ate: '2026-09-19', registros: 60114, manuais: 0 },
    igp_di: { de: '2022-01-01', ate: '2026-08-01', registros: 56, manuais: 1 },
    regioes: ['Centro-Oeste', 'Nordeste', 'Norte', 'Sudeste', 'Sul'],
    ...parcial,
  }
}
