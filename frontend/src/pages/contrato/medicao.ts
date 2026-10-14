import type { ItemMedicao, MedicaoCorpo } from '../../api/tipos'
import { exato, paraDecimal } from '../../lib/formato'

// O formulário do registro como strings, na digitação brasileira.
export interface ValoresMedicao {
  mes: string // AAAA-MM, de CampoMesAno
  codigo: string
  descricao_pdf: string
  valor_pi: string
  fator: string
  regiao_cap: string // '' = segue o contrato
  regiao_emulsoes: string
}

export type CampoMedicao = keyof ValoresMedicao

const VAZIO: ValoresMedicao = {
  mes: '', codigo: '', descricao_pdf: '', valor_pi: '', fator: '', regiao_cap: '', regiao_emulsoes: '',
}

export function valoresIniciais(item?: ItemMedicao): ValoresMedicao {
  if (!item) return { ...VAZIO }
  return {
    mes: item.mes.slice(0, 7),
    codigo: item.codigo,
    descricao_pdf: item.descricao_pdf ?? '',
    valor_pi: exato(item.valor_pi).replace(/\./g, ''),
    fator: exato(item.fator).replace(/\./g, ''),
    regiao_cap: item.regiao_cap ?? '',
    regiao_emulsoes: item.regiao_emulsoes ?? '',
  }
}

// Inclusão manda tudo; edição, só os campos sujos. Texto ilegível segue como
// digitado: o 422 do backend o recusa e a mensagem aparece no campo.
export function montarCorpo(v: ValoresMedicao, sujos?: Partial<Record<CampoMedicao, unknown>>): MedicaoCorpo {
  const todos: MedicaoCorpo = {
    mes: v.mes,
    codigo: v.codigo.trim(),
    descricao_pdf: v.descricao_pdf.trim() || null,
    valor_pi: paraDecimal(v.valor_pi) ?? v.valor_pi,
    fator: paraDecimal(v.fator) ?? v.fator,
    regiao_cap: v.regiao_cap || null,
    regiao_emulsoes: v.regiao_emulsoes || null,
  }
  if (!sujos) return todos
  return Object.fromEntries(
    Object.entries(todos).filter(([campo]) => sujos[campo as CampoMedicao]),
  ) as MedicaoCorpo
}

// O 422 do backend vem em texto "campo: mensagem" por linha; cada linha vai
// para o seu campo, e o resto para a mensagem geral.
export function errosPorCampo(detail: string): Partial<Record<CampoMedicao | 'geral', string>> {
  const saida: Partial<Record<CampoMedicao | 'geral', string>> = {}
  for (const linha of detail.split('\n')) {
    const campo = linha.split(':')[0].trim()
    const chave = campo in VAZIO ? (campo as CampoMedicao) : 'geral'
    saida[chave] = saida[chave] ? `${saida[chave]}\n${linha}` : linha
  }
  return saida
}
