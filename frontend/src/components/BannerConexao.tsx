import { useQueryClient } from '@tanstack/react-query'
import { useOffline } from '../api/conexao'
import { Icone } from './Icone'

export function BannerConexao() {
  const offline = useOffline()
  const qc = useQueryClient()
  if (!offline) return null
  return (
    <div className="notice warn banner-conexao" role="alert">
      <div className="notice-icon">
        <Icone nome="cloud_off" />
      </div>
      <div>
        <p className="notice-title">Sem conexão com o servidor.</p>
        <p className="notice-text">Confira se o servidor está rodando e tente de novo.</p>
        <div className="notice-actions">
          <button type="button" className="btn btn-sm" onClick={() => qc.refetchQueries({ type: 'active' })}>
            Tentar de novo
          </button>
        </div>
      </div>
    </div>
  )
}
