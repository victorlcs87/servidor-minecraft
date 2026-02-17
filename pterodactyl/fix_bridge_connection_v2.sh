#!/bin/bash
# fix_bridge_connection_v2.sh
# Versão corrigida e mais agressiva para garantir que a Bridge assuma.

INTERFACE="enp6s0"
BRIDGE_CONN="bridge-br0"
SLAVE_CONN="bridge-slave-enp6s0"

# 1. Identificar a conexão conflitante atual (Corrigido o cut)
# Procuramos qual conexão está ativa no dispositivo físico
CONFLICT_UUID=$(nmcli -t -f UUID,DEVICE con show --active | grep ":$INTERFACE" | cut -d: -f1)

echo "=== Correção de Bridge v2 ==="
echo "Interface Alvo: $INTERFACE"

if [ -z "$CONFLICT_UUID" ]; then
    echo "Nenhuma conexão ativa encontrada em $INTERFACE (ou já desconectada)."
else
    # Verifica o nome
    CONFLICT_NAME=$(nmcli -t -f UUID,NAME con show | grep "$CONFLICT_UUID" | cut -d: -f2)
    echo "Conexão Conflituosa Detectada:"
    echo "  Nome: $CONFLICT_NAME"
    echo "  UUID: $CONFLICT_UUID"
    
    # Previne que ela volte sozinha
    echo "Desativando autoconnect da conexão conflitante..."
    nmcli con mod "$CONFLICT_UUID" connection.autoconnect no
fi

echo ""
echo "Este script irá:"
echo "1. Baixar a conexão conflitante (se houver)"
echo "2. Subir a conexão escrava ($SLAVE_CONN)"
echo "3. Subir a bridge ($BRIDGE_CONN)"
echo ""
read -p "Deseja continuar? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelado."
    exit 1
fi

echo "Aplicando mudanças..."

# Sequência de comandos
if [ ! -z "$CONFLICT_UUID" ]; then
    nmcli con down "$CONFLICT_UUID"
fi

# Garante que a escrava e a bridge subam
nmcli con up "$SLAVE_CONN"
nmcli con up "$BRIDGE_CONN"

echo ""
echo "=== Status Final ==="
nmcli dev status
echo ""
echo "Verifique se 'br0' está 'conectado' e 'enp6s0' está associado a '$BRIDGE_CONN' ou '$SLAVE_CONN'."
