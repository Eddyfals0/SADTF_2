from flask import Flask, jsonify, request
from flask_cors import CORS # Para permitir que el HTML hable con el servidor

app = Flask(__name__)
CORS(app) # Importante para evitar errores de seguridad del navegador

# --- VARIABLES GLOBALES DEL NODO ---
capacidad_nodo = 0
estado = "desconectado"
nodos_conectados = [] # Aquí guardarías la info real de la red

# 1. RUTA PARA CONECTAR (El botón "Conectar" del HTML llama aquí)
@app.route('/conectar', methods=['POST'])
def conectar():
    data = request.json
    global capacidad_nodo, estado
    
    capacidad_nodo = data.get('capacidad') # Recibe 50-100MB del HTML
    estado = "online"
    
    # AQUÍ INICIARÍAS TU LÓGICA DE SOCKETS PARA AVISAR A OTROS NODOS
    # iniciar_servidor_sockets()
    
    return jsonify({"mensaje": "Nodo iniciado", "id_asignado": "NODO_XYZ"})

# 2. RUTA PARA OBTENER ESTADO (El HTML llama a esto cada 2 segundos)
@app.route('/estado', methods=['GET'])
def obtener_estado():
    # Aquí devuelves la lista real de nodos y el mapa de bloques
    return jsonify({
        "nodos": nodos_conectados,
        "archivos": lista_mis_archivos,
        "uso_global": calcular_uso_global()
    })

# 3. RUTA PARA SUBIR ARCHIVO (El área de carga llama aquí)
@app.route('/subir', methods=['POST'])
def subir_archivo():
    archivo = request.files['file']
    
    # AQUÍ VA TU LÓGICA PESADA:
    # 1. Leer archivo
    # 2. Dividir en bloques de 1MB
    # 3. Distribuir bloques a otros IPs (usando sockets)
    
    return jsonify({"status": "ok", "mensaje": "Archivo distribuido correctamente"})

if __name__ == '__main__':
    # Ejecuta el servidor web en el puerto 5000
    app.run(debug=True, port=5000)