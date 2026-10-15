#!/bin/bash
#
# Configura o acesso em rede ao dnit-pdf-extractor como um site normal:
# - dnsmasq para resolver reequilibrio.local (DNS local)
# - nginx como proxy reverso na porta 80
# - firewall (ufw) permitindo HTTP e DNS
#
# Depois: configure os clientes ou o roteador para usar este servidor como DNS,
# e eles poderão acessar http://reequilibrio.local sem nenhum software adicional.
#
# Uso: ./setup-network.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

log()  { echo ">> $*"; }
fail() { echo "ERRO: $*" >&2; exit 1; }
tem()  { command -v "$1" >/dev/null 2>&1; }

[ "$(id -u)" -ne 0 ] || fail "Rode como usuário comum, sem sudo: ./setup-network.sh"

NOME="reequilibrio"
PORTA_APP=8000

# Interface e IP vêm da rota padrão: é por ela que a rede local alcança este
# servidor. Pegar "o primeiro endereço" acertaria só quando nenhuma bridge do
# Docker (docker0, br-...) viesse antes da interface física.
IFACE=$(ip -4 route show default | awk '{for (i = 1; i < NF; i++) if ($i == "dev") { print $(i + 1); exit }}')
[ -n "$IFACE" ] || fail "Não encontrei a interface da rota padrão (sem rede configurada?)"
IP=$(ip -4 -o addr show dev "$IFACE" scope global | awk '{print $4}' | cut -d/ -f1 | head -1)

[ -n "$IP" ] || fail "Não consegui detectar o IP da interface $IFACE"

log "Configurando acesso em rede local:"
log "  Nome: ${NOME}.local e ${NOME}"
log "  IP: ${IP} (interface ${IFACE})"
log "  Aplicação na porta ${PORTA_APP}"

# 1. nginx como proxy reverso --------------------------------------------------

if ! tem nginx; then
    log "Instalando nginx..."
    sudo apt-get update
    sudo apt-get install -y nginx
fi

sudo tee /etc/nginx/sites-available/reequilibrio >/dev/null <<EOF
server {
    listen 80;
    server_name ${NOME}.local ${NOME} ${IP};

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:${PORTA_APP};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # SSE (Server-Sent Events) para progresso de upload. Sem a barra final:
    # "location /jobs/" faz o nginx redirecionar GET /jobs para /jobs/ (301),
    # rota que o FastAPI não tem — a lista de lotes anteriores dava 404.
    location /jobs {
        proxy_pass http://127.0.0.1:${PORTA_APP};
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/reequilibrio /etc/nginx/sites-enabled/reequilibrio
if [ -L /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
fi

sudo nginx -t || fail "Configuração do nginx inválida"
sudo systemctl enable --now nginx >/dev/null
sudo systemctl reload nginx

log "nginx configurado como proxy reverso (porta 80 → ${PORTA_APP})"

# 2. dnsmasq (servidor DNS local) ----------------------------------------------

if ! tem dnsmasq; then
    log "Instalando dnsmasq..."
    sudo apt-get install -y dnsmasq
fi

# Backup da configuração original
if [ -f /etc/dnsmasq.conf ] && [ ! -f /etc/dnsmasq.conf.original ]; then
    sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.original
fi

# Configuração do dnsmasq
sudo tee /etc/dnsmasq.d/reequilibrio.conf >/dev/null <<EOF
# DNS para reequilibrio.local e reequilibrio
address=/${NOME}.local/${IP}
address=/${NOME}/${IP}

# Escutar apenas na interface de rede local
interface=${IFACE}
bind-interfaces

# Encaminhar outras consultas DNS para servidores públicos
server=8.8.8.8
server=8.8.4.4

# Cache DNS
cache-size=1000

# Log (descomente para debug)
# log-queries
# log-facility=/var/log/dnsmasq.log
EOF

# Verificar se o systemd-resolved está ativo e pode conflitar com a porta 53
if systemctl is-active --quiet systemd-resolved; then
    log "Desabilitando systemd-resolved (conflita com dnsmasq na porta 53)..."
    sudo systemctl disable --now systemd-resolved

    # Restaurar resolv.conf para usar servidores DNS externos
    sudo rm -f /etc/resolv.conf
    sudo tee /etc/resolv.conf >/dev/null <<EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
EOF
    sudo chattr +i /etc/resolv.conf  # Impede o sistema de sobrescrever
fi

sudo systemctl enable --now dnsmasq >/dev/null
sudo systemctl restart dnsmasq

log "dnsmasq configurado como servidor DNS local"

# dig é usado na verificação abaixo; o dnsmasq não o traz.
if ! tem dig; then
    log "Instalando dig (bind9-dnsutils)..."
    sudo apt-get install -y bind9-dnsutils || sudo apt-get install -y dnsutils
fi

# 3. Firewall (ufw) -------------------------------------------------------------

if tem ufw; then
    if sudo ufw status | grep -q "Status: active"; then
        log "Abrindo portas no firewall (ufw)..."
        sudo ufw allow 80/tcp comment 'DNIT Reequilíbrio HTTP'
        sudo ufw allow 53/tcp comment 'DNS'
        sudo ufw allow 53/udp comment 'DNS'
        log "Firewall atualizado"
    else
        log "Firewall (ufw) não está ativo, pulando"
    fi
else
    log "ufw não instalado, pulando configuração de firewall"
fi

# 4. Verificação ----------------------------------------------------------------

sleep 2

if curl -fsS -o /dev/null "http://127.0.0.1/openapi.json"; then
    log "nginx respondendo corretamente"
else
    log "AVISO: nginx não está respondendo como esperado"
fi

if dig @127.0.0.1 ${NOME}.local +short 2>/dev/null | grep -q "$IP"; then
    log "DNS respondendo corretamente para ${NOME}.local"
else
    log "AVISO: DNS pode não estar funcionando"
fi

cat <<EOF

✅ Configuração concluída!

Servidor DNS configurado em: ${IP}:53
  - ${NOME}.local → ${IP}
  - ${NOME} → ${IP}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRÓXIMO PASSO: Configurar os clientes para usar este servidor DNS

Opção A: No roteador (recomendado - afeta todos os dispositivos)
  1. Acesse as configurações do roteador (geralmente 192.168.1.1 ou 192.168.0.1)
  2. Vá em DHCP ou Configurações de rede
  3. Configure o DNS primário como: ${IP}
  4. Salve e reinicie o roteador
  5. Reconecte os dispositivos à rede

Opção B: Em cada cliente individualmente

  Windows:
    1. Painel de Controle → Rede e Internet → Central de Rede
    2. Clique na conexão → Propriedades
    3. Protocolo TCP/IP versão 4 → Propriedades
    4. Use os seguintes endereços de servidor DNS: ${IP}

  macOS:
    1. Preferências → Rede
    2. Selecione a conexão → Avançado → DNS
    3. Adicione ${IP}

  Linux:
    1. Edite /etc/resolv.conf ou use NetworkManager
    2. Adicione: nameserver ${IP}

  iPhone/iPad:
    1. Ajustes → Wi-Fi → (i) ao lado da rede
    2. Configure DNS → Manual
    3. Adicione ${IP}

  Android:
    1. Configurações → Wi-Fi → Conexão atual → Avançado
    2. DNS 1: ${IP}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Depois da configuração, acesse:
  http://${NOME}.local/
  http://${NOME}/
  http://${IP}/

Testar DNS de outro computador:
  nslookup ${NOME}.local ${IP}
  dig @${IP} ${NOME}.local

Comandos úteis:
  sudo systemctl status nginx dnsmasq
  sudo journalctl -u dnsmasq -f          # logs do DNS
  sudo journalctl -u nginx -f            # logs do nginx
  dig @${IP} ${NOME}.local               # testar resolução DNS

EOF
