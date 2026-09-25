import { ErroConexao } from '../api/client'
import { ErroApi } from '../api/erros'

// Mensagem de regra de negócio exatamente como o backend a escreveu. Falta de
// conexão não aparece aqui: o aviso fixo (BannerConexao) já cobre.
export function MensagemErro({ erro }: { erro: unknown }) {
  if (!erro || erro instanceof ErroConexao) return null
  const detail = erro instanceof ErroApi ? erro.detail : erro instanceof Error ? erro.message : String(erro)
  const erros = erro instanceof ErroApi ? erro.erros : []
  return (
    <div className="notice danger" role="alert">
      <div>
        <p className="notice-text pre-linha">{detail}</p>
        {erros.length > 0 && (
          <ul className="lista-erros">
            {erros.map((texto) => (
              <li key={texto}>{texto}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
