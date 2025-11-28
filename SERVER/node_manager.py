import os
import json
import time

nodes_persistent_file = os.path.join(os.path.dirname(__file__), 'info', 'nodes_data.json')


def load_persistent_nodes():
    """Carga y devuelve la estructura {'nodos': {node_id: info}} o {} si no existe."""
    try:
        if os.path.exists(nodes_persistent_file):
            with open(nodes_persistent_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    data = {'nodos': {}}
                else:
                    data = json.loads(content)
        else:
            data = {'nodos': {}}
        # Normalizar estructura
        if 'nodos' not in data:
            data = {'nodos': {}}
        return data.get('nodos', {})
    except Exception as e:
        print(f"[NODE_MANAGER] Error cargando nodos persistentes: {e}")
        return {}


def save_persistent_nodes(nodos_dict):
    """Guarda la estructura de nodos en disco. Espera un mapping node_id -> info."""
    try:
        data = {'nodos': nodos_dict}
        os.makedirs(os.path.dirname(nodes_persistent_file), exist_ok=True)
        with open(nodes_persistent_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        # pequeña señal para debugging
        print(f"[NODE_MANAGER] Guardado {len(nodos_dict)} nodos en {nodes_persistent_file}")
    except Exception as e:
        print(f"[NODE_MANAGER] Error guardando nodos persistentes: {e}")


def compute_next_node_number(nodos_dict):
    """Calcula el siguiente número disponible para nombres tipo 'nodoX'."""
    max_n = 0
    for nid in nodos_dict.keys():
        if nid.startswith('nodo'):
            try:
                n = int(nid[4:])
                if n > max_n:
                    max_n = n
            except Exception:
                continue
    return max_n + 1


def mark_node_offline(nodos_dict, node_id):
    try:
        if node_id in nodos_dict:
            nodos_dict[node_id]['status'] = 'offline'
            nodos_dict[node_id]['last_seen'] = time.time()
            save_persistent_nodes(nodos_dict)
            return True
    except Exception as e:
        print(f"[NODE_MANAGER] Error marcando nodo offline: {e}")
    return False
