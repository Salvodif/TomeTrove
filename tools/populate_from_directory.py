import argparse
"""
Scans a specified directory for PDF files, parses their filenames to extract metadata,
standardizes the filenames, copies them into a structured library, and adds metadata
to a TinyDB database.

Purpose of the script:
1.  Scans a user-specified directory (`directory_to_scan`) for PDF files.
2.  Parses filenames to extract metadata. The expected filename format is:
    "Title - Author - Tag1, Tag2, TagN.pdf".
    - The "Title" and "Author" parts are mandatory.
    - The "Tags" part is optional. If present, tags should be comma-separated.
3.  Generates a standardized filename for each book, typically in the format:
    "Sanitized Title - Sanitized Author.pdf".
    Special characters in title and author are replaced or removed.
4.  Copies the original PDF file to a structured library directory. The structure is:
    `library_path/AuthorName/StandardizedName.pdf`.
    - `library_path` is retrieved from `config.json`.
    - The `AuthorName` directory is created if it doesn't exist.
5.  Adds the extracted book metadata (title, author, tags, standardized filename, etc.)
    to the TinyDB database specified in `config.json`.

Command-line arguments:
-   `directory_to_scan` (positional): Path to the directory containing the PDF
    files that need to be imported.
-   `--config_dir` (optional): Path to the directory containing the `config.json`
    file. Defaults to the current working directory. This config file is crucial
    as it tells the script where to find the TinyDB database (`tinydb_file_name`)
    and the root of the book library (`library_path`).

Filename parsing details:
-   The script expects filenames in the format: "Title - Author - Tags.pdf".
-   Example: "The Great Gatsby - F. Scott Fitzgerald - Classic, Literature.pdf"
-   If the " - Tags" part is omitted, the book will have no tags.
    Example: "The Old Man and the Sea - Ernest Hemingway.pdf"
-   If parsing fails (e.g., missing author), the file is skipped.

Dependencies:
-   Relies on `ConfigManager` (from `configmanager.py`) and `LibraryManager`, `Book`
    (from `models.py`) which are part of the TomeTrove project structure.
-   Implicitly requires Python libraries such as `tinydb`, as typically listed
    in the project's `requirements.txt`.

Example Usage:
1.  If `config.json` is in the project root `/path/to/TomeTrove/`:
    `python tools/populate_from_directory.py /path/to/my_new_pdfs --config_dir /path/to/TomeTrove/`

2.  If `config.json` is in the current working directory (e.g., you are running
    the script from the project root where `config.json` is located):
    `python tools/populate_from_directory.py "/path/to/my_new_pdfs"`
    (Use quotes if paths contain spaces).

    For Windows:
    `python tools\\populate_from_directory.py "C:\\Users\\YourName\\Downloads\\New Books"`
"""
import argparse
import os
import sys
import logging
import shutil # Added shutil
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

# Adjust sys.path to correctly import project modules
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from configmanager import ConfigManager
from models import LibraryManager, Book # Added Book import

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def generate_standardized_filename(title: str, author: str) -> str:
    """
    Generates a standardized filename from a title and author.
    Format: "Sanitized Title - Sanitized Author.pdf"
    """
    
    invalid_chars = r'/\?%*:|"<>' # Characters invalid in many filesystems
    
    def _sanitize_component(text: str) -> str:
        if not text:
            return ""
        # Replace invalid characters with an underscore
        for char in invalid_chars:
            text = text.replace(char, '_')
        
        # Replace sequences of whitespace with a single space
        text = ' '.join(text.split())
        
        # Strip leading/trailing whitespace (though ' '.join(text.split()) also handles this)
        text = text.strip()
        return text

    sanitized_title = _sanitize_component(title)
    sanitized_author = _sanitize_component(author)

    if not sanitized_title:
        sanitized_title = "Unknown Title"
    if not sanitized_author:
        sanitized_author = "Unknown Author"
        
    return f"{sanitized_title} - {sanitized_author}.pdf"

def parse_filename(pdf_filename_str: str) -> tuple[str | None, str | None, list[str]]:
    """
    Parses a PDF filename to extract title, author, and tags.
    Expected format: "Title - Author - Tag1, Tag2.pdf"
    """
    filename_lower = pdf_filename_str.lower()
    if filename_lower.endswith(".pdf"):
        name_part = pdf_filename_str[:-4]
    else:
        name_part = pdf_filename_str

    parts = name_part.split(" - ")
    
    title = None
    author = None
    tags = []

    if len(parts) < 2:
        # Do not log warning here, will be handled by the caller
        return None, None, []
    
    title = parts[0].strip()
    author = parts[1].strip()

    if len(parts) >= 3:
        tags_str = " - ".join(parts[2:]).strip() 
        if tags_str:
            tags = [tag.strip() for tag in tags_str.split(",")]
            tags = [tag for tag in tags if tag] 

    return title, author, tags

def main():
    parser = argparse.ArgumentParser(description="Populate database from PDF files in a directory.")
    parser.add_argument("directory_to_scan", type=str, help="Path to the directory containing PDFs.")
    parser.add_argument(
        "--config_dir",
        type=str,
        default=os.getcwd(),
        help="Path to the directory containing config.json (default: current working directory).",
    )
    args = parser.parse_args()

    logging.info("Script starting...") # Added
    logging.info("Parsed arguments:")
    logging.info(f"  Directory to scan: {args.directory_to_scan}")
    logging.info(f"  Config directory: {args.config_dir}")

    library_manager = None # Initialize to None for finally block

    try:
        config_json_path = Path(args.config_dir) / "config.json"
        logging.info(f"Attempting to load config from: {config_json_path}")

        if not config_json_path.is_file():
            raise FileNotFoundError(f"Config file not found at {config_json_path}")

        config_manager = ConfigManager(config_path=str(config_json_path)) # Corrected here
        
        tinydb_file_name = config_manager.paths.get("tinydb_file_name")
        library_path_str = config_manager.paths.get("library_path")

        if not tinydb_file_name:
            raise RuntimeError("tinydb_file_name not found in config.json")
        if not library_path_str:
            raise RuntimeError("library_path not found in config.json")

        logging.info(f"  Loaded tinydb_file_name: {tinydb_file_name}")
        logging.info(f"  Loaded library_path: {library_path_str}")

        # Ensure library_path_str is a directory
        library_path_obj = Path(library_path_str)
        if not library_path_obj.is_dir():
            logging.info(f"Library path {library_path_obj} does not exist. Creating it.")
            library_path_obj.mkdir(parents=True, exist_ok=True)


        library_manager = LibraryManager(library_root_path=library_path_str, db_file_name=tinydb_file_name) # Corrected here
        logging.info("LibraryManager initialized successfully.")

        directory_to_scan_path = Path(args.directory_to_scan)
        
        if not directory_to_scan_path.is_dir():
            logging.error(f"The specified path '{args.directory_to_scan}' is not a valid directory or does not exist.")
            sys.exit(1)

        logging.info(f"Scanning directory '{directory_to_scan_path}' for PDF files...")
        
        pdf_files = list(directory_to_scan_path.glob('*.pdf'))
        
        if not pdf_files:
            logging.info(f"No PDF files found in '{directory_to_scan_path}'.")
        else:
            logging.info(f"Found {len(pdf_files)} PDF file(s). Processing...")
            for pdf_path in pdf_files:
                pdf_filename = pdf_path.name
                logging.info(f"Processing file: {pdf_filename}")

                title, author, tags = parse_filename(pdf_filename)

                if title is None or author is None:
                    logging.warning(f"Could not parse title/author from filename: '{pdf_filename}'. Skipping.")
                    continue
                
                new_std_filename = generate_standardized_filename(title, author)
                
                book_uuid = str(uuid4())
                added_date = datetime.now(timezone.utc)

                book = Book(
                    uuid=book_uuid,
                    author=author, # Original author name for directory
                    title=title,
                    added=added_date,
                    tags=tags,
                    filename=new_std_filename, # Use standardized filename
                    other_formats=[],
                    series=None,
                    num_series=None,
                    description=None,
                    read=None
                )

                copy_successful = False
                destination_pdf_path = None # Initialize for logging

                try:
                    author_dir_path_str = library_manager.books.ensure_directory(book.author) # Use original author for dir
                    destination_pdf_path = Path(author_dir_path_str) / new_std_filename
                    
                    if destination_pdf_path.exists():
                        logging.warning(f"File '{new_std_filename}' already exists at '{destination_pdf_path}'. Skipping copy for original '{pdf_filename}'.")
                        copy_successful = True # File is already there, so treat as success for DB addition
                    else:
                        shutil.copy2(pdf_path, destination_pdf_path)
                        logging.info(f"Copied '{pdf_filename}' to '{destination_pdf_path}'")
                        copy_successful = True
                
                except (IOError, shutil.Error) as e:
                    logging.error(f"Failed to copy '{pdf_filename}' to '{destination_pdf_path if destination_pdf_path else 'destination'}'. Error: {e}")
                    copy_successful = False
                except Exception as e: # Catch other potential errors from ensure_directory etc.
                    logging.error(f"An unexpected error occurred during file handling for '{pdf_filename}'. Error: {e}")
                    copy_successful = False

                if copy_successful:
                    try:
                        library_manager.books.add_book(book)
                        logging.info(f"Successfully added to DB: '{book.title}' by {book.author} (UUID: {book.uuid}, Filename: {book.filename})")
                    except ValueError as ve:
                        logging.error(f"Failed to add book '{book.title}' to DB. Validation Error: {ve} (Original: {pdf_filename})")
                    except Exception as e:
                        logging.error(f"Failed to add book '{book.title}' to DB. Unexpected Error: {e} (Original: {pdf_filename})")
                else:
                    logging.warning(f"Skipping database entry for '{title}' by {author} (Original: {pdf_filename}) due to file copy/handling failure.")

    except FileNotFoundError as e:
        logging.error(f"Configuration Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        logging.error(f"Runtime Error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)
    finally:
        if library_manager:
            library_manager.close()
            logging.info("LibraryManager closed.")

if __name__ == "__main__":
    # The main() function is called to run the script's primary logic.
    main()
    logging.info("Script finished.")
