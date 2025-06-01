import logging
from pathlib import Path
import sys
import json # Added import
from tinydb import Query # Import Query directly

# Ensure project root is in path to allow imports from models, filesystem, etc.
# This assumes the script is in 'tools/' and project root is its parent.
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
CONFIG_FILE_PATH = project_root / 'config.json' # Defined CONFIG_FILE_PATH

# Now that sys.path is updated, we can import project modules
from models import Book, BookManager
from formvalidators import FormValidators
from filesystem import FileSystemHandler
from rich.console import Console
from rich.logging import RichHandler

# --- Logging Configuration ---
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s' # This format is mainly for the file handler
LOG_FILE_NAME = 'reorganize_library.log'

# Determine log file path (in the same directory as the script)
script_dir = Path(__file__).resolve().parent
log_file_path = script_dir / LOG_FILE_NAME

# Get root logger - configure it to add handlers
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO) # Set global level for logger

# Clear any existing handlers on the root logger (important for re-runs or if basicConfig was called)
if root_logger.hasHandlers():
    root_logger.handlers.clear()

# File Handler (setup first to ensure it gets the detailed LOG_FORMAT)
try:
    file_handler = logging.FileHandler(log_file_path, mode='a') # 'a' for append
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(file_handler)
except Exception as e:
    # If file handler fails, log to console (temporarily, if RichHandler also fails)
    # or just let it proceed if RichHandler is expected to work.
    # For now, logging this error to stderr directly before RichHandler might be set up.
    sys.stderr.write(f"Critical: Failed to initialize file logger at {log_file_path}: {e}\n")

# Rich Console Handler
# This will replace the standard StreamHandler for console output
rich_console_handler = RichHandler(
    console=Console(stderr=True), # Log to stderr
    markup=True,
    rich_tracebacks=True,
    log_time_format="[%X]", # Example: H:M:S, RichHandler controls its time format
    level=logging.INFO # Ensure RichHandler also respects the INFO level
)
# RichHandler does its own formatting, so we don't typically set a Formatter object on it
# like we do for the FileHandler. It will use the message from the LogRecord.
root_logger.addHandler(rich_console_handler)

# logger for this script module - will inherit from root_logger configuration
logger = logging.getLogger(__name__)

# Hardcoded configuration removed
# # Assume script is run from the project root directory
# LIBRARY_ROOT = '.'
# DB_FILE_NAME = 'test_library.json' # Or your actual DB name, e.g., 'library.json'

def load_config():
    logger = logging.getLogger(__name__)
    try:
        logger.debug(f"Attempting to load configuration from: {CONFIG_FILE_PATH}")
        with open(CONFIG_FILE_PATH, 'r') as f:
            config_data = json.load(f)

        library_root = config_data.get('library_root')
        db_file_name = config_data.get('db_file_name')

        if not library_root:
            logger.error(f"'library_root' not found or empty in {CONFIG_FILE_PATH}. Script cannot continue.")
            sys.exit(1)
        if not db_file_name:
            logger.error(f"'db_file_name' not found or empty in {CONFIG_FILE_PATH}. Script cannot continue.")
            sys.exit(1)

        logger.info(f"Successfully loaded configuration: LIBRARY_ROOT='{library_root}', DB_FILE_NAME='{db_file_name}'")
        return library_root, db_file_name

    except FileNotFoundError:
        logger.error(f"Configuration file {CONFIG_FILE_PATH} not found. Please ensure it exists in the project root. Script cannot continue.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {CONFIG_FILE_PATH}. Please check its format. Script cannot continue.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading config: {e}. Script cannot continue.")
        sys.exit(1)

def reorganize():
    console = Console() # Instantiate Rich Console
    console.print("[bold cyan]Starting library reorganization for series management...[/bold cyan]")
    # logger.info("Starting library reorganization for series management...") # Old way, replaced by console.print

    loaded_library_root, loaded_db_file_name = load_config() # Load config here

    book_manager = BookManager(loaded_library_root, loaded_db_file_name) # Use loaded values
    fs_handler = FileSystemHandler() # Assuming it's parameterless or defaults are fine

    all_books = book_manager.get_all_books()
    logger.info(f"Found {len(all_books)} books to process.")

    processed_series_books = 0
    files_moved_or_renamed = 0
    db_filenames_updated = 0
    skipped_due_to_missing_num_series = 0
    skipped_due_to_invalid_num_series = 0
    files_not_found = 0

    for book in all_books:
        if not (book.series and book.series.strip()):
            continue # Skip non-series books

        processed_series_books += 1
        logger.info(f"Processing series book: [bold magenta]'{book.title}'[/bold magenta] by '{book.author}' (Series: {book.series}, UUID: {book.uuid})")

        original_db_filename = book.filename
        if not original_db_filename:
            logger.warning(f":warning: Book [bold]'{book.title}'[/bold] (UUID: {book.uuid}) has no filename in DB. Skipping file operations, may update DB filename if possible.")
            # We might still generate a new_filename_only and update DB if other info is present

        # --- Old Path Construction ---
        old_author_fs = FormValidators.author_to_fsname(book.author)

        # Candidate 1: Author/filename.ext
        old_path_candidate1_parent = Path(book_manager.library_root) / old_author_fs
        old_file_path_candidate1 = old_path_candidate1_parent / original_db_filename if original_db_filename else None

        # Candidate 2: Author - Series/filename.ext (current series name, original filename)
        # This helps if the directory is correct but filename isn't, or if script is re-run
        current_series_fs = FormValidators.series_to_fsname(book.series)
        old_path_candidate2_parent_dir_name = f"{old_author_fs} - {current_series_fs}"
        old_path_candidate2_parent = Path(book_manager.library_root) / old_path_candidate2_parent_dir_name
        old_file_path_candidate2 = old_path_candidate2_parent / original_db_filename if original_db_filename else None

        actual_old_file_path = None
        if original_db_filename: # Only look for files if a filename exists in DB
            if old_file_path_candidate1 and old_file_path_candidate1.exists():
                actual_old_file_path = old_file_path_candidate1
                logger.info(f"Found file at primary old path: {actual_old_file_path}")
            elif old_file_path_candidate2 and old_file_path_candidate2.exists():
                actual_old_file_path = old_file_path_candidate2
                logger.info(f"Found file at secondary (series) old path: {actual_old_file_path}")
            else:
                logger.warning(f":warning: File for [bold]'{book.title}'[/bold] not found at expected old paths: {old_file_path_candidate1} or {old_file_path_candidate2}. Original: {original_db_filename}. Skipping file move.")
                files_not_found +=1
        else:
            logger.info(f"Book [bold]'{book.title}'[/bold] has no original filename in DB; cannot search for an existing file.")


        # --- New Filename Generation ---
        new_filename_only = original_db_filename # Default to original, change if possible
        title_fs = FormValidators.title_to_fsname(book.title)

        # Determine file extension
        file_extension = ""
        if original_db_filename:
            file_extension = Path(original_db_filename).suffix

        if not file_extension and book.other_formats:
            # Try to get extension from the first entry in other_formats
            if book.other_formats[0]:
                file_extension = Path(book.other_formats[0]).suffix
                logger.info(f"Used extension '{file_extension}' from other_formats for [bold]'{book.title}'[/bold].")

        if not file_extension:
            logger.warning(f":warning: Book [bold]'{book.title}'[/bold] has no detectable file extension. Defaulting to '.pdf'.")
            file_extension = '.pdf' # Default extension

        if book.num_series is None:
            logger.warning(f":warning: Book [bold]'{book.title}'[/bold] in series '{book.series}' (UUID: {book.uuid}) has no num_series. Filename will not include series number.")
            skipped_due_to_missing_num_series += 1
            new_filename_only = f"{title_fs}{file_extension}" # Filename without series number
        else:
            try:
                # Ensure num_series is treated as float first if it could be like "1.0"
                series_num_str = f"{int(float(book.num_series)):02d}"
                new_filename_only = f"{series_num_str} - {title_fs}{file_extension}"
            except (ValueError, TypeError):
                logger.warning(f":warning: Book [bold]'{book.title}'[/bold] (UUID: {book.uuid}) has invalid num_series [red]'{book.num_series}'[/red]. Filename will not include series number.")
                skipped_due_to_invalid_num_series += 1
                new_filename_only = f"{title_fs}{file_extension}" # Filename without series number


        # --- New Directory and Path Construction ---
        author_fs = FormValidators.author_to_fsname(book.author) # Re-get in case of changes, though unlikely here
        series_fs = FormValidators.series_to_fsname(book.series)
        new_parent_dir_name = f"{author_fs} - {series_fs}"
        new_parent_dir_path = Path(book_manager.library_root) / new_parent_dir_name
        new_full_file_path = new_parent_dir_path / new_filename_only

        # --- File Operations ---
        if actual_old_file_path: # If an existing file was found
            if actual_old_file_path.resolve() != new_full_file_path.resolve():
                try:
                    logger.info(f"Ensuring directory exists: {new_parent_dir_path}")
                    fs_handler.ensure_directory_exists(str(new_parent_dir_path))
                    logger.info(f"Attempting to move '{actual_old_file_path}' to '{new_full_file_path}'")
                    fs_handler.rename_file(str(actual_old_file_path), str(new_full_file_path))
                    logger.info(f":white_check_mark: [green]MOVED:[/] '{actual_old_file_path}' [bold]to[/] '{new_full_file_path}'")
                    files_moved_or_renamed +=1
                except Exception as e:
                    logger.error(f":x: [bold red]Error moving file for '{book.title}' (UUID: {book.uuid}):[/] {e}")
            else:
                logger.info(f"File [bold]'{book.title}'[/bold] (UUID: {book.uuid}) is already in the correct location and correctly named: {new_full_file_path}")
        elif original_db_filename: # File not found, but had a filename in DB
             logger.info(f"File for [bold]'{book.title}'[/bold] (UUID: {book.uuid}) was not found. If its DB filename needs updating, that will be handled next.")
        # If no original_db_filename and no actual_old_file_path, nothing to move.

        # --- Database Update for filename ---
        # Update if new filename is different from what's in DB, OR if DB filename was empty and we generated one.
        if original_db_filename != new_filename_only or (not original_db_filename and new_filename_only):
            try:
                book_manager.books_table.update({'filename': new_filename_only}, Query().uuid == book.uuid)
                logger.info(f":floppy_disk: [blue]DB_UPDATE:[/] Filename for '{book.title}' to '{new_filename_only}' (UUID: {book.uuid})")
                db_filenames_updated +=1
            except Exception as e:
                logger.error(f":x: [bold red]Error updating DB for filename of '{book.title}' (UUID: {book.uuid}):[/] {e}")
        else:
            logger.info(f"Filename for [bold]'{book.title}'[/bold] (UUID: {book.uuid}) in DB is already correct ('{new_filename_only}'). No DB update needed.")

    console.print("\n[bold cyan]--- Reorganization Summary ---[/bold cyan]")
    console.print(f"Total books scanned: [bold]{len(all_books)}[/bold]")
    console.print(f"Series books processed: [bold]{processed_series_books}[/bold]")
    console.print(f"Files moved/renamed: [bold green]{files_moved_or_renamed}[/bold green]")
    console.print(f"DB filenames updated: [bold blue]{db_filenames_updated}[/bold blue]")
    console.print(f"Books skipped (missing num_series): [yellow]{skipped_due_to_missing_num_series}[/yellow]")
    console.print(f"Books skipped (invalid num_series): [yellow]{skipped_due_to_invalid_num_series}[/yellow]")
    console.print(f"Original files not found: [red]{files_not_found}[/red]")
    console.print("[bold cyan]Reorganization script finished.[/bold cyan]")

    book_manager.close()

if __name__ == '__main__':
    reorganize()
