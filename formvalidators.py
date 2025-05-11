import re
import platform

class FormValidators:
    @staticmethod
    def validate_author_name(author_name: str) -> tuple[bool, str]:
        """Valida il nome dell'autore e restituisce la versione filesystem-safe"""
        if not author_name or not author_name.strip():
            return False, "Il nome dell'autore non può essere vuoto"

        fs_name = FormValidators.author_to_fsname(author_name)

        if platform.system() == "Windows":
            invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
        else:
            invalid_chars = r'[\x00-\x1F/]'

        if re.search(invalid_chars, fs_name):
            return False, f"Il nome contiene caratteri non validi: {fs_name}"

        return True, fs_name

    @staticmethod
    def author_to_fsname(author_name: str) -> str:
        """Converte il nome dell'autore in una versione filesystem-safe"""
        # Mantieni l'apostrofo e rimuovi solo altri caratteri speciali
        normalized = re.sub(r'[^\w\s\'-]', '', author_name)
        # Sostituisci spazi multipli con singolo spazio
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()

    @staticmethod
    def title_to_fsname(title: str) -> str:
        """Converte il titolo in una versione filesystem-safe"""
        # Rimuove caratteri speciali e normalizza
        normalized = re.sub(r'[^\w\s-]', '', title)
        # Sostituisci spazi multipli con singolo spazio
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()