# Pendências pós-frontend React

> Registro das pendências deixadas pela revisão final do plano
> `docs/superpowers/plans/2026-09-24-frontend-react.md` (branch `feat/frontend-react`,
> mesclado em `master` no commit `b16e9a7`) e de itens anteriores a esse plano.
> Cada item tem um dono (frontend/backend/repo) e o que falta decidir ou fazer.

## Achados Menores da revisão final (código)

1. **Faixa de cobertura sempre mostra o produto CAP.** `FaixaCobertura` (grade de
   índices ANP) lê `cobertura()` para CAP mesmo quando outro produto está
   selecionado na grade. `manuais`/registros mostrados não correspondem ao
   produto visível. Rotular explicitamente "CAP" ou tornar a cobertura por
   produto.
2. **Casos de borda de deep link no catálogo.**
   `?q=<código>` vindo da aba Medições é ignorado silenciosamente quando não há
   produtos (o diálogo *Adicionar códigos* exige produto selecionado);
   `?produto=<id inexistente>` cai silenciosamente no primeiro produto em vez de
   mostrar "não encontrado". Mostrar um aviso nos dois casos.
3. **Célula em branco na tabela de upload.** `TabelaLote`: um arquivo concluído
   com `contrato_id === null` (cabeçalho sem número de contrato) mostra a coluna
   Resultado vazia. Deveria dizer algo como "sem número de contrato no
   cabeçalho".
4. **Listas e rótulos duplicados entre frontend e backend.**
   - Região ANP existe em três lugares: `REGIOES_ANP` (`api/indices.ts`),
     `REGIOES_FIXAS` (código da grade) e `REGIOES` (backend).
   - Rótulos de bloqueio existem duas vezes: `ROTULO_BLOQUEIO` (`situacao.ts`) e
     `CAMPOS` (`bloqueio.ts`).
   - `aposUpload` usa a chave literal `['contrato']` em vez de uma chave de
     `chaves.ts`.
   - `chaves.igpDi(de, ate)` recebe parâmetros que nenhum chamador usa.
5. **Cores e tamanhos fora de `tokens.css`.** Restam valores crus
   (`rgba(147,0,10,0.18)`, `#0a74ee`, `#ffffff`, …) em `componentes.css`,
   `upload.css`, `telas.css` e `casca.css` — a maioria herdada de
   `app/static/css/style.css` na Tarefa 1, mas a regra do projeto é "só tokens".
6. **Downloads podem salvar um erro como arquivo.** Os links de planilha/CSV são
   `<a href download>` puros; uma resposta 4xx/422 do backend seria salva pelo
   navegador como `.xlsx`/`.csv`. Aceitável por agora (a tela de cálculo já
   mostra os índices faltantes antes do link aparecer), mas o link em si não se
   defende. Trocar por download via `pedir` (blob) resolveria de vez.
7. **Import cruzado de função privada no backend.** `medicoes_repo.py` importa
   `_padrao_ilike` de `catalogo.py` (nome com `_` = privado ao módulo). Tornar
   público ou mover para um helper compartilhado.

## Itens anteriores a este plano

8. **`.dockerignore` não exclui `.env` nem `data/`.** A imagem Docker pode levar
   o `.env` local (senha do banco) e o conteúdo de `data/` (artefatos de
   extração, backups) para dentro do build context. Adicionar as duas entradas.
9. **Bug confirmado com dados reais: perda de dinheiro quando um código de
   produto se repete no mesmo PDF/mês.** `medicoes_repo.gravar_itens` deduplica
   via `UNIQUE (contrato_id, codigo_servico, mes_medicao, source_file)` com
   `ON CONFLICT ... DO UPDATE` — a **última** linha processada sobrescreve as
   anteriores. Analisando os 51 PDFs reais fornecidos em `tmp/` (24/09/2026),
   dos códigos hoje associados a um produto do catálogo (CAP/emulsões, os que
   entram no ΔP), **22 casos em 51 arquivos** têm o mesmo código com valores
   financeiros diferentes e reais dentro do mesmo mês — a soma do que é
   descartado hoje chega a **R$ 2.998.897,12** de "Valor a PI Líquido" nesses
   22 casos.

   Causa raiz: o mesmo material recorre em mais de um **grupo de serviço** do
   PDF (ex.: "8,0 - AQUISIÇÃO … BETUMINOSO" → "8,1 - … PREÇOS NOVOS" → "21,0 -
   … NOVA ETAPA" quando o contrato é reajustado/re-baseado), e ainda numa
   seção de estorno ("23,0 - ESTORNOS/RESSARCIMENTOS/DESCONTOS", linhas
   "EST.QTDE.LQDA. …" com valor sempre zero). A chave de identidade da linha
   não inclui o grupo, então tudo colide na mesma linha do banco.

   **Exemplo completo verificado** — `tmp/45ª MP.pdf`, código `60112`
   (AQUISIÇÃO DE CAP 50/70), 7 ocorrências no mesmo arquivo:

   | Grupo (página) | O que é | Valor a PI Líquido |
   |---|---|---|
   | `8,0 - AQUISIÇÃO E TRANSPORTE DE MATERIAL BETUMINOSO` (pág. 3) | etapa antiga do contrato | R$ 0,00 |
   | `8,1 - … PREÇOS NOVOS` (pág. 3) | reprecificação da mesma etapa | R$ 0,00 |
   | `21,0 - … NOVA ETAPA` (pág. 5) | **a medição real deste mês** | **R$ 107.346,52** |
   | `23,0 - ESTORNOS/RESSARCIMENTOS/DESCONTOS` (pág. 5-6, 4 linhas) | linhas "EST.QTDE.LQDA. 8,0 60112"/"8,1 60112", auditoria, valor zero | R$ 0,00 cada |

   O grupo `23,0` vem depois do `21,0` na leitura do PDF; a última linha
   processada é uma das de estorno (zero), que sobrescreve os R$ 107.346,52
   reais — o banco fica com R$ 0,00 para esse material naquele mês. Outro
   exemplo (dois grupos reais, sem estorno): `tmp/10ª MEDIÇÃO PROVISÓRIA.pdf`,
   código `8300980`, grupo `2,0 - CONSERVAÇÃO CORRETIVA ROTINEIRA` (R$
   145.178,70) e grupo `3,0 - CONSERVAÇÃO PREVENTIVA PERIÓDICA` (R$
   197.208,20) — hoje só o segundo valor é gravado; a soma real é R$
   342.386,90.

   **Status: resolvido.** O usuário validou com um relatório completo
   (código, descrição, fator, valor, gerado dos 51 PDFs reais). Primeira
   regra proposta ("qualquer linha com Fator = 0 nunca entra no cálculo")
   foi **revisada e corrigida** antes de fechar: uma revisão focada (dado o
   impacto financeiro) achou, com dados reais do próprio banco, contratos com
   medições inteiras — não estornos — em que **todas** as ocorrências de um
   código têm `Fator = 0` (ex.: `rel_resumo_medicoes(44).pdf`, código `92704`
   AQUISIÇÃO DE CAP 50/70, ocorrência única, R$ 324.880,32, `Fator = 0` — é a
   primeira medição do material, antes do primeiro reajustamento, não um
   estorno). Descartar toda linha com `Fator = 0` incondicionalmente teria
   zerado essas medições reais, um erro pior que o bug original.

   **Regra final:** uma ocorrência com `Fator = 0` só é descartada quando
   existe, no mesmo (código, mês, arquivo), **outra** ocorrência com
   `Fator != 0` — nesse caso as ocorrências com `Fator != 0` são somadas e a
   de `Fator = 0` (o estorno/auditoria) sai do cálculo, mesmo carregando um
   valor real (há estornos com "Valor a PI Líquido" negativo, ex. `30ª
   MP.pdf` código `60112`: -R$ 82.238,50). Quando **todas** as ocorrências
   têm `Fator = 0` (nenhuma alternativa melhor existe), elas são mantidas e
   somadas como estão — é a única medição real que existe para aquele
   código naquele mês.

   Implementado em `medicoes_repo.gravar_itens`, com um aviso de log quando o
   `Fator` diverge entre as ocorrências não-descartadas do mesmo grupo (não
   deveria acontecer — confirmado sem exceção nos 51 PDFs reais — mas não
   deveria passar em silêncio se acontecer). Validado de ponta a ponta contra
   os 51 PDFs reais (via um contrato sintético, apagado depois). Testes
   cobrindo os quatro casos (soma de dois grupos reais, estorno com valor
   negativo descartado por ter alternativa, medição real única com Fator = 0
   mantida, reprocessamento não dobra a soma). Suíte completa: 329 passed, 9
   skipped.
10. **Branch remoto `feat/postgres-indices-delta-p` continua existindo** em
    `origin`, aparentemente já superado pelo trabalho atual. Confirmar que pode
    ser removido antes de apagar.
11. **`build_template.py` lê a planilha `Reequilíbrio - 26 - Contrato
    716-22.xlsx`.** Investigado nesta rodada: é o uso **legítimo e documentado**
    dessa planilha — `build_template.py` é a ferramenta manual que deriva o
    template do zero a partir da planilha de referência (`architecture.md`
    já a lista assim); a restrição do projeto é não usá-la em seed, fixture ou
    teste automatizado, e `build_template.py` não é nenhum dos três. **Não é um
    bug** — mantido como item resolvido/sem ação, registrado aqui só para
    encerrar a pendência formalmente.
12. **Servidor de mockup/companion do brainstorming.** Verificado: nenhum
    processo do companion, nenhum listener em portas de dev (5173/3000/8080)
    além do build do frontend em andamento no momento da checagem. **Não é um
    bug** — já estava parado.

## Perguntas para o usuário

- Item 10: ainda não decidido se remove o branch remoto
  `feat/postgres-indices-delta-p` agora ou depois.

## Dívida deixada pelo item 9

- **Dados já gravados no banco não se corrigem automaticamente.**
  `gravar_itens` só insere/atualiza, nunca apaga — reprocessar um PDF corrige
  as chaves que tinham alguma ocorrência descartada incorretamente, mas uma
  chave cujas ocorrências *todas* já foram gravadas (uma por uma, cada
  sobrescrevendo a anterior) só fica com o valor certo depois que o PDF for
  reenviado. Nenhuma migração de dados foi feita nesta rodada — se o banco de
  produção tiver contratos processados antes desta correção, os PDFs
  precisam ser reenviados (ou uma migração escrita) para os valores ficarem
  certos.
