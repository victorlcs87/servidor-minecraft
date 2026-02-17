# Status do Projeto - Servidor Minecraft Bedrock (Pterodactyl)

Este documento resume as melhorias implementadas no instalador de addons e na configuração do Egg para Pterodactyl.

## ✅ O que foi feito

### 1. Pterodactyl Egg (`egg-bedrock.json`)
- **Estratégia de Download Remoto**: O Egg foi atualizado para não embutir scripts pesados no JSON. Agora, ele baixa automaticamente o `auto_install_addons.sh` e o `bedrock_addon_installer.py` diretamente do GitHub durante a instalação. Isso evita erros de limite de caracteres no painel.
- **Novas Configurações**: Adicionado suporte para variáveis de ambiente `SEED` (Semente do nível) e `TEXTUREPACK` (Exigir pacote de textura).

### 2. Bedrock Addon Installer (`bedrock_addon_installer.py`)
- **Suporte a Arquivos**: Agora aceita diretamente arquivos `.zip`, `.mcpack` e `.mcaddon`.
- **Modo --auto-scan**: Implementada inteligência de busca que detecta automaticamente a pasta raiz do servidor (seja no Pterodactyl, Crafty ou Local) e processa a pasta `addons_auto_install`.
- **Otimização de Espaço**: O processo de extração agora utiliza uma pasta temporária local (`.tmp_addon_extract`) para evitar erros de "Disco Cheio" em partições `/tmp` restritas.
- **Filtro de Sistema**: O instalador agora ignora pacotes padrão do Minecraft (como `vanilla` e `chemistry`), focando apenas nos addons do usuário.
- **Logs Limpos**: Todos os caminhos absolutos foram removidos dos logs para facilitar a leitura no console do painel.

### 3. Wrapper de Inicialização (`auto_install_addons.sh`)
- **Dinâmico**: Atualizado para detectar o diretório de execução em tempo real, eliminando erros de permissão de "Somente Leitura" (`Read-only file system`).
- **Simplicidade**: Atua como um gatilho seguro que chama a lógica avançada do Python.

### 4. Organização do Repositório
- **Git Flow**: Todas as alterações foram commitadas e enviadas para o repositório `victorlcs87/servidor-minecraft`.
- **Controle de Arquivos**: Criado arquivo `.gitignore` para manter o workspace limpo de backups, mundos e binários do servidor.

### 5. Correção de Visibilidade LAN (Novo)
- **Problema**: Servidores Bedrock rodando em containers Docker não recebem pacotes de broadcast da LAN (udp 19132), impedindo que apareçam na aba "Amigos".
- **Solução**: Criado script Python (`lan_broadcast_fix.py`) que roda no host (VM) e retransmite esses pacotes, respondendo em nome dos servidores locais.
- **Automação**: Incluído arquivo `lan-fix.service` para gerenciar o script via systemd.

### 6. Reestruturação e Documentação
- **Organização**: Scripts de instalação (`bedrock_addon_installer.py`, `auto_install_addons.sh`) movidos para a pasta `pterodactyl/` para melhor organização.
- **Egg Atualizado**: O `egg-bedrock.json` agora baixa os scripts do novo local.
- **Documentação Completa**: Criado `docs/INSTALL.md` com o guia passo-a-passo de toda a infraestrutura (Host, VM, Rede, Pterodactyl).

---

## 📍 Onde estamos agora
- O sistema está **100% funcional** e automatizado.
- O instalador detecta corretamente o ambiente do Pterodactyl e instala addons pesados (como o *Better on Bedrock*) automaticamente ao ligar o servidor.
- A manutenção ficou fácil: basta atualizar os scripts no repositório local e dar um `push`. O servidor Pterodactyl pegará as mudanças na próxima vez que for **Reinstalado**.

---

## 🚀 O que falta fazer / Próximos Passos
- **Monitoramento de Disco**: Devido ao tamanho enorme de alguns addons, é importante monitorar se o limite de disco do servidor no painel é suficiente (Better on Bedrock pode exigir mais de 2GB extras).
- **Testes de Exclusão**: Validar a nova função de "Delete" através da interface TUI (via terminal interativo) se houver necessidade de remover addons manualmente.
- **Documentação de Uso**: Criar um pequeno guia para os usuários finais sobre como nomear suas pastas de addons (uso de prefixos BP/RP).
