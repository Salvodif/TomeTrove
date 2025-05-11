import json
from pathlib import Path
from typing import Dict

class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Carica il file di configurazione JSON"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Errore nel caricamento del file di configurazione: {e}")

    def _save_config(self):
        """Salva le modifiche nel file di configurazione"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise RuntimeError(f"Errore nel salvataggio del file di configurazione: {e}")

    @property
    def paths(self) -> Dict[str, str]:
        """Restituisce i percorsi configurati"""
        return self.config.get('paths', {})

    def update_path(self, key: str, new_path: str):
        """
        Aggiorna un percorso specifico e salva le modifiche
        
        Args:
            key: Uno dei valori tra 'tinydb_file', 'library_path', 'upload_dir_path', 'exiftool_path'
            new_path: Il nuovo percorso da impostare
        """
        if key not in ['tinydb_file', 'library_path', 'upload_dir_path', 'exiftool_path']:
            raise ValueError(f"Chiave di percorso non valida: {key}")
        
        self.config['paths'][key] = str(new_path)
        self._save_config()

    def update_paths(self, new_paths: Dict[str, str]):
        """
        Aggiorna più percorsi contemporaneamente e salva le modifiche
        
        Args:
            new_paths: Dizionario con le nuove impostazioni dei percorsi
                     Esempio: {'tinydb_file': 'path.json', 'library_path': 'new/library/path'}
        """
        for key, path in new_paths.items():
            if key in ['tinydb_file', 'library_path', 'upload_dir_path', 'exiftool_path']:
                self.config['paths'][key] = str(path)
        
        self._save_config()
