#!/bin/bash
# setup_vm_ips.sh
# Execute este script DENTRO da VM Debian como root (ou sudo).
# Ele configura o IP principal (192.168.68.60) + 15 IPs estáticos (192.168.71.x).

# --- CONFIGURAÇÃO CORRIGIDA ---
# IP Principal da VM (Onde roda o Painel e SSH)
MAIN_IP="192.168.68.60"

# Faixa de IPs Secundários (Onde rodarão os Servidores de Jogo)
IP_PREFIX="192.168.71"
START_OCTET=200
NUM_IPS=15  # Vai de .200 até .214

# Rede
GATEWAY="192.168.68.1"
NETMASK="255.255.252.0" # /22 (Abrange 68.x até 71.x)

# O Debian 12 pode usar ens3, enp1s0 ou eth0. O script tentará detectar.
INTERFACE="eth0" 

# --- DETECÇÃO DE INTERFACE ---
DETECTED_IF=$(ip -o link show | awk -F': ' '{print $2}' | grep -v "lo" | grep -v "virbr" | head -n1)
if [ ! -z "$DETECTED_IF" ]; then
    INTERFACE=$DETECTED_IF
    echo "Interface detectada: $INTERFACE"
else
    echo "Não foi possível detectar a interface padrão. Usando $INTERFACE como fallback."
fi

CONFIG_FILE="/etc/network/interfaces"
BACKUP_FILE="/etc/network/interfaces.bak.$(date +%F_%T)"

echo "=== Configuração de IPs Estáticos (VM) ==="
echo "Interface: $INTERFACE"
echo "IP Principal: $MAIN_IP"
echo "IPs Secundários: $IP_PREFIX.$START_OCTET até $IP_PREFIX.$(($START_OCTET + $NUM_IPS - 1))"
echo "Máscara de Rede: $NETMASK"
echo "Gateway: $GATEWAY"
echo ""

# Backup
echo "Fazendo backup de $CONFIG_FILE..."
cp $CONFIG_FILE $BACKUP_FILE

# Criar nova configuração
echo "Gerando nova configuração..."

cat > ./interfaces.new <<EOF
# This file describes the network interfaces available on your system
# and how to activate them. For more information, see interfaces(5).

source /etc/network/interfaces.d/*

# The loopback network interface
auto lo
iface lo inet loopback

# The primary network interface (Painel/SSH)
auto $INTERFACE
iface $INTERFACE inet static
    address $MAIN_IP
    netmask $NETMASK
    gateway $GATEWAY
    # DNS do Google e Cloudflare
    dns-nameservers 8.8.8.8 1.1.1.1

EOF

# Loop para adicionar os IPs adicionais (Aliases)
# Vamos começar os aliases do índice 0 ou 1, mas como o principal já ocupa a interface base, aliases são :0, :1...
for (( i=0; i<$NUM_IPS; i++ ))
do
    CURRENT_OCTET=$((START_OCTET + i))
    CURRENT_IP="$IP_PREFIX.$CURRENT_OCTET"
    ALIAS_NUM=$i
    
    echo "Configurando alias $INTERFACE:$ALIAS_NUM com IP $CURRENT_IP..."
    
    cat >> ./interfaces.new <<EOF

auto $INTERFACE:$ALIAS_NUM
iface $INTERFACE:$ALIAS_NUM inet static
    address $CURRENT_IP
    netmask $NETMASK
EOF
done

echo ""
echo "=== Revisão da Configuração ==="
head -n 20 ./interfaces.new
echo "..."
echo ""
echo "ATENÇÃO: A máscara foi definida como $NETMASK (/22) para permitir comunicação com o Gateway $GATEWAY."
# Como será executado manualmente, pedimos confirmação
read -p "Deseja aplicar e reiniciar a rede? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mv ./interfaces.new $CONFIG_FILE
    
    echo "Reiniciando serviço de rede..."
    if systemctl restart networking; then
        echo "Sucesso! Verifique com 'ip addr'."
    else
        echo "ERRO ao reiniciar a rede. Restaurando backup..."
        cp $BACKUP_FILE $CONFIG_FILE
        systemctl restart networking
        echo "Backup restaurado."
    fi
else
    echo "Cancelado. O arquivo gerado está em ./interfaces.new"
fi
