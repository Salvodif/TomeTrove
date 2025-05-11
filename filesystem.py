import os
import platform
import subprocess
from pathlib import Path

class FileSystemHandler:
    @staticmethod
    def open_file_with_default_app(file_path: str) -> bool:
        """Apre il file con l'applicazione predefinita del sistema"""
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", file_path], check=True)
            else:  # Linux e altri
                subprocess.run(["xdg-open", file_path], check=True)
            return True
        except Exception as e:
            raise RuntimeError(f"Impossibile aprire il file: {str(e)}")

    @staticmethod
    def is_valid_fs_path(path: str) -> bool:
        """Verifica se il percorso è valido per il filesystem"""
        try:
            Path(path)
            return True
        except (ValueError, OSError):
            return False

    @staticmethod
    def ensure_directory_exists(path: str) -> str:
        """Crea la directory se non esiste e restituisce il percorso assoluto"""
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True)
        return str(path_obj.absolute())