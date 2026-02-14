#!/bin/bash

# Diretórios
SERVER_DIR="/var/opt/minecraft/crafty/crafty-4/servers"
AUTO_INSTALL_DIR="${SERVER_DIR}/addons_auto_install"
PROCESSED_DIR="${AUTO_INSTALL_DIR}/processed"
INSTALLER_SCRIPT="${SERVER_DIR}/bedrock_addon_installer.py"

# Verifica se a pasta de auto-install existe
if [ -d "$AUTO_INSTALL_DIR" ]; then
    echo "[Auto-Install] Verificando novos addons em $AUTO_INSTALL_DIR..."
    
    # Cria pasta de processados se não existir
    mkdir -p "$PROCESSED_DIR"

    # Loop por arquivos zip/mcpack/mcaddon
    shopt -s nullglob
    for file in "$AUTO_INSTALL_DIR"/*.{zip,mcpack,mcaddon}; do
        echo "[Auto-Install] Encontrado: $(basename "$file")"
        
        # Executa o instalador em modo silencioso
        python3 "$INSTALLER_SCRIPT" --auto-install "$file" --server-dir "$SERVER_DIR"
        
        if [ $? -eq 0 ]; then
            echo "[Auto-Install] Sucesso! Movendo para processed/..."
            mv "$file" "$PROCESSED_DIR/"
        else
            echo "[Auto-Install] FALHA ao instalar $(basename "$file"). Veja logs acima."
        fi
    done
    shopt -u nullglob
else
    echo "[Auto-Install] Pasta $AUTO_INSTALL_DIR não encontrada. Criando para uso futuro..."
    mkdir -p "$AUTO_INSTALL_DIR"
    mkdir -p "$PROCESSED_DIR"
fi
