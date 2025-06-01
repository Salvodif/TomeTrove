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

        paths_config = config_data.get('paths')

        if not paths_config or not isinstance(paths_config, dict):
            logger.error(f":x: [bold red]'paths' section not found or not a valid object in {CONFIG_FILE_PATH}. Script cannot continue.[/]")
            sys.exit(1)

        library_root_path_str = paths_config.get('library_path')
        db_file_path_str = paths_config.get('tinydb_file') # This is a full path

        if not library_root_path_str:
            logger.error(f":x: [bold red]'paths.library_path' not found or empty in {CONFIG_FILE_PATH}. Script cannot continue.[/]")
            sys.exit(1)
        if not db_file_path_str:
            logger.error(f":x: [bold red]'paths.tinydb_file' not found or empty in {CONFIG_FILE_PATH}. Script cannot continue.[/]")
            sys.exit(1)

        # The BookManager's library_root parameter is used for constructing book file paths.
        # The BookManager's db_file_name, if it's an absolute path, will be used as is by TinyDB.
        # Path objects are good for robust path handling.
        library_root = str(Path(library_root_path_str).resolve())
        db_file_name = str(Path(db_file_path_str).resolve()) # Pass the resolved absolute path

        logger.info(f"Successfully loaded configuration: LIBRARY_ROOT='{library_root}', DB_FILE_NAME (full path)='{db_file_name}'")
        return library_root, db_file_name

    except FileNotFoundError:
        logger.error(f":x: [bold red]Configuration file {CONFIG_FILE_PATH} not found. Please ensure it exists in the project root. Script cannot continue.[/]")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f":x: [bold red]Error decoding JSON from {CONFIG_FILE_PATH}. Please check its format. Script cannot continue.[/]")
        sys.exit(1)
    except Exception as e:
        logger.error(f":x: [bold red]An unexpected error occurred while loading config: {e}. Script cannot continue.[/]")
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
    processed_nonseries_books = 0 # New counter
    files_moved_or_renamed = 0
    db_filenames_updated = 0
    skipped_due_to_missing_num_series = 0 # Specific to series books attempt
    skipped_due_to_invalid_num_series = 0 # Specific to series books attempt
    files_not_found = 0
    skipped_path_op_due_to_invalid_dir = 0 # New counter

    for book in all_books:
        original_db_filename = book.filename
        author_fs = FormValidators.author_to_fsname(book.author)
        title_fs = FormValidators.title_to_fsname(book.title)

        # Determine file extension robustly
        file_extension = Path(original_db_filename).suffix if original_db_filename and original_db_filename.strip() else ""
        if not file_extension and book.other_formats and len(book.other_formats) > 0 and book.other_formats[0]:
            file_extension = Path(book.other_formats[0]).suffix
            logger.info(f"Used extension '{file_extension}' from other_formats for [bold]'{book.title}'[/bold].")
        if not file_extension:
            logger.info(f"Book [bold]'{book.title}'[/bold] has no detectable file extension. Defaulting to '.pdf' for new filename construction.")
            file_extension = '.pdf'

        is_series_book_for_path_and_filename = bool(book.series and book.series.strip() and book.num_series is not None)

        current_file_to_move = None # Path object or None
        new_parent_dir_path = None  # Path object
        target_db_filename = ""     # String
        final_destination_path = None # Path object

        if is_series_book_for_path_and_filename:
            processed_series_books += 1
            logger.info(f"Processing SERIES book: [bold magenta]'{book.title}'[/bold magenta] by '{author_fs}' (Series: {book.series})")

            series_fs = FormValidators.series_to_fsname(book.series)
            if not series_fs:
                logger.error(f":x: Cannot determine series directory for '{book.title}' (Series: '{book.series}'). Skipping path operations for this book.")
                skipped_path_op_due_to_invalid_dir += 1
                # Attempt to update filename if it's different, assuming it stays in author folder as a fallback
                # This part is tricky: if series dir is invalid, where should it go? For now, skip path ops.
                # Filename generation for series books (even if dir is problematic)
                try:
                    series_num_str = f"{int(float(book.num_series)):02d}"
                    target_db_filename = f"{series_num_str} - {author_fs} - {title_fs}{file_extension}"
                except (ValueError, TypeError):
                    target_db_filename = f"{author_fs} - {title_fs}{file_extension}" # Fallback
                    skipped_due_to_invalid_num_series +=1
                # DB update logic is common at the end, so it will be handled if target_db_filename is set
            else:
                new_parent_dir_path = Path(book_manager.library_root) / series_fs
                try:
                    series_num_str = f"{int(float(book.num_series)):02d}"
                    target_db_filename = f"{series_num_str} - {author_fs} - {title_fs}{file_extension}"
                except (ValueError, TypeError):
                    logger.warning(f":warning: Series book [bold]'{book.title}'[/bold] has invalid num_series [red]'{book.num_series}'[/red]. Filename: {author_fs} - {title_fs}{file_extension}")
                    target_db_filename = f"{author_fs} - {title_fs}{file_extension}"
                    skipped_due_to_invalid_num_series += 1
                final_destination_path = new_parent_dir_path / target_db_filename

            # Old File Location Detection for Series
            if original_db_filename and original_db_filename.strip():
                path_s_c1 = Path(book_manager.library_root) / author_fs / original_db_filename
                path_s_c2_dir_name = f"{author_fs} - {series_fs}" # Use current series_fs for this check
                path_s_c2 = Path(book_manager.library_root) / path_s_c2_dir_name / original_db_filename
                path_s_c3 = Path(book_manager.library_root) / series_fs / original_db_filename # Target series dir

                if path_s_c1.exists(): current_file_to_move = path_s_c1
                elif path_s_c2.exists(): current_file_to_move = path_s_c2
                elif path_s_c3.exists(): current_file_to_move = path_s_c3

                if current_file_to_move: logger.info(f"Found series file at: {current_file_to_move}")
                else:
                    logger.warning(f":warning: File [yellow]'{original_db_filename}'[/yellow] for series book [bold]'{book.title}'[/bold] not found.")
                    files_not_found += 1
            else:
                logger.info(f"Series book [bold]'{book.title}'[/bold] has no filename in DB. Cannot search.")

        else: # NON-SERIES BOOK LOGIC
            processed_nonseries_books += 1
            logger.info(f"Processing NON-SERIES book: [bold cyan]'{book.title}'[/bold cyan] by '{author_fs}'")

            if not author_fs:
                logger.error(f":x: Cannot determine author directory for non-series book '{book.title}'. Skipping path operations.")
                skipped_path_op_due_to_invalid_dir += 1
                target_db_filename = f"UNKNOWN_AUTHOR - {title_fs}{file_extension}" # Best guess for filename
            else:
                new_parent_dir_path = Path(book_manager.library_root) / author_fs
                target_db_filename = f"{author_fs} - {title_fs}{file_extension}"
                final_destination_path = new_parent_dir_path / target_db_filename

            # Old File Location Detection for Non-Series
            if original_db_filename and original_db_filename.strip():
                # Path NS1: Author_fs / original_db_filename
                path_ns_c1 = Path(book_manager.library_root) / author_fs / original_db_filename
                if path_ns_c1.exists():
                    current_file_to_move = path_ns_c1
                    logger.info(f"Found non-series file at: {current_file_to_move}")
                else:
                    # Path NS2: (Mistakenly in Author-Series folder?) - Less likely for non-series but possible if series info was removed
                    if book.series and book.series.strip(): # Check if it HAD series info
                        old_series_fs_ns = FormValidators.series_to_fsname(book.series)
                        path_ns_c2_dir = Path(book_manager.library_root) / f"{author_fs} - {old_series_fs_ns}"
                        path_ns_c2 = path_ns_c2_dir / original_db_filename
                        if path_ns_c2.exists():
                            current_file_to_move = path_ns_c2
                            logger.info(f"Found non-series file (was series?) at 'Author - Series' path: {current_file_to_move}")
                        else:
                           logger.warning(f":warning: File [yellow]'{original_db_filename}'[/yellow] for non-series book [bold]'{book.title}'[/bold] not found.")
                           files_not_found += 1
                    else:
                        logger.warning(f":warning: File [yellow]'{original_db_filename}'[/yellow] for non-series book [bold]'{book.title}'[/bold] not found in Author directory.")
                        files_not_found += 1
            else:
                logger.info(f"Non-series book [bold]'{book.title}'[/bold] has no filename in DB. Cannot search.")

        # --- COMMON FILE OPERATIONS & DB UPDATE (after if/else block) ---
        if new_parent_dir_path and final_destination_path: # Ensure target paths were determined
            if current_file_to_move: # If an old physical file was found
                if current_file_to_move.resolve() != final_destination_path.resolve():
                    try:
                        fs_handler.ensure_directory_exists(str(new_parent_dir_path))
                        fs_handler.rename_file(str(current_file_to_move), str(final_destination_path))
                        logger.info(f":white_check_mark: [green]MOVED/RENAMED:[/] '{current_file_to_move}' [bold]to[/] '{final_destination_path}'")
                        files_moved_or_renamed += 1
                    except Exception as e:
                        logger.error(f":x: [bold red]Error moving/renaming file for '{book.title}':[/] {e}")
                else:
                    logger.info(f"File for [bold]'{book.title}'[/bold] already at correct path and name: {final_destination_path}")
        elif current_file_to_move: # Old file found, but target path invalid (e.g. bad series/author name for dir)
             logger.warning(f"Old file {current_file_to_move} found for book '{book.title}', but target directory was invalid. File not moved.")


        if target_db_filename: # Ensure a target filename was determined
            if original_db_filename != target_db_filename or (not original_db_filename and target_db_filename):
                try:
                    book_manager.books_table.update({'filename': target_db_filename}, Query().uuid == book.uuid)
                    logger.info(f":floppy_disk: [blue]DB_UPDATE:[/] Filename for '{book.title}' to '{target_db_filename}' (UUID: {book.uuid})")
                    db_filenames_updated += 1
                except Exception as e:
                    logger.error(f":x: [bold red]Error updating DB for filename of '{book.title}' (UUID: {book.uuid}):[/] {e}")
            else: # Filename in DB is already correct
                # Log only if file was also correctly placed or if no move was needed.
                if (current_file_to_move and final_destination_path and current_file_to_move.resolve() == final_destination_path.resolve()) or not current_file_to_move :
                     logger.info(f"Filename for [bold]'{book.title}'[/bold] (UUID: {book.uuid}) in DB is already correct ('{target_db_filename}').")

    console.print("\n[bold cyan]--- Reorganization Summary ---[/bold cyan]")
    console.print(f"Total books scanned: [bold]{len(all_books)}[/bold]")
    console.print(f"Series books processed: [bold]{processed_series_books}[/bold]")
    console.print(f"Non-series books processed: [bold]{processed_nonseries_books}[/bold]") # New summary line
    console.print(f"Files moved/renamed: [bold green]{files_moved_or_renamed}[/bold green]")
    console.print(f"DB filenames updated: [bold blue]{db_filenames_updated}[/bold blue]")
    console.print(f"Series books skipped (missing num_series for filename prefix): [yellow]{skipped_due_to_missing_num_series}[/yellow]")
    console.print(f"Series books skipped (invalid num_series for filename prefix): [yellow]{skipped_due_to_invalid_num_series}[/yellow]")
    console.print(f"Books skipped (path op due to invalid dir name): [magenta]{skipped_path_op_due_to_invalid_dir}[/magenta]") # New summary line
    console.print(f"Original files not found: [red]{files_not_found}[/red]")
    console.print("[bold cyan]Reorganization script finished.[/bold cyan]")

    book_manager.close()

if __name__ == '__main__':
    reorganize()
