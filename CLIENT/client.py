import socket
import json
import threading
import time

DISCOVERY_PORT = 5001   # Debe coincidir con el del coordinador
LISTEN_PORT = 6000      # Puerto donde ESTE nodo escucharía (lo puedes usar después)
DISCOVERY_TIMEOUT = 3   # segundos

# Variables globales
coord_socket = None
node_id = None
coord_ip = None
coord_port = None
lock_socket = threading.Lock()  # Para evitar conflictos en el socket


def discover_coordinator():
    """
    Envía un broadcast UDP preguntando 'DISCOVER_COORDINATOR'.
    Espera una respuesta JSON con {ip, port, node_id}.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(DISCOVERY_TIMEOUT)

    mensaje = "DISCOVER_COORDINATOR".encode()
    # 255.255.255.255 → broadcast a la red local
    sock.sendto(mensaje, ("255.255.255.255", DISCOVERY_PORT))

    try:
        data, addr = sock.recvfrom(1024)
        respuesta = json.loads(data.decode())
        print(f"[CLIENTE] Respuesta de discovery desde {addr}: {respuesta}")
        return respuesta["ip"], respuesta["port"], respuesta["node_id"]
    except socket.timeout:
        print("[CLIENTE] No se encontró coordinador (timeout).")
        return None, None, None
    finally:
        sock.close()


def connect_to_coordinator(coord_ip, coord_port, node_id):
    """
    Se conecta por TCP al coordinador y mantiene la conexión abierta.
    """
    global coord_socket
    
    try:
        coord_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[CLIENTE] Conectando al coordinador en {coord_ip}:{coord_port}...")
        coord_socket.connect((coord_ip, coord_port))

        msg = {
            "type": "REGISTER_NODE",
            "node_id": node_id,
            "listen_port": LISTEN_PORT
        }

        with lock_socket:
            coord_socket.sendall(json.dumps(msg).encode())
            resp = coord_socket.recv(1024).decode()
        print("[CLIENTE] Respuesta del coordinador:", resp)
        return True
    except Exception as e:
        print(f"[CLIENTE] Error conectando al coordinador: {e}")
        return False


def escuchar_mensajes():
    """
    Hilo dedicado a escuchar mensajes entrantes del coordinador/otros nodos.
    Se ejecuta continuamente en background.
    """
    global coord_socket
    
    while True:
        try:
            with lock_socket:
                if coord_socket:
                    data = coord_socket.recv(1024)
            
            if not data:
                print("\n[CLIENTE] Conexión cerrada por el servidor.")
                break
            
            try:
                msg = json.loads(data.decode())
                msg_type = msg.get("type")
                
                if msg_type == "RECEIVE_MESSAGE":
                    from_node = msg.get("from")
                    content = msg.get("content")
                    print(f"\n╔════════════════════════════════════════╗")
                    print(f"║ 📨 MENSAJE DE {from_node:30}║")
                    print(f"╠════════════════════════════════════════╣")
                    print(f"║ {content:38}║")
                    print(f"╚════════════════════════════════════════╝\n")
                    print("Selecciona una opción (1-4): ", end="", flush=True)
                elif msg_type == "PING":
                    # Responder con PONG para que el coordinador confirme la conexión
                    try:
                        pong = {"type": "PONG", "node_id": node_id}
                        with lock_socket:
                            if coord_socket:
                                coord_socket.sendall(json.dumps(pong).encode())
                    except Exception:
                        pass
                elif msg_type == "PONG":
                    # Ignorar PONGs recibidos
                    pass
                elif msg_type == "NODE_CONNECTED":
                    nid = msg.get("node_id")
                    ip = msg.get("ip")
                    port = msg.get("port")
                    print(f"\n[NOTIFICACIÓN] Nodo conectado: {nid} -> {ip}:{port}")
                    print("Selecciona una opción (1-4): ", end="", flush=True)
                elif msg_type == "NODE_DISCONNECTED":
                    nid = msg.get("node_id")
                    print(f"\n[NOTIFICACIÓN] Nodo desconectado: {nid}")
                    print("Selecciona una opción (1-4): ", end="", flush=True)
                
            except json.JSONDecodeError:
                print(f"\n[CLIENTE] Mensaje no JSON recibido: {data.decode()}")
        
        except Exception as e:
            if coord_socket:
                print(f"\n[CLIENTE] Error escuchando mensajes: {e}")
            break
        
        time.sleep(0.1)


def get_nodos_conectados():
    """
    Solicita al coordinador la lista de nodos conectados.
    """
    try:
        msg = {
            "type": "GET_NODOS",
            "node_id": node_id
        }
        with lock_socket:
            coord_socket.sendall(json.dumps(msg).encode())
            resp = coord_socket.recv(4096).decode()
        respuesta = json.loads(resp)
        return respuesta.get("nodos", [])
    except Exception as e:
        print(f"[CLIENTE] Error obteniendo nodos: {e}")
        return []


def enviar_mensaje_a_nodo(nodo_destino, contenido):
    """
    Envía un mensaje a través del coordinador a otro nodo.
    """
    try:
        msg = {
            "type": "SEND_MESSAGE",
            "from": node_id,
            "to": nodo_destino,
            "content": contenido
        }
        with lock_socket:
            coord_socket.sendall(json.dumps(msg).encode())
            resp = coord_socket.recv(1024).decode()
        print(f"[CLIENTE] Respuesta: {resp}")
    except Exception as e:
        print(f"[CLIENTE] Error enviando mensaje: {e}")


def enviar_mensaje_al_servidor(contenido):
    """
    Envía un mensaje al servidor (coordinador).
    """
    try:
        msg = {
            "type": "SEND_MESSAGE",
            "from": node_id,
            "to": "COORDINADOR",
            "content": contenido
        }
        with lock_socket:
            coord_socket.sendall(json.dumps(msg).encode())
            resp = coord_socket.recv(1024).decode()
        print(f"[CLIENTE] Respuesta del servidor: {resp}")
    except Exception as e:
        print(f"[CLIENTE] Error enviando mensaje al servidor: {e}")


def mostrar_menu():
    """
    Muestra el menú principal y procesa las opciones del usuario.
    """
    while True:
        print("\n" + "="*50)
        print("MENÚ PRINCIPAL")
        print("="*50)
        print("1. Ver nodos conectados")
        print("2. Enviar mensaje a un nodo")
        print("3. Enviar mensaje al servidor")
        print("4. Salir")
        print("="*50)
        
        opcion = input("Selecciona una opción (1-4): ").strip()
        
        if opcion == "1":
            nodos = get_nodos_conectados()
            if nodos:
                print("\n[NODOS CONECTADOS]")
                for idx, nodo in enumerate(nodos, 1):
                    print(f"  {idx}. {nodo}")
            else:
                print("\n[INFO] No hay nodos conectados.")
        
        elif opcion == "2":
            nodos = get_nodos_conectados()
            if not nodos:
                print("\n[INFO] No hay nodos disponibles.")
                continue
            
            print("\n[NODOS DISPONIBLES]")
            for idx, nodo in enumerate(nodos, 1):
                print(f"  {idx}. {nodo}")
            
            try:
                seleccion = int(input("\nSelecciona el número del nodo: ")) - 1
                if 0 <= seleccion < len(nodos):
                    nodo_destino = nodos[seleccion]
                    contenido = input(f"Mensaje para {nodo_destino}: ").strip()
                    if contenido:
                        enviar_mensaje_a_nodo(nodo_destino, contenido)
                    else:
                        print("[ADVERTENCIA] Mensaje vacío no enviado.")
                else:
                    print("[ERROR] Selección inválida.")
            except ValueError:
                print("[ERROR] Entrada inválida.")
        
        elif opcion == "3":
            contenido = input("Mensaje para el servidor: ").strip()
            if contenido:
                enviar_mensaje_al_servidor(contenido)
            else:
                print("[ADVERTENCIA] Mensaje vacío no enviado.")
        
        elif opcion == "4":
            print("[CLIENTE] Desconectando...")
            if coord_socket:
                try:
                    # Intentar desconexión limpia
                    msg = {"type": "DISCONNECT", "node_id": node_id}
                    with lock_socket:
                        coord_socket.sendall(json.dumps(msg).encode())
                        # intentar recibir ack (no obligatorio)
                        try:
                            resp = coord_socket.recv(1024).decode()
                            print(f"[CLIENTE] ACK desconexión: {resp}")
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[CLIENTE] Error enviando DISCONNECT: {e}")
                finally:
                    try:
                        coord_socket.close()
                    except Exception:
                        pass
            break
        
        else:
            print("[ERROR] Opción no válida. Intenta de nuevo.")


def main():
    global node_id, coord_ip, coord_port
    
    # 1) Descubrir coordinador y obtener IP, puerto y node_id asignado
    coord_ip, coord_port, node_id = discover_coordinator()
    if coord_ip is None:
        print("No se pudo descubrir el coordinador. Saliendo.")
        return

    print(f"[CLIENTE] Usaré node_id = {node_id}")

    # 2) Conectarse por TCP con ese node_id (mantiene conexión abierta)
    if not connect_to_coordinator(coord_ip, coord_port, node_id):
        print("[CLIENTE] No se pudo conectar. Saliendo.")
        return
    
    # 3) Iniciar hilo para escuchar mensajes
    hilo_escucha = threading.Thread(target=escuchar_mensajes, daemon=True)
    hilo_escucha.start()
    
    # 4) Mostrar menú interactivo
    mostrar_menu()


if __name__ == "__main__":
    main()
