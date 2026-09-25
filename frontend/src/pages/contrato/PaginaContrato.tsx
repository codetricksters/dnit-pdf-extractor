import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router'
import { chaves } from '../../api/chaves'
import { buscarContrato } from '../../api/contratos'
import { ErroApi } from '../../api/erros'
import { buscarCobertura } from '../../api/indices'
import { Cabecalho } from '../../components/Cabecalho'
import { Carregando } from '../../components/Carregando'
import { MensagemErro } from '../../components/MensagemErro'
import { NaoEncontrado } from '../../components/NaoEncontrado'

const ABAS = [
  { para: 'cadastro', rotulo: 'Cadastro' },
  { para: 'medicoes', rotulo: 'Medições' },
  { para: 'calculo', rotulo: 'Cálculo e exportação' },
]

export function PaginaContrato() {
  const id = Number(useParams().id)
  const valido = Number.isInteger(id) && id > 0
  const qc = useQueryClient()
  const consulta = useQuery({ queryKey: chaves.contrato(id), queryFn: () => buscarContrato(id), enabled: valido })

  // /contratos/:id sozinho não bate com nenhuma sub-rota; redireciona para
  // cadastro assim que a página monta, sem esperar o contrato carregar — do
  // contrário o redirecionamento fica dependente da mesma requisição que
  // preenche o cabeçalho, atrasando a navegação sem necessidade.
  const location = useLocation()
  const navigate = useNavigate()
  useEffect(() => {
    if (valido && location.pathname === `/contratos/${id}`) navigate('cadastro', { replace: true })
  }, [valido, id, location.pathname, navigate])

  // Início adiantado: as abas (Cadastro, Cálculo) precisam da lista de
  // regiões; pedir aqui, em paralelo com o contrato, evita que a aba monte e
  // só então dispare a busca, atrasando o preenchimento dos selects.
  // `prefetchQuery` (em vez de `useQuery`) preenche o cache sem forçar mais
  // uma renderização desta página.
  useEffect(() => {
    if (valido) void qc.prefetchQuery({ queryKey: chaves.cobertura, queryFn: buscarCobertura })
  }, [valido, qc])

  if (!valido) return <NaoEncontrado mensagem="Contrato não encontrado." />
  if (consulta.error instanceof ErroApi && consulta.error.status === 404) {
    return <NaoEncontrado mensagem={consulta.error.detail} />
  }
  if (consulta.error) return <MensagemErro erro={consulta.error} />
  if (!consulta.data) return <Carregando />

  const contrato = consulta.data
  return (
    <>
      <Cabecalho
        trilha={<Link to="/contratos">Contratos</Link>}
        titulo={contrato.numero}
        subtitulo={contrato.contratada ?? 'Contratada não informada'}
      />
      <nav className="tabs" aria-label="Seções do contrato">
        {ABAS.map((aba) => (
          <NavLink key={aba.para} to={aba.para} className={({ isActive }) => (isActive ? 'tab active' : 'tab')}>
            {aba.rotulo}
          </NavLink>
        ))}
      </nav>
      <Outlet context={contrato} />
    </>
  )
}
