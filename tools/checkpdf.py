import os
import sys
import re
from tinydb import TinyDB, Query
from colorama import init, Fore, Style

# Importa il tuo ConfigReader (codice invariato)
try:
    from config_reader import ConfigReader
except ImportError:
    print("Errore: Impossibile importare 'ConfigReader'.")
    print("Assicurati che il file 'config_reader.py' sia presente e accessibile.")
    sys.exit(1)
except Exception as e:
    print(f"Errore durante l'import di ConfigReader: {e}")
    sys.exit(1)

# Inizializza colorama (codice invariato)
init(autoreset=True)

# Definisci i colori (codice invariato)
COLOR_ERROR = Fore.RED
COLOR_WARNING = Fore.YELLOW
COLOR_INFO = Fore.CYAN
COLOR_DEBUG = Fore.MAGENTA
COLOR_RESET = Style.RESET_ALL

# --- Funzione Modificata ---
def clean_author_dirname(author_name: str) -> str:
    """
    Pulisce e normalizza il nome dell'autore per creare un nome di directory valido:
    - Gestisce "AA.VV." -> "AAVV".
    - Rimuove apostrofi (es. d'Aquino -> dAquino).
    - Sostituisce i punti (.) con uno spazio.
    - Normalizza spazi multipli in spazi singoli.
    - Rimuove caratteri non validi per i filesystem.
    - Mantiene gli spazi tra le parole.
    """
    if not author_name:
        return "_SENZA_AUTORE_"

    # 1. Gestione specifica AA.VV. (prima di altre pulizie)
    if author_name.strip().upper() == "AA.VV.":
        return "AAVV"

    # 2. Rimuovi apostrofi
    cleaned_name = author_name.replace("'", "")

    # 3. Sostituisci i punti con spazi
    cleaned_name = cleaned_name.replace(".", " ")

    # 4. Rimuovi caratteri non validi per i nomi di directory
    cleaned_name = re.sub(r'[<>:"/\\|?*]', '', cleaned_name)

    # 5. Normalizza spazi multipli e rimuovi spazi iniziali/finali
    #    split() senza argomenti gestisce spazi multipli e li rimuove
    #    ' '.join(...) rimette un singolo spazio tra le parti
    cleaned_name = ' '.join(cleaned_name.split())

    # 6. Controllo finale se il nome è diventato vuoto
    if not cleaned_name:
        return "_NOME_INVALIDO_"

    return cleaned_name
# --- Fine Funzione Modificata ---

def check_and_report_missing_files():
    """
    Legge library.json, controlla l'esistenza dei file PDF, raccoglie i problemi
    e stampa una lista riepilogativa finale colorata.
    (IL RESTO DELLA FUNZIONE RIMANE INVARIATO RISPETTO ALLA VERSIONE PRECEDENTE
     CON LA LISTA RIEPILOGATIVA)
    """
    # 1. Carica la configurazione (invariato)
    try:
        config = ConfigReader()
        db_path = config.DB
        library_base_path = config.LIBRARY
        if not db_path or not os.path.exists(db_path):
            print(f"{COLOR_ERROR}Errore: File database '{db_path}' non trovato o percorso non valido in config.json.")
            sys.exit(1)
        if not library_base_path or not os.path.isdir(library_base_path):
             print(f"{COLOR_ERROR}Errore: Percorso base libreria '{library_base_path}' non valido o non trovato in config.json.")
             sys.exit(1)
        print(f"{COLOR_INFO}Controllo database:{Style.RESET_ALL} {db_path}")
        print(f"{COLOR_INFO}Usando base libreria:{Style.RESET_ALL} {library_base_path}\n")
    except Exception as e:
        print(f"{COLOR_ERROR}Errore durante la lettura della configurazione: {e}")
        sys.exit(1)

    # 2. Apri il database TinyDB (invariato)
    try:
        db = TinyDB(db_path, encoding='utf-8')
        print(f"Database aperto. Numero record totali: {len(db)}.")
    except Exception as e:
        print(f"{COLOR_ERROR}Errore nell'aprire il database '{db_path}': {e}")
        sys.exit(1)

    # 3. Itera sui record e raccogli i problemi (invariato nella logica di raccolta)
    missing_filename_list = []
    file_not_found_list = []
    processed_count = 0
    all_books = db.all()
    total_records = len(all_books)
    print(f"Inizio controllo di {total_records} record...")

    for i, book in enumerate(all_books):
        processed_count += 1
        filename_value = book.get("filename")
        author_value = book.get("author")
        doc_id = book.doc_id
        title = book.get('title', 'Titolo Sconosciuto')

        # Stampa progresso (invariato)
        if (i + 1) % 50 == 0 or i == total_records - 1:
            print(f"\rControllo record {i+1}/{total_records}...", end="")
            sys.stdout.flush()

        if not filename_value:
            missing_filename_list.append({
                "doc_id": doc_id, "title": title, "reason": "Filename mancante/vuoto"
            })
            continue

        expected_path_normalized = None
        problem_details = f"(JSON 'filename': '{filename_value}'"

        if os.path.isabs(filename_value):
            expected_path_normalized = os.path.normpath(filename_value)
            problem_details += ", Tipo: Assoluto)"
            if not os.path.exists(expected_path_normalized):
                file_not_found_list.append({
                    "doc_id": doc_id, "title": title, "details": problem_details, "path_checked": expected_path_normalized
                })
        else:
            if not author_value:
                 missing_filename_list.append({
                    "doc_id": doc_id, "title": title, "reason": f"Autore mancante per filename relativo '{filename_value}'"
                 })
                 continue
            else:
                # USA LA NUOVA FUNZIONE DI PULIZIA
                cleaned_author_dir = clean_author_dirname(author_value)
                problem_details += f", Autore JSON: '{author_value}', Dir cercata: '{cleaned_author_dir}')"
                expected_path = os.path.join(library_base_path, cleaned_author_dir, filename_value)
                expected_path_normalized = os.path.normpath(expected_path)
                if not os.path.exists(expected_path_normalized):
                    file_not_found_list.append({
                        "doc_id": doc_id, "title": title, "details": problem_details, "path_checked": expected_path_normalized
                    })

    # Fine del loop, pulisci la riga del progresso (invariato)
    print("\r" + " " * 80 + "\r", end="")
    print("Controllo terminato.")

    # 4. Chiudi il database (invariato)
    db.close()

    # 5. Stampa la LISTA riepilogativa (invariato)
    total_problems = len(missing_filename_list) + len(file_not_found_list)
    if total_problems == 0:
        print(f"\n{Fore.GREEN}✅ Nessun problema rilevato.{Style.RESET_ALL}")
    else:
        print(f"\n--- Riepilogo Problemi ({total_problems} totali) ---")
        if missing_filename_list:
            print(f"\n{COLOR_WARNING}--- Filename o Autore Mancante ({len(missing_filename_list)}) ---{COLOR_RESET}")
            for problem in missing_filename_list:
                reason = problem.get('reason', 'Filename mancante/vuoto')
                print(f"  ID: {problem['doc_id']} - Titolo: {problem['title']}")
                print(f"    {COLOR_WARNING}Motivo:{COLOR_RESET} {reason}")
        if file_not_found_list:
            print(f"\n{COLOR_ERROR}--- File Non Trovato ({len(file_not_found_list)}) ---{COLOR_RESET}")
            for problem in file_not_found_list:
                print(f"  ID: {problem['doc_id']} - Titolo: {problem['title']}")
                print(f"    {COLOR_INFO}Dettagli:{COLOR_RESET} {problem['details']}")
                print(f"    {COLOR_ERROR}Percorso cercato:{COLOR_RESET} {problem['path_checked']}")
        print("\n--- Fine Riepilogo ---")

# --- Esecuzione dello script ---
if __name__ == "__main__":
    check_and_report_missing_files()