# DNIT PDF Extractor

Aplicação web que transforma os PDFs de **"Resumo da Medição"** do DNIT na
**planilha de Reequilíbrio dos Materiais Betuminosos**, com os cálculos
auditáveis célula por célula.

O trabalho que antes era feito à mão — abrir cada medição, copiar valores para o
Excel, procurar os preços da ANP e o IGP-DI do mês, calcular o ΔP e montar a
planilha — passa a ser: subir os PDFs, cadastrar o que não está neles e baixar o
arquivo.

## O que a aplicação faz

**Extração dos PDFs.** Aceita vários arquivos de uma vez. PDFs com texto são
lidos com `pdfplumber`; os digitalizados caem no caminho de OCR
(Tesseract, com EasyOCR como reserva). O processamento roda em segundo plano e o
progresso de cada arquivo aparece na tela em tempo real.

**Persistência em PostgreSQL.** Contrato, itens de medição, catálogo de produtos
e a série de índices ficam no banco. Reprocessar o mesmo PDF não duplica nada e
não sobrescreve o que o usuário corrigiu à mão.

**Catálogo de produtos por código de serviço.** O código é a chave confiável — o
OCR corrompe a descrição, nunca o código. O usuário cadastra os produtos que
entram na planilha, com a descrição que quiser e a família (*Aquisição de CAP* ou
*Aquisição de Emulsões*), e associa a eles **alguns** códigos extraídos (o
`8300980`, "AQUISIÇÃO DE CIMENTO ASFÁLTICO CAP 50/70" no PDF, pode sair como
"AQUISIÇÃO DE CAP 50/70"). Código sem associação simplesmente fica fora do
cálculo: não é pendência e não bloqueia nada. A associação vale para tudo o que
já foi extraído, sem reprocessar PDFs.

**ΔP automático.** A variação do preço do produtor (art. 16) é calculada pela
aplicação a partir dos preços semanais da ANP e do IGP-DI, sempre contra a *Data
Base* do contrato. Cada família (CAP e EMULSÕES) tem a sua região da ANP,
cadastrada no contrato. O preço do mês é o da semana que contém o dia 15 do mês
anterior; uma semana sem cotação, ou um índice ainda não cadastrado, **recusa** o
cálculo com a lista do que falta — nunca vira zero.

**Índices globais, editáveis por qualquer usuário.** Os preços da ANP e o IGP-DI
não pertencem a contrato nenhum. Podem ser corrigidos um a um ou importados em
massa: o `.xls` de preços semanais publicado pela ANP e um template próprio para o
IGP-DI, que a aplicação gera já preenchido com o que está no banco. Toda
importação tem prévia, é tudo ou nada e **preserva as correções manuais**, a menos
que se peça para sobrescrevê-las. As duas séries também podem ser exportadas em
CSV ou XLSX.

**Simulação de região.** Na exportação, a região de cada família pode ser trocada
só para aquela geração, sem alterar o cadastro; o arquivo sai com `SIMULACAO` no
nome. Para comparar regiões, exporta-se duas vezes.

**API REST.** Tudo o que o cálculo usa — contratos, catálogo, índices, cálculo e
planilha — está em `/api/v1`, utilizável por `curl` ou por qualquer cliente, com a
documentação interativa em `/docs`.

**Planilha com fórmulas vivas.** A exportação é gerada a partir de um template
`.xlsx` que o próprio usuário mantém no Excel. As colunas calculadas saem como
**fórmulas** (`=TRUNC(E18*D18,2)`, `=D18*G18`, `=H18-F18`, `=I18*(1-0.0511)`),
com subtotal por produto e total geral; só o ΔP entra como valor. A **memória de
cálculo** é preservada como equação nativa, vetorial e imprimível.

**Uma trilha de seis etapas.** Em qualquer tela, o cabeçalho mostra em que ponto
o contrato está — upload, cadastro, região da ANP, códigos pendentes, memória de
cálculo, exportação — e cada etapa leva à tela que a resolve. Quando a planilha
está bloqueada, o motivo aparece junto do botão, não em outro lugar.

**Cadastro do contrato.** Os campos que nenhum PDF traz (Edital, Rodovia, Trecho,
Subtrecho, Segmento, Extensão, Contratada) são cadastrados por contrato e
preenchem o cabeçalho da planilha. A *Data Base* vem sugerida pelo PDF e pode ser
corrigida; a região da ANP de cada família é obrigatória para calcular.

**Templates e backup pela interface.** Quem roda em Docker não precisa de
`docker cp` nem de terminal: enviar, baixar, ativar e excluir templates, e gerar,
listar, baixar, enviar, restaurar e excluir backups do banco — tudo por tela. O
backup automático roda sozinho no intervalo configurado.

## Telas

| Endereço | O que é |
|---|---|
| `/` | Upload dos PDFs, progresso e download dos resultados da extração |
| `/dashboard` | Reequilíbrio: cálculo na tela, cadastro do contrato, códigos, índices, templates e backup |
| `/docs` | Documentação interativa da API REST (`/api/v1`), gerada pelo FastAPI |

## Requisitos

- **Python 3.12** (fixado em `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** para as dependências
- **Docker** e **Docker Compose** — o PostgreSQL vem daí, inclusive para os testes
- **Tesseract OCR** com o pacote de português, para PDFs digitalizados
  (`apt install tesseract-ocr tesseract-ocr-por`). Sem ele a aplicação recorre ao
  EasyOCR, que é mais lento.
- **Cliente PostgreSQL 16** (`pg_dump`/`pg_restore`), apenas para os backups.
  A versão maior precisa ser a mesma do servidor — ver *Backups* abaixo.

## Setup em um ambiente novo

```bash
# 1. Dependências (inclui as de desenvolvimento)
uv sync

# 2. Variáveis de ambiente
cp .env.example .env
#    Troque TROQUE_ESTA_SENHA nas duas URLs de conexão. A senha precisa ser a
#    mesma de POSTGRES_PASSWORD no docker-compose.yml.

# 3. Banco de dados (fica na porta 5433 do host)
docker compose up -d postgres

# 4. Banco usado pelos testes
docker compose exec postgres createdb -U dnit dnit_test

# 5. Carga inicial dos preços da ANP (cópia versionada do arquivo oficial)
uv run python scripts/seed_indices.py --anp tests/fixtures/anp_semanal.xls

# 6. Servidor de desenvolvimento
uv run uvicorn main:app --reload --port 8000
```

As migrações são aplicadas na subida da aplicação, e o template inicial da
planilha é instalado no banco na primeira execução. Não há passo manual de
schema.

Rodando fora do Docker, aponte a `DATABASE_URL` para `localhost:5433`.

O seed grava todos os produtos do arquivo da ANP (o cálculo usa só o CAP 50/70).
O IGP-DI não vem de arquivo público padronizado: baixe o template em
`GET /api/v1/indices/igp-di/template`, preencha os meses e importe-o por
`POST /api/v1/indices/igp-di/importar` ou por
`uv run python scripts/seed_indices.py --sem-anp --igp-di <arquivo>`. Rodar o seed
de novo não desfaz correções manuais. Arquivos mais novos da ANP entram por
`POST /api/v1/indices/anp/importar`.

Depois disso: suba os PDFs em `http://localhost:8000/`, complete o cadastro do
contrato e as regiões da ANP, associe os códigos de CAP e de emulsão a produtos
do catálogo e baixe a planilha — pelo `/dashboard` ou pela API (`/docs`).

PDFs de exemplo vão em `tmp/` (não versionado).

## Testes

A suíte precisa de um PostgreSQL de verdade: o schema `public` do banco
`dnit_test` é derrubado e recriado a partir de `migrations/` a cada teste.

```bash
docker compose up -d postgres
uv run pytest -v
```

O teste ponta a ponta (`tests/test_e2e_reequilibrio.py`) importa o arquivo
oficial da ANP e leva alguns segundos. Ele usa só as fixtures versionadas em
`tests/fixtures/`, que incluem o ΔP calculado de forma independente no Excel como
oráculo.

Os testes de backup se auto-ignoram quando não há um `pg_dump` compatível no
`PATH`. Se a máquina tiver um cliente de versão maior que o servidor, aponte para
o de versão 16:

```bash
PG_BIN=/usr/lib/postgresql/16/bin uv run pytest -q
```

## Produção

```bash
docker compose up -d
```

Sobe o banco e a aplicação, com volumes nomeados para o PostgreSQL (`pgdata`) e
para os artefatos de extração e backups (`appdata`) — ambos necessários para o
estado sobreviver ao contêiner.

Fora do Compose, `--workers 2` é seguro: a aplicação não guarda estado em
memória e as tarefas periódicas são protegidas por *advisory locks* do
PostgreSQL, então só um worker executa cada uma.

## Backups

`pg_dump -Fc` no diretório `BACKUP_DIR`, mantendo os `BACKUP_RETENTION` mais
recentes, a cada `BACKUP_INTERVAL_HOURS`. Um único arquivo contém tudo o que é do
usuário: índices, contratos, itens de medição e os templates do Excel.

Restaurar é destrutivo, então exige digitar o nome do backup para confirmar,
valida o arquivo com `pg_restore --list` antes de encostar no banco e grava um
dump de segurança do estado atual primeiro.

**Atenção à versão do cliente:** o `pg_dump` grava diretivas da própria versão,
então um dump gerado por um cliente mais novo que o servidor não pode ser
restaurado (o PG 17+ emite `SET transaction_timeout`, que o 16 não conhece). A
aplicação se recusa a gerar um dump nessa situação; use `PG_BIN` para apontar
para o cliente correspondente ao servidor.

## Estrutura do projeto

```
main.py            Ponto de entrada (main:app)
migrations/        Migrações SQL numeradas, aplicadas na subida
scripts/           Carga inicial dos índices, geração das fixtures do teste
                   ponta a ponta e reconstrução do template
app/
├── routers/       Rotas HTTP: upload, jobs, admin, reequilíbrio e a API REST
│                  em api/ (/api/v1)
├── services/      Regra de negócio: extração, repositórios, ΔP, exportação, backup
├── dashboard/     Aplicação Dash em /dashboard
├── templates/     HTML (Jinja2) da página de upload
├── templates_xlsx/Template inicial da planilha (semente do banco)
└── static/        CSS, JS e fontes (Inter, JetBrains Mono, Material Symbols
                   Outlined) hospedadas localmente — sem CDN
tests/             Suíte pytest; fixtures/ com índices reais e o oráculo do ΔP
```

Detalhes de cada camada estão em [.claude/rules/](.claude/rules/):
[arquitetura](.claude/rules/architecture.md),
[backend](.claude/rules/backend.md),
[frontend](.claude/rules/frontend.md),
[deployment](.claude/rules/deployment.md) e
[documentação](.claude/rules/documentation.md).
