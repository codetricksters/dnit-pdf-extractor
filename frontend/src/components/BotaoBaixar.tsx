import { type ReactNode, useState } from 'react'
import { ErroConexao, pedirArquivo, salvarArquivo } from '../api/client'
import { ErroApi } from '../api/erros'

interface Props {
  caminho: string
  nomeArquivo: string
  className?: string
  children: ReactNode
}

// Substitui o <a href download> puro: busca o arquivo como blob e só o salva
// se a resposta foi 2xx, para que um erro do backend não seja gravado no disco
// do usuário como se fosse a planilha/CSV/zip pedido.
export function BotaoBaixar({ caminho, nomeArquivo, className = 'btn', children }: Props) {
  const [erro, setErro] = useState<unknown>(null)
  const [baixando, setBaixando] = useState(false)

  async function baixar() {
    setErro(null)
    setBaixando(true)
    try {
      const arquivo = await pedirArquivo(caminho)
      salvarArquivo(arquivo.blob, arquivo.nomeArquivo ?? nomeArquivo)
    } catch (e) {
      setErro(e)
    } finally {
      setBaixando(false)
    }
  }

  // Falta de conexão já aparece no BannerConexao fixo da aplicação inteira.
  const mensagem =
    erro instanceof ErroConexao ? null : erro instanceof ErroApi ? erro.detail : erro instanceof Error ? erro.message : null

  return (
    <>
      <button type="button" className={className} disabled={baixando} onClick={baixar}>
        {children}
      </button>
      {mensagem && <span className="erro-campo">{mensagem}</span>}
    </>
  )
}
