import { ErroApi } from '../../api/erros'
import type { CampoCadastro, Contrato, ContratoPatch, Familia } from '../../api/tipos'
import { exato } from '../../lib/formato'

// O formulário do cadastro como strings; a API recebe só o que mudou.

export interface ValoresCadastro {
  data_base: string // AAAA-MM, do <input type="month">
  regiao_CAP: string
  regiao_EMULSOES: string
  contratada: string
  edital: string
  rodovia: string
  trecho: string
  subtrecho: string
  segmento: string
  extensao: string // como o usuário digita: "45,7"
}

export type CampoForm = keyof ValoresCadastro

export const PARAMETROS: { campo: CampoForm; rotulo: string }[] = [
  { campo: 'data_base', rotulo: 'Data Base' },
  { campo: 'regiao_CAP', rotulo: 'Região ANP — CAP' },
  { campo: 'regiao_EMULSOES', rotulo: 'Região ANP — Emulsões' },
]

export const CABECALHO: { campo: CampoCadastro; rotulo: string }[] = [
  { campo: 'contratada', rotulo: 'Contratada' },
  { campo: 'edital', rotulo: 'Edital' },
  { campo: 'rodovia', rotulo: 'Rodovia' },
  { campo: 'trecho', rotulo: 'Trecho' },
  { campo: 'subtrecho', rotulo: 'Subtrecho' },
  { campo: 'segmento', rotulo: 'Segmento' },
  { campo: 'extensao', rotulo: 'Extensão (km)' },
]

export function valoresIniciais(c: Contrato): ValoresCadastro {
  return {
    data_base: c.data_base ? c.data_base.slice(0, 7) : '',
    regiao_CAP: c.regioes.CAP ?? '',
    regiao_EMULSOES: c.regioes.EMULSOES ?? '',
    contratada: c.contratada ?? '',
    edital: c.edital ?? '',
    rodovia: c.rodovia ?? '',
    trecho: c.trecho ?? '',
    subtrecho: c.subtrecho ?? '',
    segmento: c.segmento ?? '',
    extensao: c.extensao ? exato(c.extensao).replace(/\./g, '') : '',
  }
}

export function montarPatch(v: ValoresCadastro, sujos: Partial<Record<CampoForm, unknown>>): ContratoPatch {
  const patch: ContratoPatch = {}
  for (const { campo } of CABECALHO) {
    if (sujos[campo]) patch[campo] = v[campo].trim() || null
  }
  if (sujos.data_base) patch.data_base = v.data_base
  const regioes: Partial<Record<Familia, string>> = {}
  if (sujos.regiao_CAP && v.regiao_CAP) regioes.CAP = v.regiao_CAP
  if (sujos.regiao_EMULSOES && v.regiao_EMULSOES) regioes.EMULSOES = v.regiao_EMULSOES
  if (Object.keys(regioes).length) patch.regioes = regioes
  return patch
}

export function pendenciasParametros(v: ValoresCadastro): number {
  return PARAMETROS.filter(({ campo }) => !v[campo]).length
}

export function vaziosCabecalho(v: ValoresCadastro): number {
  return CABECALHO.filter(({ campo }) => !v[campo].trim()).length
}

// A recusa do PATCH é uma frase só (CadastroInvalido); este mapa decide em qual
// campo mostrá-la. A validação do Pydantic já vem por campo.
export function campoDoErro(erro: ErroApi, v: ValoresCadastro): Partial<Record<CampoForm | 'geral', string>> {
  if (Object.keys(erro.campos).length) {
    const saida: Partial<Record<CampoForm | 'geral', string>> = {}
    for (const [loc, msg] of Object.entries(erro.campos)) {
      const campo = loc.replace(/^regioes\./, 'regiao_') as CampoForm
      saida[campo in v ? campo : 'geral'] = msg
    }
    return saida
  }
  if (/Data Base/.test(erro.detail)) return { data_base: erro.detail }
  if (/Região/.test(erro.detail)) {
    const familia = (['CAP', 'EMULSOES'] as const).find((f) => {
      const valor = v[`regiao_${f}`]
      return valor && erro.detail.includes(`'${valor}'`)
    })
    if (familia) return { [`regiao_${familia}`]: erro.detail }
  }
  return { geral: erro.detail }
}
