import { useId, useRef, useState, type FormEvent, type ReactNode } from 'react'

interface Props {
  rotulo: string
  accept: string
  botao: string
  pendente: boolean
  aoEnviar: (arquivo: File) => Promise<unknown>
  // Campos extras entre o arquivo e o botão (a observação do template).
  children?: ReactNode
}

export function EnviarArquivo({ rotulo, accept, botao, pendente, aoEnviar, children }: Props) {
  const id = useId()
  const campo = useRef<HTMLInputElement>(null)
  const [arquivo, setArquivo] = useState<File | null>(null)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) return
    try {
      await aoEnviar(arquivo)
      setArquivo(null)
      if (campo.current) campo.current.value = ''
    } catch {
      // O erro já aparece na página, pela mutação que aoEnviar dispara.
    }
  }

  return (
    <form className="barra" onSubmit={enviar}>
      <div className="field">
        <label className="field-label" htmlFor={id}>{rotulo}</label>
        <input
          ref={campo}
          id={id}
          type="file"
          className="input"
          accept={accept}
          onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
        />
      </div>
      {children}
      <button type="submit" className="btn btn-primary" disabled={!arquivo || pendente}>{botao}</button>
    </form>
  )
}
