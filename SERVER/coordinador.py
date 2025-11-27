import socket
import threading
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# --- Configuración ---
COORD_HOST = "0.0.0.0"   # Escucha en todas las interfaces de red
COORD_PORT = 5000        # Puerto TCP del coordinador (para REGISTER_NODE)
DISCOVERY_PORT = 5001    # Puerto UDP para descubrimiento automático
HTTP_PORT = 8000        # Puerto HTTP para API (UI)

# Tabla de nodos registrados: node_id -> {ip, port, conexión}
nodos_registrados = {}
conexiones_activas = {}  # node_id -> socket conexión TCP
nodes_persistent_file = os.path.join(os.path.dirname(__file__), 'nodes_data.json')

# Contador simple para generar nombres nodo1, nodo2, nodo3, ...
next_node_number = 1
lock_nodos = threading.Lock()   # Para modificar contador/tablas de forma segura


def obtener_ip_servidor():
    """
    Obtiene una IP 'usable' del servidor (no 127.0.0.1).
    Truco típico: conectar a una IP pública y leer la IP local usada.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No hace falta que funcione la conexión, solo se usa para obtener la IP local.
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def discovery_server():
    """
    Servidor UDP que responde a los mensajes de descubrimiento.
    Cliente manda: "DISCOVER_COORDINATOR"
    Respuesta: JSON con { "ip", "port", "node_id" }
    """
    global next_node_number

    ip_servidor = obtener_ip_servidor()
    print(f"[DISCOVERY] Usando IP servidor: {ip_servidor}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass
    sock.bind(("", DISCOVERY_PORT))  # Escucha en DISCOVERY_PORT en cualquier interfaz
    print(f"[DISCOVERY] Escuchando broadcast UDP en puerto {DISCOVERY_PORT}...")

    while True:
        data, addr = sock.recvfrom(1024)
        mensaje = data.decode().strip()
        print(f"[DISCOVERY] Mensaje '{mensaje}' desde {addr}")

        if mensaje == "DISCOVER_COORDINATOR":
            # Generamos un nuevo node_id único
            with lock_nodos:
                node_id = f"nodo{next_node_number}"
                next_node_number += 1

            respuesta = {
                "ip": ip_servidor,
                "port": COORD_PORT,
                "node_id": node_id
            }

            sock.sendto(json.dumps(respuesta).encode(), addr)
            print(f"[DISCOVERY] Asignado {node_id} para {addr}")


def load_persistent_nodes():
    try:
        if os.path.exists(nodes_persistent_file):
            with open(nodes_persistent_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            with lock_nodos:
                nodos_registrados.update(data.get('nodos', {}))
            print(f"[HTTP] Cargados {len(nodos_registrados)} nodos desde disco.")
    except Exception as e:
        print(f"[HTTP] Error cargando nodos persistentes: {e}")


def _broadcast_event(event_obj, exclude_node=None):
    """
    Envía un JSON `event_obj` a todas las conexiones activas TCP.
    Si alguna conexión falla, la elimina de `conexiones_activas`.
    """
    remove_list = []
    with lock_nodos:
        for nid, sock in list(conexiones_activas.items()):
            if exclude_node and nid == exclude_node:
                continue
            try:
                sock.sendall(json.dumps(event_obj).encode())
            except Exception as e:
                print(f"[BROADCAST] Error enviando a {nid}: {e}. Se eliminará la conexión.")
                remove_list.append(nid)

        for nid in remove_list:
            try:
                del conexiones_activas[nid]
            except KeyError:
                pass
            if nid in nodos_registrados:
                # Marcar offline y actualizar persistencia
                nodos_registrados[nid]['status'] = 'offline'
    if remove_list:
        save_persistent_nodes()


def save_persistent_nodes():
    try:
        with lock_nodos:
            data = {'nodos': nodos_registrados}
        with open(nodes_persistent_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[HTTP] Guardado {len(nodos_registrados)} nodos en {nodes_persistent_file}")
    except Exception as e:
        print(f"[HTTP] Error guardando nodos persistentes: {e}")


class SimpleAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        resp = json.dumps(obj).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/discover':
            global next_node_number
            with lock_nodos:
                node_id = f"nodo{next_node_number}"
                next_node_number += 1
            respuesta = {'ip': obtener_ip_servidor(), 'port': COORD_PORT, 'node_id': node_id}
            self._send_json(respuesta)
        elif path == '/nodes':
            with lock_nodos:
                nodes_list = []
                for nid, info in nodos_registrados.items():
                    nodes_list.append({'id': nid, 'ip': info.get('ip'), 'port': info.get('port'), 'capacity': info.get('capacity', 0), 'status': info.get('status', 'unknown'), 'used': info.get('used', 0)})
            self._send_json({'nodes': nodes_list})
        else:
            self._send_json({'error': 'Not found'}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length > 0 else b''
        try:
            data = json.loads(body.decode('utf-8')) if body else {}
        except Exception:
            data = {}

        if path == '/register':
            node_id = data.get('node_id')
            capacity = data.get('capacity', 0)
            client_ip = self.client_address[0]
            if not node_id:
                self._send_json({'status': 'ERROR', 'message': 'missing node_id'}, status=400)
                return
            with lock_nodos:
                nodos_registrados[node_id] = {'ip': client_ip, 'port': COORD_PORT, 'capacity': capacity, 'status': 'online', 'used': 0}
            save_persistent_nodes()
            print(f"[HTTP] Nodo registrado via HTTP: {node_id} -> {client_ip} cap={capacity}")
            self._send_json({'status': 'OK', 'node_id': node_id})
        elif path == '/message':
            print(f"[HTTP] Mensaje recibido via API: {data}")
            self._send_json({'status': 'OK'})
        else:
            self._send_json({'error': 'Not found'}, status=404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', '0')
        self.end_headers()


def start_http_server():
    server_address = ('', HTTP_PORT)
    httpd = ThreadingHTTPServer(server_address, SimpleAPIHandler)
    print(f"[HTTP] API escuchando en puerto {HTTP_PORT}...")
    httpd.serve_forever()


def manejar_nodo(conn, addr):
    """
    Maneja una conexión TCP individual con un nodo.
    Aquí el nodo envía REGISTER_NODE con el node_id que recibió por discovery.
    Mantiene la conexión abierta para mensajes posteriores.
    """
    print(f"[TCP] Nueva conexión TCP desde {addr}")
    
    node_id_actual = None
    conn.settimeout(None)  # Sin timeout para conexión persistente

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                print(f"[TCP] {node_id_actual or addr} cerró la conexión.")
                break

            try:
                msg = json.loads(data.decode())
            except Exception as e:
                print(f"[TCP] Error al decodificar JSON: {e}")
                continue

            msg_type = msg.get("type")

            if msg_type == "REGISTER_NODE":
                node_id_actual = msg.get("node_id")
                listen_port = msg.get("listen_port")

                # Guardamos la info del nodo en la tabla global
                with lock_nodos:
                    nodos_registrados[node_id_actual] = {
                        "ip": addr[0],
                        "port": listen_port,
                        "status": "online",
                        "used": 0
                    }
                    conexiones_activas[node_id_actual] = conn

                print(f"[TCP] Nodo registrado: {node_id_actual} -> {addr[0]}:{listen_port}")
                print(f"[TCP] Tabla actual de nodos: {list(nodos_registrados.keys())}")

                conn.sendall(json.dumps({"status": "REGISTER_OK", "node_id": node_id_actual}).encode())
                # Notificar a los demás nodos que este nodo se ha conectado
                evento = {
                    "type": "NODE_CONNECTED",
                    "node_id": node_id_actual,
                    "ip": addr[0],
                    "port": listen_port
                }
                print(f"[BROADCAST] Notificando conexión de {node_id_actual} a {len(conexiones_activas)-1} nodos")
                _broadcast_event(evento, exclude_node=node_id_actual)
                save_persistent_nodes()

            elif msg_type == "GET_NODOS":
                # Retorna la lista de todos los nodos conectados
                with lock_nodos:
                    nodos_lista = [n for n in nodos_registrados.keys() if n != node_id_actual]
                
                respuesta = {
                    "type": "NODOS_LIST",
                    "nodos": nodos_lista
                }
                conn.sendall(json.dumps(respuesta).encode())
                print(f"[TCP] {node_id_actual} solicitó lista de nodos. Enviados: {nodos_lista}")

            elif msg_type == "SEND_MESSAGE":
                from_node = msg.get("from")
                to_node = msg.get("to")
                contenido = msg.get("content")

                if to_node == "COORDINADOR":
                    # Mensaje dirigido al servidor
                    print(f"\n[MENSAJE] {from_node} → COORDINADOR: {contenido}")
                    respuesta = json.dumps({"status": "MESSAGE_RECEIVED", "message": f"Servidor recibió: {contenido}"})
                    conn.sendall(respuesta.encode())
                else:
                    # Mensaje dirigido a otro nodo
                    print(f"\n[MENSAJE] {from_node} → {to_node}: {contenido}")
                    
                    with lock_nodos:
                        if to_node in conexiones_activas:
                            try:
                                # Reenviamos el mensaje al nodo destino
                                msg_reenvio = {
                                    "type": "RECEIVE_MESSAGE",
                                    "from": from_node,
                                    "content": contenido
                                }
                                conexiones_activas[to_node].sendall(json.dumps(msg_reenvio).encode())
                                respuesta = json.dumps({"status": "MESSAGE_SENT", "to": to_node})
                            except Exception as e:
                                print(f"[ERROR] No se pudo enviar mensaje a {to_node}: {e}")
                                respuesta = json.dumps({"status": "ERROR", "message": f"No se pudo enviar a {to_node}"})
                        else:
                            respuesta = json.dumps({"status": "ERROR", "message": f"Nodo {to_node} no conectado"})
                    
                    conn.sendall(respuesta.encode())

            else:
                print(f"[TCP] Mensaje desconocido de {node_id_actual}: {msg}")

    except Exception as e:
        print(f"[TCP] Error en conexión de {node_id_actual or addr}: {e}")
    finally:
        with lock_nodos:
            if node_id_actual and node_id_actual in conexiones_activas:
                del conexiones_activas[node_id_actual]
            if node_id_actual and node_id_actual in nodos_registrados:
                # Marcamos como desconectado (offline) y persistimos
                nodos_registrados[node_id_actual]['status'] = 'offline'
                del nodos_registrados[node_id_actual]
                save_persistent_nodes()
                # Notificar a los demás nodos
                evento = {
                    "type": "NODE_DISCONNECTED",
                    "node_id": node_id_actual
                }
                print(f"[BROADCAST] Notificando desconexión de {node_id_actual} a {len(conexiones_activas)} nodos")
                _broadcast_event(evento, exclude_node=node_id_actual)
        
        print(f"[TCP] Desconexión de {node_id_actual or addr}. Nodos activos: {list(nodos_registrados.keys())}")
        conn.close()


def tcp_server():
    """
    Servidor TCP del coordinador, que recibe REGISTER_NODE y mensajes.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        try:
            s.bind((COORD_HOST, COORD_PORT))
        except OSError as e:
            print(f"[ERROR] No se pudo enlazar TCP en {COORD_HOST}:{COORD_PORT} -> {e}")
            raise
        s.listen()
        print(f"[COORDINADOR] Escuchando conexiones TCP en {COORD_HOST}:{COORD_PORT}...")

        while True:
            conn, addr = s.accept()
            hilo = threading.Thread(target=manejar_nodo, args=(conn, addr), daemon=True)
            hilo.start()


def main():
    # Hilo para el servidor UDP (discovery)
    hilo_discovery = threading.Thread(target=discovery_server, daemon=True)
    hilo_discovery.start()

    # Cargar nodos persistentes
    load_persistent_nodes()

    # Hilo para servidor HTTP (API)
    hilo_http = threading.Thread(target=start_http_server, daemon=True)
    hilo_http.start()

    # Servidor TCP principal (bloqueante)
    tcp_server()


if __name__ == "__main__":
    main()
