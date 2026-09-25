// Respostas da API. Decimal chega como string (Pydantic 2) e nunca vira
// number: é só formatado (lib/formato.ts). Datas são strings ISO.

export type Decimal = string
export type Familia = 'CAP' | 'EMULSOES'
export const FAMILIAS: Familia[] = ['CAP', 'EMULSOES']
export const ROTULO_FAMILIA: Record<Familia, string> = { CAP: 'CAP', EMULSOES: 'Emulsões' }

export interface ContratoResumo {
  id: number
  numero: string
  data_base: string | null
  contratada: string | null
  rodovia: string | null
  regioes: Partial<Record<Familia, string>>
  itens: number
  medicoes: number
  primeiro_mes: string | null
  ultimo_mes: string | null
  faltantes: string[]
}

export interface Contrato {
  id: number
  numero: string
  numero_processo: string | null
  data_base: string | null
  edital: string | null
  rodovia: string | null
  trecho: string | null
  subtrecho: string | null
  segmento: string | null
  extensao: Decimal | null
  contratada: string | null
  regioes: Partial<Record<Familia, string>>
  faltantes: string[]
  atualizado_em: string
}

export type CampoCadastro = 'edital' | 'rodovia' | 'trecho' | 'subtrecho' | 'segmento' | 'extensao' | 'contratada'

export interface ContratoPatch {
  edital?: string | null
  rodovia?: string | null
  trecho?: string | null
  subtrecho?: string | null
  segmento?: string | null
  extensao?: string | null
  contratada?: string | null
  data_base?: string
  regioes?: Partial<Record<Familia, string>>
}

export interface ItemMedicao {
  id: number
  mes: string
  codigo: string
  descricao_pdf: string | null
  valor_pi: Decimal
  fator: Decimal
  reajuste: Decimal
  arquivo: string
  produto_id: number | null
  produto: string | null
  familia: Familia | null
}

export interface LinhaCalculo {
  mes: string
  a: Decimal
  fator: Decimal
  b: Decimal
  d: Decimal
  c: Decimal
  e: Decimal
  f: Decimal
}

export interface ProdutoCalculo {
  descricao: string
  subtotal: Decimal
  linhas: LinhaCalculo[]
}

export interface FamiliaCalculo {
  familia: Familia
  rotulo: string
  subtotal: Decimal
  produtos: ProdutoCalculo[]
}

export interface Calculo {
  contrato: { id: number; numero: string }
  parametros: { data_base: string; regioes: Partial<Record<Familia, string>>; simulacao: boolean; lucro: Decimal }
  familias: FamiliaCalculo[]
  total: Decimal
  avisos: string[]
  arquivo: string
}

export interface Produto {
  id: number
  descricao_export: string
  familia: Familia
  ordem: number
  codigos: number
}

export interface Codigo {
  codigo: string
  descricao_pdf: string | null
  contratos: number
  ocorrencias: number
  produto_id: number | null
  descricao_export: string | null
  familia: Familia | null
}

export interface SemanaAnp {
  id: number
  produto: string
  regiao: string
  vigencia_inicio: string
  vigencia_fim: string
  preco: Decimal | null
  origem: string
  atualizado_em: string
}

export interface SemanaAnpEntrada {
  produto?: string
  vigencia_inicio: string
  vigencia_fim: string
  regiao: string
  preco: Decimal | null
}

export interface IndiceMensal {
  mes: string
  valor: Decimal
  origem: string
  atualizado_em: string
}

export interface PeriodoCoberto {
  de: string | null
  ate: string | null
  registros: number
  manuais: number
}

export interface Cobertura {
  anp: PeriodoCoberto
  igp_di: PeriodoCoberto
  regioes: string[]
}

export interface ResultadoImportacao {
  arquivo: string
  simulacao: boolean
  periodo: { de: string | null; ate: string | null }
  inseridos: number
  atualizados: { chave: Record<string, string>; antes: Decimal | null; depois: Decimal | null }[]
  inalterados: number
  conflitos_manuais: {
    chave: Record<string, string>
    valor_banco: Decimal | null
    valor_arquivo: Decimal | null
    atualizado_em: string
  }[]
  manuais_preservados: number
  avisos: string[]
}

export type StatusArquivo = 'pending' | 'processing' | 'completed' | 'failed'

export interface ArquivoDoJob {
  status: StatusArquivo
  error: string | null
  contrato_id: number | null
  itens: number | null
}

export interface StatusJob {
  job_id: string
  completed: boolean
  files: Record<string, ArquivoDoJob>
}

export interface ResumoJob {
  job_id: string
  created_at: string
  completed: boolean
  file_count: number
  completed_count: number
  failed_count: number
  processing_count: number
  pending_count: number
}

export interface Template {
  id: number
  nome: string
  tamanho: number
  sha256: string
  ativo: boolean
  criado_em: string
  observacao: string | null
}

export interface Backup {
  nome: string
  tamanho: number
  criado_em: string
}
