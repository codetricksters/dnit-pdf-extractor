import { useState, type DragEvent } from 'react'
import { Icone } from '../../components/Icone'
import { tamanho } from '../../lib/formato'

const ehPdf = (f: File) => f.name.toLowerCase().endsWith('.pdf')

interface Props {
  arquivos: File[]
  aoEscolher: (arquivos: File[]) => void
  desabilitado: boolean
}

// Arrastar e soltar ou escolher. Soltar não respeita o accept do input, por isso
// o filtro de PDF é feito aqui e o ignorado é dito ao usuário.
export function AreaArquivos({ arquivos, aoEscolher, desabilitado }: Props) {
  const [sobre, setSobre] = useState(false)
  const [ignorados, setIgnorados] = useState<string[]>([])

  function receber(lista: FileList | null) {
    const todos = [...(lista ?? [])]
    setIgnorados(todos.filter((f) => !ehPdf(f)).map((f) => f.name))
    aoEscolher(todos.filter(ehPdf))
  }

  function soltar(e: DragEvent) {
    e.preventDefault()
    setSobre(false)
    if (!desabilitado) receber(e.dataTransfer.files)
  }

  const total = arquivos.reduce((soma, f) => soma + f.size, 0)
  return (
    <>
      <label
        className={sobre ? 'dropzone over' : 'dropzone'}
        onDragOver={(e) => {
          e.preventDefault()
          setSobre(true)
        }}
        onDragLeave={() => setSobre(false)}
        onDrop={soltar}
      >
        <input
          type="file"
          accept=".pdf"
          multiple
          aria-label="Arquivos PDF"
          disabled={desabilitado}
          onChange={(e) => {
            receber(e.target.files)
            e.target.value = ''
          }}
        />
        <span className="dropzone-icon"><Icone nome="cloud_upload" /></span>
        <span className="dropzone-title">Arraste os PDFs aqui ou clique para escolher</span>
        <span className="dropzone-text">
          PDFs de Resumo da Medição, com texto ou digitalizados. Os digitalizados passam pelo OCR automaticamente.
        </span>
        <span className="dropzone-meta">
          <span>
            <Icone nome="summarize" />
            <span>
              {arquivos.length === 0
                ? 'Nenhum arquivo selecionado'
                : `${arquivos.length} ${arquivos.length === 1 ? 'arquivo selecionado' : 'arquivos selecionados'}`}
            </span>
          </span>
          {arquivos.length > 0 && (
            <span>
              <Icone nome="scale" />
              <span>{tamanho(total)}</span>
            </span>
          )}
        </span>
      </label>
      {ignorados.length > 0 && (
        <p className="erro-campo mt-md">Ignorado: {ignorados.join(', ')} (não é PDF).</p>
      )}
    </>
  )
}
