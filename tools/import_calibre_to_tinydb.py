import json
import os
import shutil
import uuid
import logging
import subprocess

from datetime import datetime
from tinydb import TinyDB
from pathlib import Path



def setup_logging():
    """Configure logging"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"import_calibre_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # Also output to console
        ]
    )
    return log_file


def get_first_author(authors: list) -> str:
    """
    Estrae il primo autore dalla lista degli autori
    """
    logging.info(f"Getting first author from: {authors}")
    if not authors:
        return "Unknown Author"
    if isinstance(authors, str):
        return authors
    return authors[0]


def update_pdf_metadata_exiftool(pdf_path: str, title: str, author: str, tags: list) -> bool:
    try:
        tags_str = ", ".join(tags) if tags else ""
        subprocess.run([
            "D:\\exiftool-13.27_64\\exiftool",
            f"-Title={title}",
            f"-Author={author}",
            f"-Keywords={tags_str}",
            "-overwrite_original",  # Sovrascrive il file senza creare copie
            pdf_path
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Errore con exiftool: {e}")
        return False

def ensure_author_directory(base_path: str, author: str) -> str:
    """
    Crea la directory per l'autore se non esiste e ritorna il path
    """
    # Pulisce il nome dell'autore da caratteri non validi per il filesystem
    safe_author = "".join(c for c in author if c.isalnum() or c in (' ', '-', '_'))
    # Rimuove spazi multipli e spazi all'inizio/fine
    safe_author = " ".join(safe_author.split())
    author_path = os.path.join(base_path, safe_author)
    
    if not os.path.exists(author_path):
        os.makedirs(author_path)
    return author_path

def copy_non_pdf_to_library(formats: list, author: str, dest_base: str) -> list:
    """
    Copia i file non-PDF nella directory 'non-PDF' e ritorna la lista dei nuovi percorsi
    """
    if not formats:
        return []

    # Crea la directory non-PDF se non esiste
    non_pdf_dir = os.path.join(dest_base, "01 - non-PDF")
    if not os.path.exists(non_pdf_dir):
        os.makedirs(non_pdf_dir)

    copied_files = []
    for format_path in formats:
        if not format_path.lower().endswith('.pdf'):
            # Ottieni il nome originale del file
            original_filename = os.path.basename(format_path)
            # Pulisce il nome dell'autore da caratteri non validi
            safe_author = "".join(c for c in author if c.isalnum() or c in (' ', '-', '_'))
            # Crea il nuovo nome file: author-originalname
            new_filename = f"{safe_author}-{original_filename}"
            new_path = os.path.join(non_pdf_dir, new_filename)
            
            if os.path.exists(format_path):
                try:
                    shutil.copy2(format_path, new_path)
                    copied_files.append(new_path)
                    logging.info(f"File copiato nella cartella di destinazione: {new_path}")
                except Exception as e:
                    logging.error(f"Errore nella copia del file {format_path}: {e}")
    return copied_files


def copy_pdf_to_library(formats: list, authors: str, title: str, tags: list, dest_base: str) -> tuple[str, list]:
    """
    Copia il PDF nella directory dell'autore e i file non-PDF nella directory non-PDF
    Ritorna una tupla (pdf_path, non_pdf_paths)
    """
    first_author = get_first_author(authors)
    pdf_path = None
    # Gestione PDF
    for format_path in formats:
        if format_path.lower().endswith('.pdf'):
            pdf_path = format_path
            break
    
    if not pdf_path:
        logging.warning(f"Nessun PDF trovato per l'autore {first_author}. Formati disponibili: {formats}")
        return None, []

    # Crea la directory dell'autore
    author_dir = ensure_author_directory(dest_base, first_author)
    
    # Crea la directory per PDF senza metadati aggiornati
    no_metadata_dir = os.path.join(dest_base, "02 - PDF no metadata updated")
    if not os.path.exists(no_metadata_dir):
        os.makedirs(no_metadata_dir)
    
    # Costruisce il nuovo percorso per il PDF
    filename = os.path.basename(pdf_path)
    new_pdf_path = os.path.join(author_dir, filename)
    
    # Copia il file PDF e aggiorna i metadati
    if os.path.exists(pdf_path):
        shutil.copy2(pdf_path, new_pdf_path)
        if update_pdf_metadata_exiftool(new_pdf_path, title, first_author, tags):
            # Gestione altri formati
            non_pdf_paths = copy_non_pdf_to_library(formats, first_author, dest_base)
            return new_pdf_path, non_pdf_paths
        else:
            # Se l'aggiornamento dei metadati fallisce
            os.remove(new_pdf_path)  # Rimuove il file dalla directory dell'autore
            
            # Sposta il file nella directory "PDF no metadata updated"
            safe_author = "".join(c for c in first_author if c.isalnum() or c in (' ', '-', '_'))
            no_metadata_filename = f"{safe_author}-{filename}"
            no_metadata_path = os.path.join(no_metadata_dir, no_metadata_filename)
            
            # Copia il file originale nella nuova directory
            shutil.copy2(pdf_path, no_metadata_path)
            logging.warning(f"PDF spostato in 'PDF no metadata updated': {no_metadata_filename}")
            
            return no_metadata_path, []
    return None, []


def import_calibre_to_tinydb(json_path: str = None, db_path: str = None):
    """
    Importa i libri da Calibre a TinyDB e copia i file nella nuova struttura
    
    Args:
        json_path (str): Percorso al file JSON di Calibre
        db_path (str): Percorso dove salvare il database TinyDB
    """
    errors: int = 0
    processed: int = 0
    
    try:
        # Setup logging
        log_file = setup_logging()
        logging.info(f"Inizio importazione - Log file: {log_file}")
        
        # Configura i percorsi
        if json_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(current_dir, "calibre_books.json")
        
        dest_library_path = r"c:\MyDBTiny"

        if db_path is None:
            db_path = os.path.join(dest_library_path, "library.json")

        # Crea la directory di destinazione se non esiste
        if not os.path.exists(dest_library_path):
            os.makedirs(dest_library_path)

        # Leggi il file JSON
        for encoding in ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']:
            try:
                with open(json_path, 'r', encoding=encoding) as f:
                    calibre_data = json.load(f)
                errors += 1
                logging.info(f"File JSON letto correttamente con encoding: {encoding}")   
                break  # Se la lettura ha successo, esci dal loop
            except UnicodeDecodeError:
                errors += 1
                logging.debug(f"Tentativo fallito con encoding: {encoding}")
                continue  # Prova il prossimo encoding
            except json.JSONDecodeError:
                errors += 1
                logging.debug(f"JSON non valido con encoding: {encoding}")
                continue  # Prova il prossimo encoding
        else:
            # Se nessun encoding ha funzionato
            msg = f"Non è stato possibile leggere il file JSON con nessun encoding supportato: {json_path}"
            logging.error(msg)
            errors += 1
            raise ValueError(msg)

        # Usa il context manager per gestire la chiusura del db
        with TinyDB(db_path, encoding='utf-8') as db:
            # Processa ogni libro
            for book in calibre_data:
                try:
                    pdf_path = None
                    other_formats = []
                    if book.get("formats") and book.get("authors"):
                        logging.info(f"Authors from Calibre: {book.get('authors')}")

                        # Assicurati che authors sia una lista
                        authors = book.get("authors")
                        if isinstance(authors, str):
                            authors = [authors]
                
                        # Ottieni il primo autore
                        first_author = get_first_author(authors)
            
                        pdf_path, other_formats = copy_pdf_to_library(
                            book.get("formats"),
                            first_author,  # Passa la lista di autori
                            book.get("title"),
                            book.get("tags", []),
                            dest_library_path
                        )
                    
                    # Crea il documento per TinyDB
                    book_uuid = str(uuid.uuid4())
                    doc = {
                        "uuid": book_uuid,
                        "author": first_author,
                        "title": book.get("title"),
                        "added": book.get("last_modified"),  # '2025-04-11T14:20:38+00:00' controllare che il formato sia simile prima di inserire il dato
                        "tags": book.get("tags", []),
                        "filename": os.path.basename(pdf_path) if pdf_path else None,
                        "other_formats": [os.path.basename(p) for p in other_formats],
                        "series": book.get("series"),
                        "num_series": book.get("series_index"),
                        "desc": book.get("comments"),
                        "read": ""
                    }
                    
                    # Inserisci il documento usando l'UUID come chiave diretta
                    db.insert(doc)
                    processed += 1
                    logging.info(f"Libro '{book.get('title')}' inserito con UUID: {book_uuid}")

                    
                except Exception as e:
                    logging.error(f"Errore nel processare il libro {book.get('title', 'Unknown')}: {e}")
                    errors += 1

        logging.info(f"\nImportazione completata:")
        logging.info(f"Libri processati: {processed}")
        logging.info(f"Errori: {errors}")
        
        db.close()
        
        return True

    except Exception as e:
        logging.error(f"Errore nella lettura del file JSON: {e}")
        return False

if __name__ == "__main__":
    print("Inizio importazione da Calibre a TinyDB...")
    import_calibre_to_tinydb()