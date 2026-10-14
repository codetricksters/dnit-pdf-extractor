#!/bin/bash
#
# Testa a configuração DNS. Execute este script no seu computador (não no servidor).
#
# Linux/macOS: salve como test-dns.sh, chmod +x test-dns.sh, ./test-dns.sh
# Windows: use Git Bash ou WSL

SERVIDOR_DNS="192.168.10.20"
NOME="reequilibrio.local"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Teste de DNS - reequilibrio.local"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Detectar sistema operacional
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
else
    OS="Windows/Outros"
fi

echo "Sistema: $OS"
echo "Servidor DNS esperado: $SERVIDOR_DNS"
echo

# 1. Testar resolução diretamente no servidor DNS
echo "1️⃣  Testando resolução DNS diretamente no servidor $SERVIDOR_DNS..."
if command -v dig >/dev/null 2>&1; then
    RESULTADO=$(dig @$SERVIDOR_DNS $NOME +short 2>/dev/null)
    if [ -n "$RESULTADO" ]; then
        echo "   ✅ DNS do servidor responde: $NOME → $RESULTADO"
    else
        echo "   ❌ DNS do servidor NÃO responde"
        echo "   → Verifique se o servidor está acessível: ping $SERVIDOR_DNS"
        exit 1
    fi
elif command -v nslookup >/dev/null 2>&1; then
    RESULTADO=$(nslookup $NOME $SERVIDOR_DNS 2>/dev/null | grep 'Address:' | tail -1 | awk '{print $2}')
    if [ -n "$RESULTADO" ]; then
        echo "   ✅ DNS do servidor responde: $NOME → $RESULTADO"
    else
        echo "   ❌ DNS do servidor NÃO responde"
        exit 1
    fi
else
    echo "   ⚠️  dig/nslookup não disponível, pulando teste direto"
fi

echo

# 2. Verificar DNS configurado neste computador
echo "2️⃣  Verificando qual DNS este computador está usando..."

if [ "$OS" = "macOS" ]; then
    DNS_ATIVO=$(scutil --dns | grep 'nameserver\[0\]' | head -1 | awk '{print $3}')
elif [ "$OS" = "Linux" ]; then
    if [ -f /etc/resolv.conf ]; then
        DNS_ATIVO=$(grep '^nameserver' /etc/resolv.conf | head -1 | awk '{print $2}')
    fi
else
    DNS_ATIVO="(não detectado automaticamente)"
fi

if [ "$DNS_ATIVO" = "$SERVIDOR_DNS" ]; then
    echo "   ✅ Este computador está usando o DNS correto: $DNS_ATIVO"
else
    echo "   ❌ Este computador está usando: $DNS_ATIVO"
    echo "   → Precisa ser: $SERVIDOR_DNS"
    echo
    echo "   AÇÃO NECESSÁRIA: Configure este computador para usar $SERVIDOR_DNS como DNS"
fi

echo

# 3. Testar resolução do nome usando o DNS configurado neste computador
echo "3️⃣  Testando se este computador consegue resolver $NOME..."

if command -v dig >/dev/null 2>&1; then
    RESULTADO=$(dig $NOME +short 2>/dev/null)
elif command -v nslookup >/dev/null 2>&1; then
    RESULTADO=$(nslookup $NOME 2>/dev/null | grep 'Address:' | tail -1 | awk '{print $2}')
elif command -v host >/dev/null 2>&1; then
    RESULTADO=$(host $NOME 2>/dev/null | grep 'has address' | awk '{print $4}')
fi

if [ -n "$RESULTADO" ] && [ "$RESULTADO" = "$SERVIDOR_DNS" ]; then
    echo "   ✅ $NOME resolve para $RESULTADO"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 SUCESSO! Você pode acessar: http://$NOME/"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "   ❌ $NOME NÃO resolve ou resolve incorretamente"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "❌ CONFIGURAÇÃO NECESSÁRIA"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo "Configure este computador para usar $SERVIDOR_DNS como servidor DNS:"
    echo

    if [ "$OS" = "macOS" ]; then
        echo "macOS:"
        echo "  1. Preferências do Sistema → Rede"
        echo "  2. Selecione sua conexão → Avançado → DNS"
        echo "  3. Clique em + e adicione: $SERVIDOR_DNS"
        echo "  4. Arraste para o topo da lista"
        echo "  5. Clique em OK e depois em Aplicar"

    elif [ "$OS" = "Linux" ]; then
        echo "Linux (NetworkManager):"
        echo "  1. Configurações → Rede"
        echo "  2. Clique no ícone de engrenagem da sua conexão"
        echo "  3. Aba IPv4 → DNS → Desative 'Automático'"
        echo "  4. Adicione: $SERVIDOR_DNS"
        echo "  5. Clique em Aplicar"
        echo
        echo "Linux (linha de comando):"
        echo "  sudo nano /etc/resolv.conf"
        echo "  Adicione no topo: nameserver $SERVIDOR_DNS"

    else
        echo "Windows:"
        echo "  1. Painel de Controle → Rede e Internet → Central de Rede"
        echo "  2. Clique na conexão → Propriedades"
        echo "  3. Protocolo TCP/IP versão 4 → Propriedades"
        echo "  4. Use os seguintes endereços de servidor DNS: $SERVIDOR_DNS"
        echo "  5. Clique em OK"
    fi

    echo
    echo "OU configure no roteador (afeta todos os dispositivos):"
    echo "  1. Acesse o roteador (geralmente 192.168.1.1 ou 192.168.0.1)"
    echo "  2. Encontre as configurações de DHCP/DNS"
    echo "  3. Configure DNS primário: $SERVIDOR_DNS"
    echo "  4. Salve e reinicie o roteador"
    echo
fi
