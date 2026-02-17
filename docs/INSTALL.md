# Guia de Instalação Completa - Servidor Minecraft Bedrock (Pterodactyl)

Este documento detalha como configurar do zero o ambiente para rodar servidores de Minecraft Bedrock com **IPs Dedicados** e **Visibilidade LAN** (Aba Amigos), utilizando uma VM KVM sobre Linux.

## 🏗️ Arquitetura

- **Host (Físico)**: Gerencia a rede (Bridge) e o Relay de LAN.
- **VM (Guest - Debian 12)**: Roda o Docker, Painel Pterodactyl e Wings.
- **Rede**:
    - `br0` (Host): Ponte direta com o roteador.
    - `eth0` (VM): Recebe Múltiplos IPs (Aliases) na mesma interface.
    - **Docker**: Cada servidor roda em uma porta 19132 UDP, mas ligado a um IP específico (ex: 192.168.71.200).

---

## 🚀 Passo 1: Preparação do Host (Máquina Física)

O Host precisa de uma "Bridge" para que a VM tenha acesso direto à rede física (como se fosse outro PC no cabo).

### 1.1 Configurar Bridge (`br0`)
Execute o script de configuração de bridge (requer `network-manager`):

```bash
# Na pasta do repositório
cd pterodactyl
sudo bash setup_host_bridge.sh
```
*Isso vai criar a interface `br0` e desconectar/reconectar a rede.*

### 1.2 Configurar Correção de LAN (Aba Amigos)
Como o Docker isola broadcasts, precisamos de um Relay no Host para "avisar" a rede que existem servidores rodando.

```bash
# Copia e instala o serviço
sudo cp lan_broadcast_fix.py /root/
sudo cp lan-fix.service /etc/systemd/system/

# Ativa
sudo systemctl daemon-reload
sudo systemctl enable --now lan-fix.service
```

---

## 💻 Passo 2: Configuração da VM (Debian)

Instale uma VM Debian 12 usando o `virt-manager`.
**Importante**: Na configuração da placa de rede da VM, selecione:
- **Network Source**: Bridge device (br0)
- **Device model**: virtio

### 2.1 Configurar IPs Dedicados (Dentro da VM)
Acesse a VM via SSH ou Console e clone este repositório lá dentro.

```bash
git clone https://github.com/victorlcs87/servidor-minecraft.git
cd servidor-minecraft/pterodactyl
```

Edite o script `setup_vm_ips.sh` se precisar ajustar a faixa de IPs (Padrão: 192.168.71.200 a .214).
Execute para configurar os IPs estáticos:

```bash
sudo bash setup_vm_ips.sh
```
*A VM irá reiniciar a rede e assumir 16 IPs (1 principal + 15 aliases).*

---

## 🦅 Passo 3: Instalação Pterodactyl + Wings (Na VM)

### 3.1 Instalar Docker e Dependências
```bash
curl -sSL https://get.docker.com/ | CHANNEL=stable bash
systemctl enable --now docker
apt install -y certbot
```

### 3.2 Instalar Painel e Wings
Siga a documentação oficial ou use scripts de auto-instalação.
**Ponto Crítico - Configuração do Wings (`/etc/pterodactyl/config.yml`):**
Certifique-se de que o Wings ouça em **todos** os IPs:

```yaml
api:
  host: 0.0.0.0
  port: 8080
system:
  # ...
  sftp:
    bind_port: 2022
```

### 3.3 Importar o Egg Bedrock
1. No Painel Pterodactyl (Admin), vá em **Nests** > **Import Egg**.
2. Selecione o arquivo `pterodactyl/egg-bedrock.json` deste repositório.
3. Associe-o ao Nest "Minecraft".

### 3.4 Criar Servidores
Ao criar um servidor:
1. **Alocation**: Escolha um dos IPs dedicados (ex: 192.168.71.200) e a porta `19132`.
2. **Environment**: Deixe tudo padrão. O instalador baixará os scripts automaticamente.

---

## 🔄 Manutenção e Updates

### Atualizar Scripts de Instalação (Sem reinstalar VM)
Se você alterou `bedrock_addon_installer.py` ou `auto_install_addons.sh`:
1. Dê `git push` no repositório.
2. No Painel Pterodactyl, vá no servidor e clique em **Reinstall Server**.
   - Isso baixará as novas versões dos scripts.
   - **Seus mundos e addons não serão perdidos** (o script só baixa os arquivos de sistema).

### Atualizar Fix de LAN
No Host:
```bash
cd servidor-minecraft
git pull
sudo cp pterodactyl/lan_broadcast_fix.py /root/
sudo systemctl restart lan-fix.service
```
