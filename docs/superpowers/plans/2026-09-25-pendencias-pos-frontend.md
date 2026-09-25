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
9. **Política de linhas duplicadas dentro de um mesmo PDF não está decidida.**
   `medicoes_repo.gravar_itens` já deduplica entre arquivos diferentes via
   `UNIQUE (contrato_id, codigo_servico, mes_medicao, source_file)`, mas não há
   uma decisão registrada sobre o que fazer quando o **mesmo PDF** produz duas
   linhas para o mesmo `codigo_servico`/mês (erro de extração vs. dado legítimo
   do PDF?). Precisa de decisão de negócio antes de codar — ver seção
   "Perguntas para o usuário" abaixo.
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

- Item 9 precisa de uma decisão de negócio antes de qualquer código: quando o
  **mesmo PDF** tem duas linhas para o mesmo `codigo_servico` no mesmo mês,
  isso deveria ser: (a) um erro 422 que recusa o arquivo, (b) manter a última
  linha (comportamento atual do `ON CONFLICT ... DO UPDATE`, silencioso), ou
  (c) somar/registrar as duas como medições distintas? Depende de como o PDF
  real do DNIT costuma representar isso.
