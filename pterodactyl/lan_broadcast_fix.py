import socket
import struct
import time
import sys
import os
import subprocess
import shutil

# Configurações
BROADCAST_PORT = 19132
# IPs alvo manuais (deixe vazio para auto-detectar)
TARGET_IPS = [] 

# Constantes do RakNet
UNCONNECTED_PING_ID = 0x01
UNCONNECTED_PONG_ID = 0x1C

def find_ip_command():
    """Encontra o caminho do executável 'ip'."""
    path = shutil.which("ip")
    if path:
        return path
    
    # Fallbacks comuns
    for p in ["/sbin/ip", "/usr/sbin/ip", "/bin/ip", "/usr/bin/ip"]:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
    return None

def get_local_interfaces_ips():
    """
    Tenta descobrir os IPs configurados nas interfaces de rede (aliases).
    Retorna lista de strings IP.
    """
    ips = []
    ip_cmd = find_ip_command()
    
    if not ip_cmd:
        print("[Erro] Comando 'ip' não encontrado no sistema.")
        return []

    try:
        # Executa 'ip -4 addr show' diretamente (sem shell=True para evitar problemas de PATH/pipe)
        output = subprocess.check_output([ip_cmd, "-4", "addr", "show"], stderr=subprocess.STDOUT).decode()
        
        for line in output.splitlines():
            line = line.strip()
            # Procura por linhas com o IP da nossa sub-rede
            if "inet 192.168.71." in line:
                # Ex: inet 192.168.71.200/22 brd ...
                parts = line.split()
                # O segundo campo geralmente é o IP/CIDR
                # Às vezes pode variar, então vamos buscar o que tem formato de IP
                for part in parts:
                    if "192.168.71." in part and "/" in part:
                        ip = part.split('/')[0]
                        ips.append(ip)
                        break
    except Exception as e:
        print(f"[Erro] Falha ao detectar IPs: {e}")
    
    return list(set(ips)) # Remove duplicados

def create_pong_packet(ping_payload, motd, server_port=19132):
    packet = bytearray()
    packet.append(UNCONNECTED_PONG_ID)
    
    if len(ping_payload) >= 9:
        packet.extend(ping_payload[1:9])
    else:
        packet.extend((0).to_bytes(8, byteorder='big'))
        
    import random
    server_guid = random.getrandbits(64)
    packet.extend(server_guid.to_bytes(8, byteorder='big'))
    
    magic = bytes.fromhex("00ffff00fefefefefdfdfdfd12345678")
    packet.extend(magic)
    
    if not motd:
        motd = f"MCPE;Bedrock Server;589;1.20.0;0;10;{server_guid};Bedrock Level;Survival;1;{server_port};{server_port+1};"
        
    motd_bytes = motd.encode('utf-8')
    packet.extend(len(motd_bytes).to_bytes(2, byteorder='big'))
    packet.extend(motd_bytes)
    
    return packet

def query_local_server(ip, port=19132):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.2)
    
    try:
        ping_pkt = bytearray()
        ping_pkt.append(UNCONNECTED_PING_ID)
        ping_pkt.extend((0).to_bytes(8, byteorder='big'))
        ping_pkt.extend(bytes.fromhex("00ffff00fefefefefdfdfdfd12345678"))
        ping_pkt.extend((0).to_bytes(8, byteorder='big'))
        
        sock.sendto(ping_pkt, (ip, port))
        
        data, _ = sock.recvfrom(2048)
        
        if data and data[0] == UNCONNECTED_PONG_ID:
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
    print("Iniciando fix de LAN Bedrock...")
    
    # Loop de detecção de IP (Retry)
    # Se o serviço iniciar antes da rede estar pronta, ele vai aguardar.
    ips_to_announce = []
    listener = None
    
    while True:
        # 1. Atualizar IPs alvo se necessário (ou se estiver vazio)
        if not ips_to_announce:
            manual_ips = TARGET_IPS
            if manual_ips:
                ips_to_announce = manual_ips
            else:
                detected_ips = get_local_interfaces_ips()
                if detected_ips:
                    ips_to_announce = detected_ips
                    print(f"IPs detectados: {ips_to_announce}")
                else:
                    # Se não achou IPs, aguarda e tenta de novo sem crashar
                    print("Aguardando detecção de IPs 192.168.71.x ...")
                    time.sleep(5)
                    continue

        # 2. Bind do Socket (apenas uma vez)
        if listener is None:
            try:
                listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if hasattr(socket, 'SO_REUSEPORT'):
                    try: 
                        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                    except: pass
                
                listener.bind(('0.0.0.0', BROADCAST_PORT))
                print(f"Escutando em 0.0.0.0:{BROADCAST_PORT}")
            except Exception as e:
                print(f"Erro fatal no bind: {e}")
                print("Tentando novamente em 5s...")
                if listener: listener.close()
                listener = None
                time.sleep(5)
                continue

        # 3. Loop principal de pacotes
        try:
            # Check se temos dados com timeout para permitir re-verificar IPs periodicamente?
            # Por enquanto, blockeante é mais eficiente.
            data, addr = listener.recvfrom(4096)
            
            if data and len(data) > 0 and (data[0] == 0x01 or data[0] == 0x02):
                client_ip, client_port = addr
                
                if client_ip in ips_to_announce or client_ip.startswith("127."):
                    continue
                
                for server_ip in ips_to_announce:
                    real_motd = query_local_server(server_ip, 19132)
                    
                    if real_motd:
                        pong = create_pong_packet(data, real_motd)
                        try:
                            reply_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                            reply_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            reply_sock.bind((server_ip, BROADCAST_PORT)) 
                            reply_sock.sendto(pong, addr)
                            reply_sock.close()
                        except Exception as ex:
                            # Erro silencioso no envio para não spammar log
                            pass

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Erro no loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
