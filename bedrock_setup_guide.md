# Otimização Minecraft Bedrock (UDP) para Linux

Servidores Bedrock utilizam o protocolo UDP (RakNet). As configurações padrão do Linux são geralmente otimizadas para TCP, o que pode causar perda de pacotes ou lag em servidores Bedrock.

## 1. Ajustes de Kernel (Sysctl)

Crie o arquivo `/etc/sysctl.d/99-bedrock.conf` na VM com o seguinte conteúdo:

```ini
# Aumentar buffers de leitura/escrita UDP
net.core.rmem_max = 26214400
net.core.rmem_default = 26214400
net.core.wmem_max = 26214400
net.core.wmem_default = 26214400

# Otimizações de fila
net.core.netdev_max_backlog = 5000

# Configurações IPv4 UDP
net.ipv4.udp_rmem_min = 16384
net.ipv4.udp_wmem_min = 16384
```

Aplicar com: `sysctl --system`

## 2. Configuração do Wings (config.yml)

Ao configurar o **Wings**, você deve garantir que a opção `throttle` (limite) do sistema de arquivos e rede não esteja sufocando a transferência de mundos grandes, mas o mais importante para o Bedrock é a **alocação**.

No `config.yml` do Wings (geralmente em `/etc/pterodactyl/config.yml`), certifique-se de que:
*   `allow_cors_origins`: esteja configurado se for usar acesso web externo.
*   **IMPORTANTE**: O Wings deve ouvir em `0.0.0.0` para aceitar conexões em todos os IPs.

```yaml
api:
  host: 0.0.0.0
  port: 8080
```

## 3. Alocações (Painel)
Você tem 15 IPs. Para garantir funcionamento perfeito:
*   Crie alocações **APENAS** na porta `19132` (Padrão Bedrock) e `19133` (IPv6/Alt) para **CADA IP**.
*   Não use portas aleatórias (ex: 25565) se o objetivo é ter "IP Dedicado".

Exemplo no Painel:
*   IP `192.168.71.200` -> Porta `19132`
*   IP `192.168.71.201` -> Porta `19132`
*   ...
