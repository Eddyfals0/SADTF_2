#!/usr/bin/env python3
"""
Herramienta de limpieza para el proyecto SADTF_2.

Uso:
  python cleanup.py        # interactivo (pregunta antes de borrar)
  python cleanup.py --yes  # ejecuta sin preguntar

Acciones:
  - Reescribe `SERVER/info/nodes_data.json` con estructura mínima.
  - Reescribe `SERVER/info/blocks_data.json` con estructura mínima.
  - Elimina todos los ficheros dentro de `SERVER/temp/`.

Diseñado para usarse por el desarrollador localmente. Advertencia: esta acción es destructiva.
"""
import os
import sys
import json
import shutil


def safe_write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def remove_all_in_dir(path):
    if not os.path.exists(path):
        return 0
    removed = 0
    for name in os.listdir(path):
        full = os.path.join(path, name)
        try:
            if os.path.isdir(full):
                shutil.rmtree(full)
                removed += 1
            else:
                os.remove(full)
                removed += 1
        except Exception as e:
            print(f"Warning: no se pudo eliminar {full}: {e}")
    return removed


def main(argv=None):
    argv = argv or sys.argv[1:]
    force = False
    if '--yes' in argv or '-y' in argv:
        force = True

    # Calcular rutas relativas al directorio SERVER
    script_dir = os.path.dirname(os.path.abspath(__file__))  # .../SERVER/tools
    server_dir = os.path.dirname(script_dir)  # .../SERVER
    info_dir = os.path.join(server_dir, 'info')
    temp_dir = os.path.join(server_dir, 'temp')

    nodes_file = os.path.join(info_dir, 'nodes_data.json')
    blocks_file = os.path.join(info_dir, 'blocks_data.json')
    files_file = os.path.join(info_dir, 'files_data.json')

    print('=== Cleanup SADTF_2 ===')
    print(f'Info dir: {info_dir}')
    print(f'Temp dir: {temp_dir}')
    print('This will erase nodes, blocks, files index and all files in temp.\n')

    if not force:
        ans = input('¿Deseas continuar? [yes/no]: ').strip().lower()
        if ans not in ('y', 'yes'):
            print('Aborting. No se realizaron cambios.')
            return 0

    # Reescribir nodes_data.json
    safe_write_json(nodes_file, {'nodos': {}})
    print(f'Reescrito: {nodes_file}')

    # Reescribir blocks_data.json
    safe_write_json(blocks_file, {'blocks': {}, 'table_size': 0})
    print(f'Reescrito: {blocks_file}')

    # Reescribir files_data.json (índice de archivos)
    safe_write_json(files_file, {'files': {}})
    print(f'Reescrito: {files_file}')

    # Vaciar temp
    removed = remove_all_in_dir(temp_dir)
    print(f'Eliminados {removed} elementos en {temp_dir}')

    print('\nLimpieza completada.')


if __name__ == '__main__':
    sys.exit(main())
