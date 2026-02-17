#!/bin/bash
# fix_vm_main_ip.sh
# Define o IP 192.168.68.60 como principal e restaura os aliases .71.x

INTERFACE="enp1s0" # Confirmado pelo seu output anterior
MAIN_IP="192.168.68.60"
NETMASK="255.255.252.0"
GATEWAY="192.168.68.1"

# Faixa Adicional
IP_PREFIX="192.168.71"
START=200
END=214

echo "=== Corrigindo IP Principal da VM ==="
echo "Definindo $INTERFACE como estático: $MAIN_IP"

# Fazer backup do atual
cp /etc/network/interfaces /etc/network/interfaces.bak.fix

# Recriar arquivo
cat > interfaces.new <<EOF
# Configuração Fixa - Pterodactyl
source /etc/network/interfaces.d/*

auto lo
iface lo inet loopback

# IP Principal (Antigo DHCP, agora Estático para garantir)
auto $INTERFACE
iface $INTERFACE inet static
    address $MAIN_IP
    netmask $NETMASK
    gateway $GATEWAY
    dns-nameservers 8.8.8.8 1.1.1.1

EOF

# Adicionar Aliases (.200 a .214)
# Note: Usamos alias a partir de :0 ou :1. Vamos usar :0 para o primeiro alias.
INDEX=0
for (( i=$START; i<=$END; i++ ))
do
    echo "Adicionando alias $INTERFACE:$INDEX -> $IP_PREFIX.$i"
    cat >> interfaces.new <<EOF

auto $INTERFACE:$INDEX
iface $INTERFACE:$INDEX inet static
    address $IP_PREFIX.$i
    netmask $NETMASK
EOF
    ((INDEX++))
done

echo ""
echo "Aplicando nova configuração..."
sudo mv interfaces.new /etc/network/interfaces

echo "Reiniciando Networking..."
# Se vc estiver logado via .60, isso PODE derrubar sua conexão momentaneamente se o lease DHCP já tinha morrido.
sudo systemctl restart networking

echo "Feito! Verifique com 'ip addr'."
