import socket
import struct
import time
import sys
import os

# Configurações
BROADCAST_PORT = 19132
# Lista de IPs locais que queremos anunciar (IPs dos containers ou aliases)
# O script tentará descobrir automaticamente, mas você pode forçar aqui se necessário.
# Exemplo: TARGET_IPS = ["192.168.71.200", "192.168.71.201"]
TARGET_IPS = [] 

# Constantes do RakNet
UNCONNECTED_PING_ID = 0x01
UNCONNECTED_PONG_ID = 0x1C

def get_local_interfaces_ips():
    """Tenta descobrir os IPs configurados nas interfaces de rede (aliases)."""
    ips = []
    try:
        # Comando ip addr para pegar todos os IPs eth0:0, eth0:1, etc.
        # Filtra apenas 192.168.71.x conforme seu setup
        import subprocess
        result = subprocess.check_output("ip -4 addr show | grep 'inet 192.168.71.'", shell=True).decode()
        for line in result.splitlines():
            # Ex: inet 192.168.71.200/22 brd ...
            parts = line.strip().split()
            if len(parts) >= 2:
                ip_cidr = parts[1]
                ip = ip_cidr.split('/')[0]
                ips.append(ip)
    except Exception as e:
        print(f"[Erro] Falha ao detectar IPs automaticamente: {e}")
    
    return ips

def create_pong_packet(ping_payload, motd, server_port=19132):
    """
    Cria um pacote Unconnected Pong.
    Original Ping Payload deve vir junto para retornar o PingID (Time).
    """
    # Header
    packet = bytearray()
    packet.append(UNCONNECTED_PONG_ID)
    
    # Ping ID (Time) - copiamos do ping recebido (bytes 1-8)
    # Ping payload normal tem ~35 bytes. ID=0x01, Time=8bytes, Magic=16bytes, GUID=8bytes
    if len(ping_payload) >= 9:
        packet.extend(ping_payload[1:9])
    else:
        packet.extend((0).to_bytes(8, byteorder='big'))
        
    # Server GUID (Random)
    import random
    server_guid = random.getrandbits(64)
    packet.extend(server_guid.to_bytes(8, byteorder='big'))
    
    # Magic (Offline Message Data ID)
    # 00ffff00fefefefefdfdfdfd12345678
    magic = bytes.fromhex("00ffff00fefefefefdfdfdfd12345678")
    packet.extend(magic)
    
    # Se não temos um MOTD real, construímos um genérico
    if not motd:
        motd = f"MCPE;Bedrock Server;589;1.20.0;0;10;{server_guid};Bedrock Level;Survival;1;{server_port};{server_port+1};"
        
    motd_bytes = motd.encode('utf-8')
    packet.extend(len(motd_bytes).to_bytes(2, byteorder='big'))
    packet.extend(motd_bytes)
    
    return packet

def query_local_server(ip, port=19132):
    """
    Tenta enviar um pingo para o servidor local (na propria interface)
    para pegar o MOTD real dele.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.2) # Timeout rápido
    
    try:
        # Envia Ping
        ping_pkt = bytearray()
        ping_pkt.append(UNCONNECTED_PING_ID)
        ping_pkt.extend((0).to_bytes(8, byteorder='big')) # Time
        ping_pkt.extend(bytes.fromhex("00ffff00fefefefefdfdfdfd12345678")) # Magic
        ping_pkt.extend((0).to_bytes(8, byteorder='big')) # GUID
        
        sock.sendto(ping_pkt, (ip, port))
        
        data, _ = sock.recvfrom(2048)
        
        # Parse PONG para extrair o MOTD (remove bytes iniciais)
        if data and data[0] == UNCONNECTED_PONG_ID:
            # Pula ID(1) + Time(8) + GUID(8) + Magic(16) = 33 bytes
            offset = 33
            if len(data) > offset:
                str_len = int.from_bytes(data[offset:offset+2], byteorder='big')
                motd = data[offset+2 : offset+2+str_len].decode('utf-8')
                return motd
            
    except Exception:
        pass
    finally:
        sock.close()
    
    return None

def main():
    # 1. Detecta IPs
    ips_to_announce = TARGET_IPS
    if not ips_to_announce:
        print("Detectando IPs locais (192.168.71.x)...")
        ips_to_announce = get_local_interfaces_ips()
    
    if not ips_to_announce:
        print("Nenhum IP 192.168.71.x encontrado! O script não fará nada.")
        sys.exit(1)

    print(f"IPs detectados para anúncio: {ips_to_announce}")

    # 2. Socket Principal (Escuta Broadcasts)
    # 0.0.0.0 escuta em todas as interfaces
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Permite compartilhar a porta 19132 com o Docker
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, 'SO_REUSEPORT'):
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except:
            pass

    try:
        listener.bind(('0.0.0.0', BROADCAST_PORT))
        print(f"Escutando broadcasts UDP em 0.0.0.0:{BROADCAST_PORT}...")
    except Exception as e:
        print(f"ERRO CRÍTICO: Não foi possível fazer bind na porta {BROADCAST_PORT}: {e}")
        print("Verifique se rodou como root (sudo) ou se o Docker já travou a porta exclusivamente.")
        sys.exit(1)

    while True:
        try:
            data, addr = listener.recvfrom(4096)
            
            # Se for Unconnected Ping (0x01 ou 0x02)
            if data and len(data) > 0 and (data[0] == 0x01 or data[0] == 0x02):
                client_ip, client_port = addr
                
                # Ignorar pings vindos dos nossos próprios IPs
                if client_ip in ips_to_announce or client_ip.startswith("127."):
                    continue
                
                # Para cada IP de servidor que temos, vamos responder como se fossemos ele
                for server_ip in ips_to_announce:
                    # Tenta pegar MOTD real do servidor rodando nesse IP
                    real_motd = query_local_server(server_ip, 19132)
                    
                    if real_motd:
                        # Constrói resposta com os dados originais do ping (para o cliente aceitar como resposta válida)
                        pong = create_pong_packet(data, real_motd)
                        
                        # TRUQUE: Enviar a resposta usando o IP de origem correto (server_ip)
                        # Sem isso, o cliente recebe do IP principal da VM e tenta conectar nele
                        try:
                            reply_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                            reply_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            
                            # Bind no IP específico do alias e na porta 19132
                            # Isso faz o pacote de retorno ter Source IP = server_ip
                            reply_sock.bind((server_ip, BROADCAST_PORT)) 
                            
                            reply_sock.sendto(pong, addr)
                            reply_sock.close()
                            
                            # print(f"DEBUG: Anunciado {server_ip} para {client_ip}")
                            
                        except Exception as ex:
                            # Se falhar o bind específico, pode ser que a porta esteja em uso exclusivo pelo Docker
                            print(f"Erro ao responder por {server_ip}: {ex}")

        except KeyboardInterrupt:
            print("\nParando...")
            break
        except Exception as e:
            print(f"Erro no loop: {e}")

if __name__ == "__main__":
    main()
