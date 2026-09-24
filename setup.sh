#!/bin/bash
#
# Sobe o dnit-pdf-extractor num ambiente novo: verifica as dependências de
# sistema, cria o .env, sobe o PostgreSQL via Docker, prepara o banco de testes,
# instala as dependências Python e carrega a série histórica de índices.
#
# Uso: ./setup.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

log()  { echo ">> $1"; }
fail() { echo "ERRO: $1" >&2; exit 1; }

# 1. Dependências de sistema -------------------------------------------------

command -v docker >/dev/null 2>&1 || fail "docker não encontrado. Instale o Docker antes de continuar."
docker compose version >/dev/null 2>&1 || fail "'docker compose' não encontrado (precisa do plugin do Compose v2)."
command -v uv >/dev/null 2>&1 || fail "uv não encontrado. Instale em https://docs.astral.sh/uv/"

log "Dependências de sistema OK (docker, docker compose, uv)"

# 2. .env ---------------------------------------------------------------------
#
# docker-compose.yml define POSTGRES_PASSWORD=dnit para o serviço postgres, e
# o fluxo de desenvolvimento documentado no README roda a aplicação fora do
# Docker apontando para localhost:5433 — então a senha do .env precisa ser a
# mesma. Não há segredo real aqui: é a senha de um Postgres que só escuta em
# localhost, para desenvolvimento.

if [ -f .env ]; then
    log ".env já existe, mantendo o que está lá"
else
    [ -f .env.example ] || fail ".env.example não encontrado"
    sed 's/TROQUE_ESTA_SENHA/dnit/g' .env.example > .env
    log ".env criado a partir de .env.example (senha alinhada com docker-compose.yml)"
fi

# 3. PostgreSQL via Docker ----------------------------------------------------

log "Subindo o PostgreSQL (docker compose up -d postgres)..."
docker compose up -d postgres

log "Esperando o PostgreSQL ficar saudável..."
for i in $(seq 1 30); do
    status=$(docker compose ps postgres --format '{{.Health}}' 2>/dev/null || true)
    [ "$status" = "healthy" ] && break
    sleep 1
    [ "$i" -eq 30 ] && fail "PostgreSQL não ficou saudável a tempo. Veja: docker compose logs postgres"
done
log "PostgreSQL pronto (localhost:5433)"

# 4. Banco usado pelos testes --------------------------------------------------

if docker compose exec -T postgres psql -U dnit -tAc "SELECT 1 FROM pg_database WHERE datname='dnit_test'" | grep -q 1; then
    log "Banco dnit_test já existe"
else
    docker compose exec -T postgres createdb -U dnit dnit_test
    log "Banco dnit_test criado"
fi

# 5. Dependências Python -------------------------------------------------------

log "Instalando dependências Python (uv sync)..."
uv sync

# 6. Carga inicial da série histórica de índices ------------------------------

log "Carregando a série histórica de índices (CAP 50/70)..."
uv run python scripts/seed_indices.py

cat <<'EOF'

Tudo pronto. Para rodar o servidor de desenvolvimento:

    uv run uvicorn main:app --reload --port 8000

Depois, no navegador: http://localhost:8000/

Para rodar os testes (o mesmo PostgreSQL do passo anterior já serve):

    uv run pytest -v

EOF
