#!/bin/bash
#
# Verifica se o servidor está pronto e a aplicação no ar. Não altera nada.
#
# Uso: ./check-env.sh

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -f "$HOME/.local/bin/env" ]; then
    . "$HOME/.local/bin/env"
fi

FALHAS=0
ok()   { echo "  ok    $*"; }
erro() { echo "  FALTA $*"; FALHAS=$((FALHAS + 1)); }
checar() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else erro "$1${3:+ -> $3}"; fi; }

echo "Ferramentas"
checar "uv $(uv --version 2>/dev/null | cut -d' ' -f2)"  "command -v uv"                     "./setup.sh"
checar "uv fora do login (/usr/local/bin/uv)"             "test -x /usr/local/bin/uv"         "./setup.sh"
checar "node $(node --version 2>/dev/null)"              "node -e 'process.exit(Number(process.versions.node.split(\".\")[0] < 24))'" "./setup.sh"
checar "docker sem sudo"                                 "docker info"                        "faça logout/login no SSH"
checar "tesseract com português"                         "tesseract --list-langs 2>&1 | grep -qx por" "./setup.sh"
checar "pg_dump 16"                                      "/usr/lib/postgresql/16/bin/pg_dump --version" "./setup.sh"

echo "Projeto"
checar ".env"                                            "test -f .env"                       "./setup.sh"
checar "BACKUP_DIR fora de /app"                         "! grep -qE '^BACKUP_DIR=/app/' .env" "./setup.sh"
checar "nenhum arquivo do projeto com o root"            "test -z \"\$(find . -user root -print -quit)\"" "./setup.sh"
checar ".venv executável por $(id -un)"                  ".venv/bin/python -c ''"             "./setup.sh"
checar "frontend/dist"                                   "test -f frontend/dist/index.html"   "cd frontend && npm run build"

echo "Serviços"
checar "docker habilitado no boot"                       "systemctl is-enabled docker"        "./prod.sh"
checar "PostgreSQL saudável"                             "docker compose ps postgres --format '{{.Health}}' | grep -qx healthy" "./prod.sh"
checar "dnit-postgres habilitado no boot"                "systemctl is-enabled dnit-postgres" "./prod.sh"
checar "dnit-pdf-extractor habilitado no boot"           "systemctl is-enabled dnit-pdf-extractor" "./prod.sh"
checar "dnit-pdf-extractor rodando"                      "systemctl is-active dnit-pdf-extractor" "journalctl -u dnit-pdf-extractor -n 50"
checar "aplicação responde na porta 8000"                "curl -fsS http://127.0.0.1:8000/openapi.json" "journalctl -u dnit-pdf-extractor -n 50"

echo
if [ "$FALHAS" -eq 0 ]; then echo "Tudo certo."; else echo "$FALHAS item(ns) com problema."; exit 1; fi
