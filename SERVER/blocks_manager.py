import os
import json

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
                b['status'] = 'free'
                if 'primary_for' in b:
                    del b['primary_for']
                if 'replica_for' in b:
                    try:
                        del b['replica_for']
                    except Exception:
                        pass
                changed = True
        except Exception:
            pass

    if changed:
        blocks_data_raw['table_size'] = len(blocks_data_raw.get('blocks', {}))
    return changed
