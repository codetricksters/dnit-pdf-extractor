import { Link, Outlet, useLocation } from 'react-router'
import { Icone } from './Icone'

interface Item {
  para: string
  prefixos: string[]
  icone: string
  rotulo: string
}

const GRUPOS: { titulo: string; itens: Item[] }[] = [
  {
    titulo: 'Trabalho',
    itens: [
      { para: '/contratos', prefixos: ['/', '/contratos'], icone: 'description', rotulo: 'Contratos' },
      { para: '/upload', prefixos: ['/upload'], icone: 'upload_file', rotulo: 'Upload de PDFs' },
    ],
  },
  {
    titulo: 'Bases globais',
    itens: [
      { para: '/catalogo', prefixos: ['/catalogo'], icone: 'inventory_2', rotulo: 'Catálogo de produtos' },
      { para: '/indices/anp', prefixos: ['/indices'], icone: 'monitoring', rotulo: 'Índices ANP / IGP-DI' },
    ],
  },
  {
    titulo: 'Sistema',
    itens: [
      { para: '/sistema/templates', prefixos: ['/sistema/templates'], icone: 'table_view', rotulo: 'Templates' },
      { para: '/sistema/backups', prefixos: ['/sistema/backups'], icone: 'backup', rotulo: 'Backups' },
    ],
  },
]

// "/" só casa com a raiz; os demais prefixos casam com as sub-rotas.
export function itemAtivo(prefixos: string[], pathname: string): boolean {
  return prefixos.some((p) => (p === '/' ? pathname === '/' : pathname === p || pathname.startsWith(`${p}/`)))
}

export function Shell() {
  const { pathname } = useLocation()
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <img className="brand-mark" src="/logo.svg" alt="" />
          <div>
            <p className="brand-title">DNIT</p>
            <p className="brand-sub">Reequilíbrio · art. 16</p>
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="Menu principal">
          {GRUPOS.map((grupo) => (
            <div className="nav-group" key={grupo.titulo}>
              <p className="nav-group-title">{grupo.titulo}</p>
              {grupo.itens.map((item) => {
                const ativo = itemAtivo(item.prefixos, pathname)
                return (
                  <Link
                    key={item.para}
                    to={item.para}
                    className={ativo ? 'nav-item active' : 'nav-item'}
                    aria-current={ativo ? 'page' : undefined}
                  >
                    <Icone nome={item.icone} />
                    <span>{item.rotulo}</span>
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
