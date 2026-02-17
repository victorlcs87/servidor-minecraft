#!/bin/bash
# setup_host_bridge.sh
# Cria uma bridge br0 usando a interface física ethernet detectada.

# Nome da interface física (detectada anteriormente como enp6s0, mas vamos confirmar)
PHYSICAL_IF="enp6s0"
BRIDGE_NAME="br0"
CONN_NAME="bridge-br0"
SLAVE_NAME="bridge-slave-$PHYSICAL_IF"

echo "=== Configuração de Bridge KVM ==="
echo "Interface Física: $PHYSICAL_IF"
echo "Nome da Bridge: $BRIDGE_NAME"
echo ""
echo "AVISO: Isso pode desconectar sua rede temporariamente."
read -p "Deseja continuar? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelado."
    exit 1
fi

# 1. Criar a conexão da Bridge
echo "Criando bridge $BRIDGE_NAME..."
nmcli con add type bridge ifname $BRIDGE_NAME con-name $CONN_NAME

# 2. Desativar STP (Spanning Tree Protocol) para evitar delays na VM (opcional, mas bom pra home lab)
nmcli con modify $CONN_NAME bridge.stp no

# 3. Adicionar a interface física como escrava (slave)
echo "Adicionando $PHYSICAL_IF à bridge..."
nmcli con add type bridge-slave ifname $PHYSICAL_IF master $CONN_NAME con-name $SLAVE_NAME

# 4. Configurar IP da Bridge (DHCP ou fixo? Vamos manter o padrão DHCP da rede atual)
# O NetworkManager deve migrar o IP da interface física para a bridge automaticamente via DHCP.

# 5. Ativar a conexão
echo "Ativando conexão..."
nmcli con up $CONN_NAME

echo ""
echo "=== Configuração Concluída ==="
echo "Verifique sua conexão com 'ip addr' e 'ping google.com'."
echo "No Virt-Manager, configure a NIC da VM para usar 'Bridge device: $BRIDGE_NAME'."
