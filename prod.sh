#!/bin/bash
#
# Produção neste servidor: PostgreSQL no Docker e a aplicação como serviço
# systemd. Os dois sobem sozinhos no boot e reiniciam se caírem. Pode ser rodado
# de novo (por exemplo, depois de um git pull) — reinstala e reinicia o serviço.
#
# Uso: ./setup.sh (uma vez) e depois ./prod.sh   (como usuário comum, sem sudo)

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PROJETO="$(pwd)"
USUARIO="$(id -un)"
PORTA=8000

log()  { echo ">> $*"; }
fail() { echo "ERRO: $*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || fail "Rode como usuário comum, sem sudo: ./prod.sh"

# Arquivos deixados por um 'sudo ./script' anterior ficam do root: o serviço,
# que roda como este usuário, não consegue usá-los.
if [ -n "$(find . -user root -print -quit 2>/dev/null)" ]; then
    log "Devolvendo a $USUARIO os arquivos do projeto que estão com o root..."
    sudo chown -R "$USUARIO:$(id -gn)" .
fi
if [ -f .venv/pyvenv.cfg ] && grep -q '^home = /root/' .venv/pyvenv.cfg; then
    log "Recriando .venv (o Python dele estava em /root)..."
    rm -rf .venv
fi

if [ -f "$HOME/.local/bin/env" ]; then
    . "$HOME/.local/bin/env"
fi
export PATH="$HOME/.local/bin:$PATH"

# 1. Pré-requisitos -----------------------------------------------------------

command -v uv >/dev/null || fail "uv não encontrado. Rode ./setup.sh primeiro."
[ -f .env ] || fail ".env não encontrado. Rode ./setup.sh primeiro."
grep -q TROQUE_ESTA_SENHA .env && fail ".env ainda contém TROQUE_ESTA_SENHA."

if docker info >/dev/null 2>&1; then DOCKER=(docker); else DOCKER=(sudo docker); fi
dc() { "${DOCKER[@]}" compose "$@"; }

# 2. Código e frontend atualizados ---------------------------------------------

log "Sincronizando dependências Python..."
uv sync --frozen
[ -x .venv/bin/uvicorn ] || fail ".venv/bin/uvicorn não encontrado depois do uv sync"

if [ ! -f frontend/dist/index.html ] || [ -n "$(find frontend/src frontend/index.html -newer frontend/dist/index.html -print -quit)" ]; then
    log "Construindo o frontend..."
    (cd frontend && npm ci && npm run build)
fi

# 3. PostgreSQL ---------------------------------------------------------------

sudo systemctl enable --now docker.service containerd.service >/dev/null

# O contêiner da aplicação (modo Docker completo) disputaria a porta 8000 e
# voltaria no boot; aqui a aplicação roda pelo systemd.
if dc ps -a --format '{{.Service}}' | grep -qx dnit-pdf-extractor; then
    log "Removendo o contêiner dnit-pdf-extractor (os volumes ficam)..."
    dc rm -sf dnit-pdf-extractor
fi

log "Subindo o PostgreSQL..."
dc up -d postgres
for i in $(seq 1 60); do
    [ "$(dc ps postgres --format '{{.Health}}' 2>/dev/null)" = "healthy" ] && break
    [ "$i" -eq 60 ] && fail "PostgreSQL não ficou saudável. Veja: docker compose logs postgres"
    sleep 1
done
log "PostgreSQL pronto (localhost:5433)"

# 4. Serviços systemd -----------------------------------------------------------

sudo tee /etc/systemd/system/dnit-postgres.service >/dev/null <<EOF
[Unit]
Description=DNIT PostgreSQL (Docker Compose)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${PROJETO}
ExecStart=/usr/bin/docker compose up -d postgres
ExecStop=/usr/bin/docker compose stop postgres
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

# Sem uv nem .bashrc no caminho do boot: o uvicorn do .venv é chamado direto, e a
# aplicação lê o .env sozinha (app/config.py).
sudo tee /etc/systemd/system/dnit-pdf-extractor.service >/dev/null <<EOF
[Unit]
Description=DNIT PDF Extractor (FastAPI)
After=network-online.target dnit-postgres.service
Wants=network-online.target dnit-postgres.service

[Service]
Type=simple
User=${USUARIO}
WorkingDirectory=${PROJETO}
ExecStartPre=/bin/bash -c 'until (exec 3<>/dev/tcp/127.0.0.1/5433) 2>/dev/null; do sleep 1; done'
ExecStart=${PROJETO}/.venv/bin/uvicorn main:app --host 0.0.0.0 --port ${PORTA} --workers 2
TimeoutStartSec=120
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable dnit-postgres.service dnit-pdf-extractor.service >/dev/null
sudo systemctl start dnit-postgres.service
sudo systemctl restart dnit-pdf-extractor.service

# 5. Verificação --------------------------------------------------------------

log "Aguardando a aplicação responder..."
for i in $(seq 1 60); do
    curl -fsS -o /dev/null "http://127.0.0.1:${PORTA}/openapi.json" 2>/dev/null && break
    if [ "$i" -eq 60 ]; then
        journalctl -u dnit-pdf-extractor.service -n 40 --no-pager || true
        fail "A aplicação não respondeu em 60 s (log acima)."
    fi
    sleep 1
done

IP="$(hostname -I | awk '{print $1}')"
cat <<EOF

Aplicação no ar: http://${IP}:${PORTA}/

Sobe sozinha no boot e reinicia se cair. Comandos úteis:

    systemctl status dnit-pdf-extractor          # situação
    journalctl -u dnit-pdf-extractor -f          # log ao vivo
    sudo systemctl restart dnit-pdf-extractor    # reiniciar
    docker compose ps                            # PostgreSQL
    ./check-env.sh                               # verificação completa

EOF
