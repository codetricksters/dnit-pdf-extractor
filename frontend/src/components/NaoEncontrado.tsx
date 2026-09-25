import { Link } from 'react-router'
import { Cabecalho } from './Cabecalho'

export function NaoEncontrado({ mensagem = 'A página pedida não existe.' }: { mensagem?: string }) {
  return (
    <>
      <Cabecalho titulo="Não encontrado" />
      <div className="panel">
        <div className="empty-state">
          <p>{mensagem}</p>
          <p className="mt-md">
            <Link to="/contratos" className="btn btn-sm">
              Voltar aos contratos
            </Link>
          </p>
        </div>
      </div>
    </>
  )
}
