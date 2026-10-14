#!/bin/bash
#
# Prepara o dnit-pdf-extractor num servidor Ubuntu: instala o que faltar (Docker,
# uv, Node 24, Tesseract, cliente PostgreSQL 16, bibliotecas do OCR), cria o .env,
# sobe o PostgreSQL via Docker, cria o banco de testes, instala as dependências,
# constrói o frontend e carrega os preços da ANP. Pode ser rodado de novo.
#
# Uso: ./setup.sh        (como usuário comum; pede a senha do sudo quando precisa)

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

log()  { echo ">> $*"; }
fail() { echo "ERRO: $*" >&2; exit 1; }
tem()  { command -v "$1" >/dev/null 2>&1; }

[ "$(id -u)" -ne 0 ] || fail "Rode como usuário comum, sem sudo: ./setup.sh"

# Arquivos deixados por um 'sudo ./script' anterior ficam do root: o serviço,
# que roda como este usuário, não consegue usá-los.
if [ -n "$(find . -user root -print -quit 2>/dev/null)" ]; then
    log "Devolvendo a $USER os arquivos do projeto que estão com o root..."
    sudo chown -R "$USER:$(id -gn)" .
fi
if [ -f .venv/pyvenv.cfg ] && grep -q '^home = /root/' .venv/pyvenv.cfg; then
    log "Recriando .venv (o Python dele estava em /root)..."
    rm -rf .venv
fi

# O instalador do uv o coloca em ~/.local/bin e cria ~/.local/bin/env.
carregar_uv() {
    if [ -f "$HOME/.local/bin/env" ]; then
        . "$HOME/.local/bin/env"
    fi
    export PATH="$HOME/.local/bin:$PATH"
}
carregar_uv

APT_ATUALIZADO=0
apt_instalar() {
    if [ "$APT_ATUALIZADO" -eq 0 ]; then
        sudo apt-get update
        APT_ATUALIZADO=1
    fi
    sudo apt-get install -y "$@"
}
instalado() { dpkg -s "$1" >/dev/null 2>&1; }

# 1. Docker -------------------------------------------------------------------

if ! tem docker; then
    log "Instalando Docker..."
    apt_instalar ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
    APT_ATUALIZADO=0
    apt_instalar docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# Docker sobe sozinho no boot.
sudo systemctl enable --now docker.service containerd.service >/dev/null

# Grupo docker para as próximas sessões; nesta, se ainda não vale, usa sudo.
if ! id -nG "$USER" | grep -qw docker; then
    sudo usermod -aG docker "$USER"
    log "Usuário adicionado ao grupo docker (vale a partir do próximo login SSH)"
fi
if docker info >/dev/null 2>&1; then DOCKER=(docker); else DOCKER=(sudo docker); fi
dc() { "${DOCKER[@]}" compose "$@"; }
dc version >/dev/null || fail "plugin do Docker Compose v2 não encontrado"

# 2. uv -----------------------------------------------------------------------

if ! tem uv; then
    log "Instalando uv..."
    tem curl || apt_instalar curl
    curl -LsSf https://astral.sh/uv/install.sh | sh
    carregar_uv
    tem uv || fail "uv instalado, mas não encontrado em ~/.local/bin"
fi

# Link em /usr/local/bin: uv disponível também em 'ssh servidor comando',
# sob sudo e para qualquer serviço, sem depender do .bashrc.
for b in uv uvx; do
    if [ -x "$HOME/.local/bin/$b" ] && [ "$(readlink -f /usr/local/bin/$b 2>/dev/null)" != "$HOME/.local/bin/$b" ]; then
        sudo ln -sf "$HOME/.local/bin/$b" "/usr/local/bin/$b"
    fi
done

# 3. Node 24 ------------------------------------------------------------------

if ! tem node || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 24 ]; then
    log "Instalando Node.js 24..."
    tem curl || apt_instalar curl
    curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
    APT_ATUALIZADO=1
    sudo apt-get install -y nodejs
fi

# 4. Pacotes de sistema que a aplicação usa fora do Docker ---------------------
#
# Os mesmos do Dockerfile: Tesseract (OCR principal), libgl1/glib (EasyOCR) e o
# cliente PostgreSQL 16 do repositório PGDG para os backups. O cliente do Ubuntu
# é de outra versão maior, e um dump de cliente mais novo não restaura no 16.

FALTANDO=()
for p in tesseract-ocr tesseract-ocr-por libgl1 libglib2.0-0t64; do
    instalado "$p" || FALTANDO+=("$p")
done
if [ "${#FALTANDO[@]}" -gt 0 ]; then
    log "Instalando ${FALTANDO[*]}..."
    apt_instalar "${FALTANDO[@]}"
fi

if ! instalado postgresql-client-16; then
    log "Instalando postgresql-client-16 (PGDG)..."
    apt_instalar ca-certificates curl gnupg
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | sudo gpg --dearmor --yes -o /usr/share/keyrings/pgdg.gpg
    echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "$VERSION_CODENAME")-pgdg main" \
        | sudo tee /etc/apt/sources.list.d/pgdg.list >/dev/null
    APT_ATUALIZADO=0
    apt_instalar postgresql-client-16
fi

log "Dependências de sistema OK: docker, uv $(uv --version | cut -d' ' -f2), node $(node --version), tesseract, pg_dump 16"

# 5. .env ---------------------------------------------------------------------
#
# A senha precisa ser a mesma de POSTGRES_PASSWORD no docker-compose.yml.

if [ ! -f .env ]; then
    [ -f .env.example ] || fail ".env.example não encontrado"
    sed 's/TROQUE_ESTA_SENHA/dnit/g' .env.example > .env
    log ".env criado a partir de .env.example"
fi

definir_env() {
    if grep -qE "^$1=" .env; then
        sed -i "s#^$1=.*#$1=$2#" .env
    else
        echo "$1=$2" >> .env
    fi
}

# Fora do contêiner, /app não existe: backups vão para data/backups do projeto.
if grep -qE '^BACKUP_DIR=/app/' .env; then
    definir_env BACKUP_DIR "$(pwd)/data/backups"
    log "BACKUP_DIR ajustado para $(pwd)/data/backups"
fi
# pg_dump/pg_restore da mesma versão maior do servidor (16).
grep -qE '^PG_BIN=' .env || definir_env PG_BIN /usr/lib/postgresql/16/bin

# 6. PostgreSQL via Docker ----------------------------------------------------

log "Subindo o PostgreSQL..."
dc up -d postgres
for i in $(seq 1 60); do
    [ "$(dc ps postgres --format '{{.Health}}' 2>/dev/null)" = "healthy" ] && break
    [ "$i" -eq 60 ] && fail "PostgreSQL não ficou saudável. Veja: docker compose logs postgres"
    sleep 1
done
log "PostgreSQL pronto (localhost:5433)"

if dc exec -T postgres psql -U dnit -tAc "SELECT 1 FROM pg_database WHERE datname='dnit_test'" | grep -q 1; then
    log "Banco dnit_test já existe"
else
    dc exec -T postgres createdb -U dnit dnit_test
    log "Banco dnit_test criado"
fi

# 7. Dependências e frontend --------------------------------------------------

log "Instalando dependências Python (uv sync)..."
uv sync

log "Construindo o frontend..."
(cd frontend && npm ci && npm run build)

# 8. Carga inicial dos preços da ANP ------------------------------------------
#
# Rodar de novo não desfaz correções manuais.

log "Carregando os preços da ANP..."
uv run python scripts/seed_indices.py --anp tests/fixtures/anp_semanal.xls

cat <<'EOF'

Pronto. Próximos passos:

    ./prod.sh                                      # produção: sobe e mantém no boot
    uv run uvicorn main:app --reload --port 8000   # ou: servidor de desenvolvimento
    uv run pytest -q                               # testes

EOF
