#!/bin/bash
# fix_bridge_connection.sh
# Script para corrigir a conexão da Bridge br0, desativando a conexão conflitante atual.

INTERFACE="enp6s0"
BRIDGE_CONN="bridge-br0"
SLAVE_CONN="bridge-slave-enp6s0"

# 1. Identificar a conexão conflitante atual em enp6s0
CONFLICT_CONN=$(nmcli -t -f UUID,DEVICE con show --active | grep ":$INTERFACE" | cut -d: -fw1)

if [ -z "$CONFLICT_CONN" ]; then
    echo "Nenhuma conexão ativa encontrada em $INTERFACE."
    # Tenta subir a bridge mesmo assim
else
    echo "Conexão conflituosa detectada (UUID: $CONFLICT_CONN)."
    echo "Nome da conexão do conflito:"
    nmcli -t -f UUID,NAME con show | grep "$CONFLICT_CONN"
fi

echo ""
echo "=== Correção de Bridge ==="
echo "Este script irá:"
echo "1. Desativar a conexão atual em $INTERFACE"
echo "2. Ativar a conexão escrava da bridge ($SLAVE_CONN)"
echo "3. Verificar se a bridge ($BRIDGE_CONN) está ativa"
echo ""
echo "AVISO: Perda momentânea de conexão é esperada."
read -p "Deseja continuar? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelado."
    exit 1
fi

# Executar comandos em sequência para minimizar tempo offline
# Usamos 'nmcli con up' no slave, o que deve ativar o master automaticamente.
# Se falhar, tentamos subir o master.

echo "Aplicando correção..."

if [ ! -z "$CONFLICT_CONN" ]; then
    # Desativa a anterior E ativa a nova. 
    # Usando subshell ou grouping para garantir execução rápida
    (
        nmcli con down uuid "$CONFLICT_CONN"
        nmcli con up "$SLAVE_CONN"
        nmcli con up "$BRIDGE_CONN"
    )
else
    nmcli con up "$SLAVE_CONN"
    nmcli con up "$BRIDGE_CONN"
fi

echo ""
echo "=== Status Atual ==="
nmcli dev status
echo ""
echo "Se 'br0' estiver 'conectado', a correção funcionou."
