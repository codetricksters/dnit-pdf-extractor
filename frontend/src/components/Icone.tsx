// Material Symbols é decorativo: o texto ao lado é o rótulo acessível.
export function Icone({ nome }: { nome: string }) {
  return (
    <span className="material-symbols-outlined" aria-hidden="true">
      {nome}
    </span>
  )
}
