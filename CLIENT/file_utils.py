import os
import json


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def safe_basename(filename):
    # Simple safe basename: quitar rutas
    return os.path.basename(filename)


def split_file_to_blocks(file_storage, dest_dir=None, block_size=1024*1024):
    """Divide un archivo recibido (Flask FileStorage) en bloques de `block_size` bytes.
    Guarda los bloques en `dest_dir` y devuelve metadata JSON con lista de bloques.
    Cada bloque se nombra: <base>.partNNN
    """
    if dest_dir is None:
        dest_dir = os.path.join(os.path.dirname(__file__), 'temp')
    ensure_dir(dest_dir)

    filename = safe_basename(getattr(file_storage, 'filename', 'uploaded_file'))
    base, ext = os.path.splitext(filename)

    blocks = []
    index = 1

    # FileStorage provides a stream attribute
    stream = getattr(file_storage, 'stream', None) or file_storage

    while True:
        chunk = stream.read(block_size)
        if not chunk:
            break
        block_name = f"{base}.part{index:03d}"
        block_path = os.path.join(dest_dir, block_name)
        with open(block_path, 'wb') as bf:
            bf.write(chunk)

        blocks.append({
            'block_name': block_name,
            'size': len(chunk),
            'path': block_path,
            'index': index
        })
        index += 1

    meta = {
        'original_filename': filename,
        'total_blocks': len(blocks),
        'blocks': blocks
    }

    meta_path = os.path.join(dest_dir, f"{base}_blocks.json")
    try:
        with open(meta_path, 'w', encoding='utf-8') as mf:
            json.dump(meta, mf, indent=2)
    except Exception:
        # si no se puede escribir metadata, seguimos devolviendo la estructura
        pass

    return meta
