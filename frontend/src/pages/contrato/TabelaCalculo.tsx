import { Fragment } from 'react'
import type { Calculo, Decimal } from '../../api/tipos'
import { deltaP, dinheiro, fator, mesAno, negativo, percentual } from '../../lib/formato'

function Num({ v, formatar, forte }: { v: Decimal; formatar: (v: Decimal) => string; forte?: boolean }) {
  const classes = ['num', forte ? 'num-strong' : '', negativo(v) ? 'neg' : ''].filter(Boolean).join(' ')
  return <td className={classes}>{formatar(v)}</td>
}

// Colunas com as letras da linha 16 do template. O frontend só formata: todos
// os valores vêm prontos da API (as mesmas fórmulas que a planilha grava).
export function TabelaCalculo({ calculo }: { calculo: Calculo }) {
  const lucro = percentual(calculo.parametros.lucro)
  const colunas: [string, string][] = [
    ['Valor PI líquido', 'a'],
    ['Fator', ''],
    ['Reajuste líquido', 'b'],
    ['ΔP', 'd'],
    ['Reajuste pelo ΔP', 'c = a·d'],
    ['Diferença', 'e = c − b'],
    ['Diferença sem lucro', `f = e·(1 − ${lucro})`],
  ]
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Mês</th>
            {colunas.map(([nome, letra]) => (
              <th key={nome} className="num">
                {nome}
                {letra && <span className="letra">{letra}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {calculo.familias.map((familia) => (
            <Fragment key={familia.familia}>
              <tr className="linha-familia">
                <td colSpan={8}>{familia.rotulo}</td>
              </tr>
              {familia.produtos.map((produto) => (
                <Fragment key={produto.descricao}>
                  <tr className="linha-produto">
                    <td colSpan={8}>{produto.descricao}</td>
                  </tr>
                  {produto.linhas.map((l) => (
                    <tr key={l.mes}>
                      <td>{mesAno(l.mes)}</td>
                      <Num v={l.a} formatar={dinheiro} />
                      <Num v={l.fator} formatar={fator} />
                      <Num v={l.b} formatar={dinheiro} />
                      <Num v={l.d} formatar={deltaP} />
                      <Num v={l.c} formatar={dinheiro} />
                      <Num v={l.e} formatar={dinheiro} />
                      <Num v={l.f} formatar={dinheiro} />
                    </tr>
                  ))}
                  <tr className="linha-subtotal">
                    <td colSpan={7}>Subtotal — {produto.descricao}</td>
                    <Num v={produto.subtotal} formatar={dinheiro} forte />
                  </tr>
                </Fragment>
              ))}
            </Fragment>
          ))}
          <tr className="linha-total">
            <td colSpan={7}>Total geral</td>
            <Num v={calculo.total} formatar={dinheiro} forte />
          </tr>
        </tbody>
      </table>
    </div>
  )
}
