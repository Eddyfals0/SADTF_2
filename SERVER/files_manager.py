import os
import json

files_persistent_file = os.path.join(os.path.dirname(__file__), 'info', 'files_data.json')


def load_persistent_files():
    try:
        if os.path.exists(files_persistent_file):
            with open(files_persistent_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    data = {'files': {}}
                else:
                    data = json.loads(content)
        else:
            data = {'files': {}}
        if 'files' not in data:
            data['files'] = {}
        return data
    except Exception as e:
        print(f"[FILES_MANAGER] Error cargando files persistentes: {e}")
        return {'files': {}}


def save_persistent_files(files_data):
    try:
        # files_data expected as {'files': {id: obj, ...}}
        with open(files_persistent_file, 'w', encoding='utf-8') as f:
            json.dump(files_data, f, indent=2, ensure_ascii=False)
        print(f"[FILES_MANAGER] Guardado {len(files_data.get('files', {}))} archivos en {files_persistent_file}")
    except Exception as e:
        print(f"[FILES_MANAGER] Error guardando files persistentes: {e}")
