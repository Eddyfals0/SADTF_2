from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import requests

from file_utils import split_file_to_blocks

app = Flask(__name__)
CORS(app)

# Configurar carpeta temp
TEMP_FOLDER = os.path.join(os.path.dirname(__file__), 'temp')
os.makedirs(TEMP_FOLDER, exist_ok=True)

# --- VARIABLES GLOBALES DEL NODO ---
capacidad_nodo = 0
estado = "desconectado"
nodos_conectados = []
lista_mis_archivos = []


def calcular_uso_global():
    total = sum(n.get('capacity', 0) for n in nodos_conectados)
    used = 0
    return {"used": used, "total": total}


# ENDPOINT: Recibir archivo, dividir en bloques y enviar info al coordinador
@app.route('/upload_and_split', methods=['POST'])
def upload_and_split():
    """
    Recibe un archivo, lo divide en bloques de 1MB, los guarda en CLIENT/temp/
    y envía la info de bloques al coordinador.
    """
    archivo = request.files.get('file')
    if not archivo:
        return jsonify({"status": "error", "mensaje": "No se recibió archivo en campo 'file'"}), 400

    try:
        # Dividir archivo en bloques
        meta = split_file_to_blocks(archivo, dest_dir=TEMP_FOLDER, block_size=1024*1024)
        
        # Registrar localmente
        lista_mis_archivos.append({
            'name': meta.get('original_filename'),
            'blocks': meta.get('total_blocks'),
        })

        # Enviar info de bloques al coordinador
        coordinator_url = "http://localhost:8000/receive_blocks"
        blocks_info = {
            'filename': meta.get('original_filename'),
            'total_blocks': meta.get('total_blocks'),
            'blocks': meta.get('blocks')
        }
        
        coordinator_contacted = False
        try:
            resp = requests.post(coordinator_url, json=blocks_info, timeout=5)
            print(f"[CLIENT] Enviado info de bloques al coordinador: {resp.status_code}")
            coordinator_contacted = True
        except Exception as e:
            print(f"[CLIENT] Advertencia: no se pudo enviar bloques al coordinador: {e}")

        return jsonify({
            "status": "ok",
            "mensaje": "Archivo dividido y almacenado localmente",
            "blocks_sent_to_coordinator": coordinator_contacted,
            "meta": meta
        })

    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500


if __name__ == '__main__':
    # Puerto 5001 para el backend que procesa archivos
    print("[API] Escuchando en http://localhost:5001")
    print("[INSTRUCCIONES] Usa 'python -m http.server 5500' en la carpeta raíz para servir Index.html")
    app.run(debug=True, port=5001)