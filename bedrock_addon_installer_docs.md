# Bedrock Addon Installer - Documentação

## 📋 Visão Geral

Gerenciador interativo (TUI) de Addons para servidores Minecraft Bedrock Dedicated.
Usa as bibliotecas **rich** (interface colorida) e **InquirerPy** (menus interativos).

---

## 🔑 Conceitos Principais

| Termo | Significado |
|-------|-------------|
| **Installed** | Pack existe fisicamente em `behavior_packs/` ou `resource_packs/` do servidor |
| **Active** | Pack está registrado em `worlds/<mundo>/world_behavior_packs.json` ou `world_resource_packs.json` |

---

## ⚙️ Funcionalidades (Menu Principal)

### 1. Install
- Copia packs de uma pasta origem para o servidor
- **[NOVO] Suporte a .zip/.mcpack/.mcaddon**: Extrai e instala automaticamente
- Valida/cria `manifest.json` automático se ausente
- Registra os packs no arquivo JSON do mundo (merge, não sobrescreve)
- Gera relatório `world_packs_report.md`

### 2. Manage
- Lista todos os packs instalados com status (ACTIVE/inactive)
- **Filtros**: por tipo (behavior/resource), status (active/inactive), texto
- **Toggle individual**: ativa/desativa pack específico
- **Modo lote (batch)**: seleção por checkbox para ativar/desativar múltiplos de uma vez
- **[NOVO] Delete**: Remove do mundo E apaga os arquivos da pasta (Irreversível)

### 3. Remove (Deactivate)
- Atalho rápido para desativar um pack que está ativo
- Apenas remove do JSON do mundo (não deleta os arquivos)

### 4. [NOVO] Auto-Install (Integração Pterodactyl)
- Instalação automática ao iniciar o servidor
- Basta colocar arquivos `.zip/.mcpack` na pasta `addons_auto_install`
- O servidor instala e move o arquivo para `processed/`

---

## 🎨 Interface Visual

- 🟠 **behavior** = laranja
- 🔵 **resource** = azul
- 🟢 **ACTIVE** = verde (ativo)
- 🔴 **inactive** = vermelho (inativo)
- Painéis coloridos com bordas usando rich
- Tratamento elegante de Ctrl+C com mensagem de despedida

---

## 🛡️ Mecanismos de Segurança

```python
# Antes de escrever JSON:
safe_backup(path, ".prewrite.bak")  # Backup preventivo

# Se JSON estiver corrompido:
safe_backup(path, ".invalid.bak")   # Backup do inválido + aborta
```

---

## 📦 Dependências

- **Python 3.9+**
- **rich** (interface colorida)
- **InquirerPy** (menus interativos)

### Instalação das dependências:
```bash
pip install --user --break-system-packages rich InquirerPy
```

---

## 🚀 Como Executar

```bash
python3 bedrock_addon_installer.py
```

### Se precisar acessar pastas do servidor (permissão):
```bash
sudo chown -R $USER:$USER /var/opt/minecraft/crafty/crafty-4/servers/<UUID-DO-SERVIDOR>
```

---

## 📂 Estrutura de Arquivos

```
Minecraft/
├── bedrock_addon_installer.py      # Script principal
├── bedrock_addon_installer_docs.md # Esta documentação
├── .gitignore                      # Ignora __pycache__, venv, backups
└── Addons/                         # Pasta com seus addons para instalar
```

---

## 📝 Changelog

### v3.7 (2026-02-13)
- ✅ **[NOVO] Instalação via arquivo**: Suporte nativo para `.zip`, `.mcpack` e `.mcaddon`.
- ✅ **[NOVO] Deletar Addons**: Opção para remover permanentemente (arquivos + config).
- ✅ **[NOVO] Auto-Install**: Argumento de linha de comando `--auto-install` para integração com painéis (ex: Pterodactyl).
- ✅ **Manage**: Adicionado menu "Delete" separado do "Remove/Deactivate".

### v3.4 (2026-02-09)
- ✅ Corrigido erro `'dict' object has no attribute 'which'` ao selecionar múltiplos packs
- ✅ Status agora com cores: 🟢 **ACTIVE** (verde) e 🔴 **inactive** (vermelho)
- ✅ Refatorado sistema de seleção batch para usar chaves string em vez de objetos

### v3.3 (2026-02-08)
- ✅ Adicionada biblioteca **rich** para interface mais bonita
- ✅ Cores visuais para **behavior** (🟠) e **resource** (🔵)
- ✅ Tratamento elegante de Ctrl+C
- ✅ Detecção de dependências com instruções claras
- ✅ Removida auto-instalação de pacotes (mostra instruções)
- ✅ Removida função `pick_server_dir` não utilizada

---

## 💡 Próximos Passos (TODO)

- [ ] Testar instalação completa de addons
- [ ] Verificar comportamento após restart do servidor
- [ ] Adicionar opção de remover pack do disco (delete)
