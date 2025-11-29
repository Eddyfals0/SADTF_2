# SADTF - Sistema de Archivos Distribuido Tolerante a Fallas

Un sistema de archivos distribuido que divide archivos en bloques de 1MB, los replica entre múltiples nodos y permite descarga/consulta desde dispositivos en la LAN sin necesidad de registrarse como nodo.

## Tabla de contenidos
1. [Requisitos](#requisitos)
2. [Estructura del proyecto](#estructura-del-proyecto)
3. [Instalación](#instalación)
4. [Uso - Configuración rápida en una máquina](#uso---configuración-rápida-en-una-máquina)
5. [Uso - Multi-máquina en LAN](#uso---multi-máquina-en-lan)
6. [Interfaz Web (Index.html)](#interfaz-web-indexhtml)
7. [Troubleshooting](#troubleshooting)

---

## Requisitos

- **Python 3.8+** (3.13 recomendado)
- **Windows 10/11** (actualmente diseñado para Windows; fácilmente adaptable a Linux/macOS)
- **Navegador web** moderno (Chrome, Edge, Firefox)
- **Conexión LAN** (para multi-máquina)

---

## Estructura del proyecto

```
SADTF_2/
├── Index.html                  # Interfaz web (UI)
├── requirements.txt            # Dependencias Python
├── SERVER/
│   ├── coordinador.py          # Servidor coordinador (orquesta bloques, nodos)
│   ├── blocks_manager.py       # Gestión persistente de bloques
│   ├── files_manager.py        # Índice persistente de archivos
│   ├── node_manager.py         # Información de nodos
│   ├── partitioner.py          # Asignación round-robin de bloques
│   ├── info/                   # Directorio de persistencia JSON
│   │   ├── nodes_data.json
│   │   ├── blocks_data.json
│   │   └── files_data.json
│   ├── temp/                   # Bloques temporales durante split
│   └── tools/
│       └── cleanup.py          # Script de limpieza
├── CLIENT/
│   ├── client.py               # Cliente nodo (almacena bloques, se comunica con coordinador)
│   ├── __init__.py
│   ├── api.py                  # (futuro: APIs específicas del nodo)
│   └── funciones.py            # (futuro: utilidades)
└── Puebas/                     # Carpeta de pruebas
```

---

## Instalación

### 1. Clonar o descargar el proyecto

```bash
git clone https://github.com/Eddyfals0/SADTF_2.git
cd SADTF_2
```

### 2. Instalar dependencias (opcional, para ahora mismo no hay módulos externos)

```bash
pip install -r requirements.txt
```

*(Actualmente sin dependencias externas, usa solo librerías estándar de Python)*

### 3. Verificar Python

```powershell
python --version
# Debe mostrar Python 3.8+
```

---

## Uso - Configuración rápida en una máquina

Ideal para probar el sistema en un solo equipo (simulando coordinador + 1-2 nodos locales).

### Paso 1: Inicia el Coordinador

En una terminal PowerShell (o cmd), desde la raíz del proyecto:

```powershell
cd C:\ruta\a\SADTF_2
python SERVER\coordinador.py
```

**Esperado en la terminal:**
```
[DISCOVERY] Usando IP servidor: 172.31.13.X
[DISCOVERY] Escuchando broadcast UDP en puerto 5001...
[HTTP] Cargados X nodos desde disco. next_node_number=Y
[BLOCKS_MANAGER] Guardado N bloques en ...
[MONITOR] Monitor de conexiones iniciado (interval=5s)
[COORDINADOR] Escuchando conexiones TCP en 0.0.0.0:5000...
[HTTP] API escuchando en puerto 8000...
[MAIN] Asegurado BASE_SHARE_DIR: C:\Users\<Usuario>\espacioCompartido
```

El coordinador ahora escucha en:
- **Puerto 8000 (HTTP)**: API para subir archivos, listar nodos, descargar, etc.
- **Puerto 5000 (TCP)**: Comunicación con nodos (registro, envío de bloques).
- **Puerto 5001 (UDP)**: Discovery automático de coordinador.

### Paso 2: Abre la Interfaz Web

En una **tercera terminal** (o desde la carpeta del proyecto):

```powershell
cd C:\ruta\a\SADTF_2
python -m http.server 5500
```

**Esperado en la terminal:**
```
Serving HTTP on :: port 5500 (http://[::]:5500/) ...
```

Ahora abre tu navegador web y ve a:
```
http://localhost:5500
```

### Paso 3: Usa la UI

1. **Conectar al coordinador:**
   - Campo "IP Coord": ingresa `localhost:8000`
   - Campo "Cap (MB)": establece capacidad (p.ej. 70 MB)
   - Botón "Conectar"

2. **Subir archivo:**
   - Arrastra un archivo o haz clic en el área de carga.
   - El archivo se divide en bloques de 1MB.
   - El coordinador asigna a nodos y envía bloques.

3. **Ver estado:**
   - Pestaña "Nodos Conectados": lista de nodos online/offline.
   - Barra de almacenamiento global: uso/capacidad total.
   - Pestaña "Tabla de Bloques": mapa visual de bloques (verde=principal, rojo=réplica, gris=libre).
   - Pestaña "Consola": logs de operaciones.

4. **Descargar archivo:**
   - Lista de archivos: botón de ojo para ver, descarga para descargar (guardado en Descargas del navegador).
   - Botón eliminar: libera bloques en todos los nodos.

---

## Uso - Multi-máquina en LAN

Para simular 2 máquinas físicas o VMs en la misma red.

### Escenario: Máquina 1 (Coordinador + Nodo1) + Máquina 2 (Nodo2)

#### **Máquina 1 (Coordinador + Nodo1)**

**Terminal 1 - Coordinador:**
```powershell
cd C:\ruta\a\SADTF_2
python SERVER\coordinador.py
```

Anota la **IP de la máquina 1** (p.ej. `192.168.1.100`). Puedes verla con:
```powershell
ipconfig /all
# Busca "IPv4 Address:" en la sección de tu adaptador de red
```

**Terminal 2 - Nodo1 (cliente):**
```powershell
cd C:\ruta\a\SADTF_2
python CLIENT\client.py
```

**Terminal 3 - Servidor HTTP para UI:**
```powershell
cd C:\ruta\a\SADTF_2
python -m http.server 5500
```

Abre navegador: `http://localhost:5500` (o `http://192.168.1.100:5500` si accedes desde otra máquina).

---

#### **Máquina 2 (Nodo2 solamente)**

**Terminal - Nodo2 (cliente):**
```powershell
cd C:\ruta\a\SADTF_2
python CLIENT\client.py
```

El cliente descubrirá el coordinador mediante broadcast UDP en el puerto 5001 y se registrará automáticamente.

**Esperado:**
```
[CLIENTE] Respuesta de discovery desde ('192.168.1.100', 5001): {'ip': '192.168.1.100', 'port': 5000, 'node_id': 'nodo2'}
[CLIENTE] Conectando al coordinador en 192.168.1.100:5000...
```

---

#### **Usar la UI desde cualquier máquina en la LAN**

Desde cualquier máquina (incluso Máquina 3 sin rol de coordinador/nodo):

1. Abre navegador: `http://192.168.1.100:5500` (reemplaza con IP de Máquina 1).
2. Campo "IP Coord": `192.168.1.100:8000`
3. Campo "Cap": 70 (o la capacidad que desees para esa "máquina cliente").
4. Conectar.
5. Sube un archivo → el coordinador lo divide y distribuye entre nodo1 y nodo2.
6. Descarga desde cualquier máquina → el coordinador solicita bloques a los nodos conectados y los sirve.

---

## Interfaz Web (Index.html)

### Servir con Python HTTP Server

```powershell
cd C:\ruta\a\SADTF_2
python -m http.server 5500
```

Accede en navegador: `http://localhost:5500`

### Componentes principales

| Sección | Función |
|---------|---------|
| **Header (Azul)** | Selector de IP coordinador, capacidad, ID cliente, botón conectar |
| **Columna Izquierda** | Carga de archivo, lista de archivos (ver, descargar, eliminar) |
| **Columna Derecha - Nodos** | Tabla de nodos online/offline, barra de almacenamiento global |
| **Columna Derecha - Bloques** | Mapa visual de bloques (colores: libre, principal, réplica, no disponible) |
| **Columna Derecha - Consola** | Logs de operaciones en tiempo real |

### Endpoints HTTP disponibles

- `GET /nodes?all=1` → Lista nodos (online y offline)
- `GET /blocks` → Tabla de bloques global
- `GET /files` → Índice de archivos subidos
- `GET /storage` → Estadísticas de almacenamiento (capacidad, uso, %)
- `POST /upload` → Subir archivo (multipart/form-data)
- `GET /files/download?file_id=...` → Descargar archivo
- `POST /files/delete` → Eliminar archivo (JSON: `{file_id: ...}`)
- `POST /register` → Registrar nodo (JSON: `{node_id: ..., capacity: ...}`)
- `POST /disconnect` → Desconectar nodo (JSON: `{node_id: ...}`)
- `GET /whoami` → Información del cliente (IP, node_id, status)

---

## Troubleshooting

### Problema: "Nodo no conectado" en coordinador

**Síntoma:** Al subir archivo, logs muestran `[BLOCKS] Nodo nodo2 no conectado. Dejar primary pendiente.`

**Causa:** El cliente TCP no se registró o la conexión cayó.

**Solución:**
1. Asegúrate de que `CLIENT\client.py` está ejecutándose en la máquina nodo2.
2. Reinicia el cliente: `python CLIENT\client.py`
3. Observa terminal del cliente: debe mostrar `[CLIENTE] Respuesta del coordinador: {...REGISTER_OK...}`
4. En coordinador: debe mostrar `[TCP] Nodo registrado: nodo2 -> ...`
5. Intenta subir de nuevo.

### Problema: "No se pudo conectar al coordinador"

**Síntoma:** Error al pulsar "Conectar" desde la UI.

**Causa:** IP del coordinador incorrecta o coordinador no escuchando.

**Solución:**
1. Verifica que `SERVER\coordinador.py` está en ejecución y muestra `[HTTP] API escuchando en puerto 8000...`
2. Verifica IP: en terminal del coordinador busca `[DISCOVERY] Usando IP servidor: X.X.X.X`
3. En UI, usa esa IP, p.ej. `192.168.1.100:8000`
4. Si estás en la misma máquina, usa `localhost:8000`

### Problema: "Archivo no se descarga o descarga vacío"

**Síntoma:** Al hacer clic en descargar, el archivo no aparece en Descargas o está vacío.

**Causa:** Bloques no almacenados en nodos o coordinador no tiene acceso.

**Solución:**
1. Verifica que nodos conectados recibieron bloques: busca carpeta `C:\Users\<Usuario>\espacioCompartido\<node_id>\` en la máquina del nodo.
2. Si está vacía, revisa logs del cliente para errores en `STORE_BLOCK`.
3. Si bloques están allí pero descarga sigue fallando, puede ser timeout en coordinador solicitando bloques a nodos — aumenta timeout en código si es necesario.

### Problema: "Carpeta espacioCompartido no existe"

**Síntoma:** No aparece `C:\Users\<Usuario>\espacioCompartido\` tras subir archivo.

**Causa:** El cliente no recibió el bloque (STORE_BLOCK).

**Solución:**
1. Verifica en terminal del cliente que aparece `[CLIENT] Stored block ...`
2. Si no aparece, el coordinador no envió el bloque → revisa logs del coordinador para "[BLOCKS] No se pudo enviar..." o "[PENDING] Enviados X bloques..."
3. Si el coordinador intentó enviar pero falló, posiblemente firewall o DNS. Reinicia coordinador y cliente.

### Problema: "Permisos insuficientes para escribir en espacioCompartido"

**Síntoma:** Terminal del cliente muestra error de permiso al guardar bloque.

**Causa:** Antivirus o permisos de NTFS.

**Solución:**
1. Asegúrate de que `C:\Users\<Usuario>\espacioCompartido\` es escribible (prueba crear un archivo manualmente).
2. Si estás en Windows Defender/antivirus, añade la carpeta a excepciones.
3. Ejecuta terminal como Administrador si es necesario.

### Problema: "Conexión TCP rechazada entre máquinas en LAN"

**Síntoma:** Cliente en Máquina 2 no puede conectarse a Coordinador en Máquina 1 (error de conexión).

**Causa:** Firewall, ruta incorrecta, o puerto bloqueado.

**Solución:**
1. **Firewall:**
   - En Máquina 1 (coordinador): permite puerto 5000 (TCP) y 5001 (UDP).
   - En Windows Defender: Settings → Firewall → Allow an app through firewall → Python.exe en entrada y salida.

2. **IP correcta:**
   - En Máquina 1 terminal coordinador: anota IP exacta que aparece en "[DISCOVERY] Usando IP servidor: X.X.X.X"
   - En Máquina 2, el cliente debería descubrirla automáticamente, pero si no:
     - Prueba manualmente: `ping 192.168.1.100` desde Máquina 2 (reemplaza con IP Máquina 1).
     - Si ping falla, revisa conexión de red LAN.

3. **Puerto correcto:**
   - Cliente conecta a puerto 5000 (TCP) del coordinador.
   - Coordinador HTTP es puerto 8000 (para UI).
   - Asegúrate de no confundirlos.

---

## Notas adicionales

- **Almacenamiento de bloques:** Cada nodo almacena sus bloques en `C:\Users\<Usuario>\espacioCompartido\<node_id>\`
- **Persistencia:** Todos los índices se guardan en JSON (`SERVER/info/`), permitiendo reinicio del sistema sin pérdida de datos.
- **Replicación:** Por defecto, cada bloque se replica en 2 nodos (1 primario + 1 réplica). Configurable en `SERVER/partitioner.py`.
- **Timeout:** Descargas que solicitan bloques a nodos tienen timeout de 8 segundos. Ajustable en `coordinador.py` función `request_block_from_node`.

---

## Para desarrolladores

### Estructura de mensajes TCP

Nodos y coordinador intercambian JSON por TCP en puerto 5000:

```json
{
  "type": "REGISTER_NODE",
  "node_id": "nodo1",
  "listen_port": 6000
}
```

```json
{
  "type": "STORE_BLOCK",
  "file_id": "file_XXX",
  "block_id": "N1001",
  "block_name": "archivo.part001",
  "is_replica": false,
  "data_b64": "base64-encoded-binary-data"
}
```

Más tipos: `PING`, `PONG`, `GET_NODOS`, `SEND_MESSAGE`, `REQUEST_BLOCK`, `BLOCK_DATA`, etc.

### Ejecutar tests (futuro)

```powershell
python -m pytest Puebas/
```

---

## Licencia

Proyecto académico — Universidad. Sin licencia específica definida.

---

¿Preguntas? Consulta los logs en las terminales del coordinador y cliente para diagnóstico.
