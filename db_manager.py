import json, os, shutil
from datetime import datetime

class DBManager:
    @staticmethod
    def load(file, default):
        if not os.path.exists(file): return default
        with open(file, 'r', encoding='utf-8') as f: return json.load(f)

    @staticmethod
    def save(file, data):
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        if not os.path.exists('backups'): os.makedirs('backups')
        backup_name = f"backups/{file.replace('.json', '')}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        shutil.copy(file, backup_name)
