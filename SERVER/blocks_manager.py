import os
import json
import shutil

# Carpeta base donde el coordinador guardará los bloques físicamente
# Ejemplo Windows: C:\\Users\\<usuario>\\espacioCompartido
BASE_SHARE_DIR = os.path.join(os.path.expanduser('~'), 'espacioCompartido')


def ensure_node_dir(node_id: str):
    path = os.path.join(BASE_SHARE_DIR, node_id)
    os.makedirs(path, exist_ok=True)
    return path

blocks_persistent_file = os.path.join(os.path.dirname(__file__), 'info', 'blocks_data.json')


def load_persistent_blocks():
    try:
        if os.path.exists(blocks_persistent_file):
            with open(blocks_persistent_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    data = {'blocks': {}, 'table_size': 0}
                else:
                    data = json.loads(content)
        else:
            data = {'blocks': {}, 'table_size': 0}
        if 'blocks' not in data:
            data['blocks'] = {}
        if 'table_size' not in data:
            data['table_size'] = len(data.get('blocks', {}))
        # Devolver RAW (mapping) para uso del coordinador
        return data
    except Exception as e:
        print(f"[BLOCKS_MANAGER] Error cargando bloques persistentes: {e}")
        return {'blocks': {}, 'table_size': 0}


def save_persistent_blocks(blocks_data):
    try:
        # blocks_data puede venir como RAW {'blocks': {id: block,...}, 'table_size': n}
        # o como UI {'blocks': [...], 'table_size': n, '_raw': {...}}
        if isinstance(blocks_data, dict) and ('_raw' in blocks_data or (isinstance(blocks_data.get('blocks', None), dict))):
            # si tiene _raw usamos ese raw, si 'blocks' es mapping, asumimos que es raw
            if '_raw' in blocks_data:
                raw = blocks_data['_raw']
            else:
                raw = blocks_data
        else:
            # construir raw a partir de lista
            raw = {'blocks': {}, 'table_size': 0}
            for b in blocks_data.get('blocks', []):
                raw['blocks'][b['id']] = b
            raw['table_size'] = blocks_data.get('table_size', len(raw['blocks']))
        with open(blocks_persistent_file, 'w', encoding='utf-8') as f:
            json.dump(raw, f, indent=2)
        print(f"[BLOCKS_MANAGER] Guardado {len(raw.get('blocks', {}))} bloques en {blocks_persistent_file}")
    except Exception as e:
        print(f"[BLOCKS_MANAGER] Error guardando bloques persistentes: {e}")


def update_blocks_for_node(node_id, capacity_mb, blocks_data_raw):
    """Ajusta registros RAW (dict) de bloques para un nodo en base a capacity_mb (1 bloque = 1MB)."""
    raw = blocks_data_raw
    if 'blocks' not in raw:
        raw['blocks'] = {}

    # extraer número del nodo
    try:
        node_num = 0
        if node_id.startswith('nodo'):
            node_num = int(node_id[4:])
        else:
            import re
            m = re.search(r"(\d+)$", node_id)
            node_num = int(m.group(1)) if m else 0
    except Exception:
        node_num = 0

    prefix = f"N{node_num}"

    existing = [b for b in raw['blocks'].values() if b.get('node') == node_id]
    existing_count = len(existing)
    desired = int(capacity_mb)

    if desired > existing_count:
        for i in range(existing_count + 1, desired + 1):
            bid = f"{prefix}{str(i).zfill(3)}"
            raw['blocks'][bid] = {
                'id': bid,
                'node': node_id,
                'index': i,
                'status': 'free',
                'primary_for': None
            }
    elif desired < existing_count:
        node_blocks = sorted([b for b in raw['blocks'].values() if b.get('node') == node_id], key=lambda x: x.get('index', 0), reverse=True)
        to_remove = node_blocks[:(existing_count - desired)]
        for b in to_remove:
            bid = b.get('id')
            try:
                del raw['blocks'][bid]
            except KeyError:
                pass

    raw['table_size'] = len(raw['blocks'])
    return raw


def set_node_blocks_unavailable(node_id, blocks_data_raw):
    changed = False
    for b in blocks_data_raw.get('blocks', {}).values():
        if b.get('node') == node_id:
            if b.get('status') != 'unavailable':
                b['status'] = 'unavailable'
                changed = True
    return changed


def set_node_blocks_available(node_id, blocks_data_raw):
    changed = False
    for b in blocks_data_raw.get('blocks', {}).values():
        if b.get('node') == node_id:
            if b.get('status') == 'unavailable':
                b['status'] = 'free'
                changed = True
    return changed


def raw_to_ui_struct(raw):
    # raw: {'blocks': {id: block, ...}, 'table_size': n}
    return {'blocks': list(raw.get('blocks', {}).values()), 'table_size': raw.get('table_size', 0), '_raw': raw}


def find_free_blocks_by_node(blocks_data_raw):
    """Devuelve mapping node_id -> lista de block_ids libres"""
    res = {}
    for bid, b in blocks_data_raw.get('blocks', {}).items():
        if b.get('status') == 'free':
            node = b.get('node')
            res.setdefault(node, []).append(bid)
    return res


def assign_blocks_to_file(blocks_data_raw, file_id: str, placements: list):
    """
    Marca en `blocks_data_raw` las asignaciones para un archivo.
    `placements` es lista de dicts con keys: 'primary_block_id', 'replica_block_ids'
    Modifica estados: primary -> status='occupied', primary_for=file_id
                     replica -> status='replica', replica_for=file_id
    Retorna True si al menos una asignación fue aplicada.
    """
    changed = False
    # Nota: esta función solo marca estados en la tabla RAW. La copia física
    # de los bloques debe realizarse en el coordinador pasando metadata adicional
    for p in placements:
        prim = p.get('primary_block_id')
        reps = p.get('replica_block_ids', [])
        try:
            if prim and prim in blocks_data_raw.get('blocks', {}):
                b = blocks_data_raw['blocks'][prim]
                b['status'] = 'occupied'
                b['primary_for'] = file_id
                changed = True
        except Exception:
            pass

        for r in reps:
            try:
                if r and r in blocks_data_raw.get('blocks', {}):
                    rb = blocks_data_raw['blocks'][r]
                    rb['status'] = 'replica'
                    # mantener lista de replicas si hace falta
                    if 'replica_for' not in rb:
                        rb['replica_for'] = []
                    if file_id not in rb['replica_for']:
                        rb['replica_for'].append(file_id)
                    changed = True
            except Exception:
                pass

    if changed:
        # recompute table_size (no cambia normalmente)
        blocks_data_raw['table_size'] = len(blocks_data_raw.get('blocks', {}))
    return changed


def free_blocks(blocks_data_raw, block_ids: list):
    changed = False
    for bid in block_ids:
        try:
            if bid in blocks_data_raw.get('blocks', {}):
                b = blocks_data_raw['blocks'][bid]
                # Eliminar fichero físico si existe
                try:
                    p = b.get('path')
                    if p and os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass

                b['status'] = 'free'
                if 'primary_for' in b:
                    del b['primary_for']
                if 'replica_for' in b:
                    try:
                        del b['replica_for']
                    except Exception:
                        pass
                if 'path' in b:
                    try:
                        del b['path']
                    except Exception:
                        pass
                changed = True
        except Exception:
            pass

    if changed:
        blocks_data_raw['table_size'] = len(blocks_data_raw.get('blocks', {}))
    return changed


def assign_and_copy_blocks(blocks_data_raw, file_id: str, placements: list, metadata: dict = None, temp_dir: str = None):
    """
    Asigna bloques en la tabla RAW y copia los binarios desde `metadata` (archivos en temp)
    hacia la ruta compartida BASE_SHARE_DIR/<node_id>/. Actualiza campo 'path' en cada bloque.
    Retorna True si hubo al menos un cambio aplicado.
    """
    changed = False
    if metadata is None:
        metadata = {}

    for p in placements:
        idx = p.get('file_block_index', 0)
        # metadata.blocks expected list aligned by index-1
        src_info = None
        try:
            src_info = metadata.get('blocks', [])[idx - 1]
        except Exception:
            src_info = None

        primary_id = p.get('primary_block_id')
        primary_node = p.get('primary_node')

        # copy primary
        if primary_id and primary_node and primary_id in blocks_data_raw.get('blocks', {}):
            try:
                block_meta = blocks_data_raw['blocks'][primary_id]
                # ensure node dir
                ensure_node_dir(primary_node)
                if src_info and src_info.get('path') and os.path.exists(src_info.get('path')):
                    src_path = src_info.get('path')
                    dest_path = os.path.join(BASE_SHARE_DIR, primary_node, src_info.get('block_name'))
                    try:
                        shutil.copy2(src_path, dest_path)
                        block_meta['path'] = dest_path
                    except Exception as e:
                        print(f"[BLOCKS_MANAGER] Error copiando primary {primary_id} a {dest_path}: {e}")
                block_meta['status'] = 'occupied'
                block_meta['primary_for'] = file_id
                changed = True
            except Exception:
                pass

        # copy replicas
        reps = p.get('replica_block_ids', [])
        rep_nodes = p.get('replica_nodes', [])
        for rid, rnode in zip(reps, rep_nodes):
            if rid and rnode and rid in blocks_data_raw.get('blocks', {}):
                try:
                    rmeta = blocks_data_raw['blocks'][rid]
                    ensure_node_dir(rnode)
                    if src_info and src_info.get('path') and os.path.exists(src_info.get('path')):
                        src_path = src_info.get('path')
                        dest_path = os.path.join(BASE_SHARE_DIR, rnode, src_info.get('block_name'))
                        try:
                            shutil.copy2(src_path, dest_path)
                            rmeta['path'] = dest_path
                        except Exception as e:
                            print(f"[BLOCKS_MANAGER] Error copiando replica {rid} a {dest_path}: {e}")
                    rmeta['status'] = 'replica'
                    if 'replica_for' not in rmeta:
                        rmeta['replica_for'] = []
                    if file_id not in rmeta['replica_for']:
                        rmeta['replica_for'].append(file_id)
                    changed = True
                except Exception:
                    pass

    # marcar tamaño tabla
    if changed:
        blocks_data_raw['table_size'] = len(blocks_data_raw.get('blocks', {}))
    return changed


def replicate_blocks_to_node(blocks_data_raw, files_data, node_id: str):
    """
    Cuando un nuevo nodo se conecta, intenta crear réplicas de bloques existentes
    en `node_id` usando bloques libres del nodo. Actualiza `blocks_data_raw` y
    `files_data` (las placements de cada archivo). Retorna número de réplicas creadas.
    """
    created = 0
    # encontrar bloques libres en target node
    free_blocks = [b for b in blocks_data_raw.get('blocks', {}).values() if b.get('node') == node_id and b.get('status') == 'free']
    if not free_blocks:
        return created

    # recorrer cada archivo y sus placements
    for fid, f in files_data.get('files', {}).items():
        placements = f.get('placements', [])
        for p in placements:
            # si node_id ya es replica o primary, saltar
            primary_node = p.get('primary_node')
            replica_nodes = p.get('replica_nodes', [])
            if node_id == primary_node or node_id in replica_nodes:
                continue

            if not free_blocks:
                return created

            # tomar un free block del nodo
            target_block = free_blocks.pop(0)
            tid = target_block.get('id')

            # copiar desde primary path si existe
            try:
                primary_bid = p.get('primary_block_id')
                primary_meta = blocks_data_raw.get('blocks', {}).get(primary_bid, {})
                src = primary_meta.get('path')
                if src and os.path.exists(src):
                    ensure_node_dir(node_id)
                    dest = os.path.join(BASE_SHARE_DIR, node_id, os.path.basename(src))
                    try:
                        shutil.copy2(src, dest)
                        # actualizar tabla
                        blocks_data_raw['blocks'][tid]['path'] = dest
                        blocks_data_raw['blocks'][tid]['status'] = 'replica'
                        if 'replica_for' not in blocks_data_raw['blocks'][tid]:
                            blocks_data_raw['blocks'][tid]['replica_for'] = []
                        blocks_data_raw['blocks'][tid]['replica_for'].append(fid)
                        # actualizar placement en files_data
                        if 'replica_block_ids' not in p:
                            p['replica_block_ids'] = []
                        if 'replica_nodes' not in p:
                            p['replica_nodes'] = []
                        p['replica_block_ids'].append(tid)
                        p['replica_nodes'].append(node_id)
                        created += 1
                    except Exception as e:
                        print(f"[BLOCKS_MANAGER] Error replicando a nodo {node_id}: {e}")
                else:
                    # si no está disponible el fichero fuente, saltar
                    continue
            except Exception:
                continue

    if created:
        blocks_data_raw['table_size'] = len(blocks_data_raw.get('blocks', {}))
    return created
