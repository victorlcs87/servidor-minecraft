#!/bin/bash

# Este script agora é apenas um wrapper para a inteligência de busca do Python
# Ele chama o modo --auto-scan que localiza todos os servidores e instala os addons pendentes.

SERVER_DIR="$(pwd)"
INSTALLER_SCRIPT="${SERVER_DIR}/bedrock_addon_installer.py"

if [ -f "$INSTALLER_SCRIPT" ]; then
    # Instala dependências silenciosamente se necessário
    pip3 install --user --break-system-packages rich InquirerPy > /dev/null 2>&1
    
    # Chama o modo inteligente de scan
    python3 "$INSTALLER_SCRIPT" --auto-scan
else
    echo "[Auto-Install] Script instalador não encontrado em $INSTALLER_SCRIPT"
fi
