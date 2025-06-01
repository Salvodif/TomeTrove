import logging
from pathlib import Path
import sys
from tinydb import Query # Import Query directly

# Ensure project root is in path to allow imports from models, filesystem, etc.
# This assumes the script is in 'tools/' and project root is its parent.
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Now that sys.path is updated, we can import project modules
from models import Book, BookManager # Assuming models.py is in project_root or accessible via PYTHONPATH
from formvalidators import FormValidators # Assuming formvalidators.py is in project_root
from filesystem import FileSystemHandler # Assuming filesystem.py is in project_root

# --- Configuration ---
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__) # Use a specific logger for the script

# Assume script is run from the project root directory
LIBRARY_ROOT = '.'
DB_FILE_NAME = 'test_library.json' # Or your actual DB name, e.g., 'library.json'

def reorganize():
    logger.info("Starting library reorganization for series management...")

    book_manager = BookManager(LIBRARY_ROOT, DB_FILE_NAME)
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
        logger.info(f"Processing series book: '{book.title}' by '{book.author}' (Series: {book.series}, UUID: {book.uuid})")

        original_db_filename = book.filename
        if not original_db_filename:
            logger.warning(f"Book '{book.title}' (UUID: {book.uuid}) has no filename in DB. Skipping file operations, may update DB filename if possible.")
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
                logger.warning(f"File for '{book.title}' not found at expected paths: {old_file_path_candidate1} or {old_file_path_candidate2}.")
                files_not_found +=1
        else:
            logger.info(f"Book '{book.title}' has no original filename in DB; cannot search for an existing file.")


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
                logger.info(f"Used extension '{file_extension}' from other_formats for '{book.title}'.")

        if not file_extension:
            logger.warning(f"Book '{book.title}' has no detectable file extension. Defaulting to '.pdf'.")
            file_extension = '.pdf' # Default extension

        if book.num_series is None:
            logger.warning(f"Book '{book.title}' in series '{book.series}' (UUID: {book.uuid}) has no num_series. Filename will not include series number.")
            skipped_due_to_missing_num_series += 1
            new_filename_only = f"{title_fs}{file_extension}" # Filename without series number
        else:
            try:
                # Ensure num_series is treated as float first if it could be like "1.0"
                series_num_str = f"{int(float(book.num_series)):02d}"
                new_filename_only = f"{series_num_str} - {title_fs}{file_extension}"
            except (ValueError, TypeError):
                logger.warning(f"Book '{book.title}' (UUID: {book.uuid}) has invalid num_series '{book.num_series}'. Filename will not include series number.")
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
                    logger.info(f"MOVED: '{actual_old_file_path}' to '{new_full_file_path}'")
                    files_moved_or_renamed +=1
                except Exception as e:
                    logger.error(f"Error moving file for '{book.title}' (UUID: {book.uuid}): {e}")
            else:
                logger.info(f"File '{book.title}' (UUID: {book.uuid}) is already in the correct location and correctly named: {new_full_file_path}")
        elif original_db_filename: # File not found, but had a filename in DB
             logger.info(f"File for '{book.title}' (UUID: {book.uuid}) was not found. If its DB filename needs updating, that will be handled next.")
        # If no original_db_filename and no actual_old_file_path, nothing to move.

        # --- Database Update for filename ---
        # Update if new filename is different from what's in DB, OR if DB filename was empty and we generated one.
        if original_db_filename != new_filename_only or (not original_db_filename and new_filename_only):
            try:
                book_manager.books_table.update({'filename': new_filename_only}, Query().uuid == book.uuid)
                logger.info(f"DB_UPDATE: Filename for '{book.title}' (UUID: {book.uuid}) updated to '{new_filename_only}'")
                db_filenames_updated +=1
            except Exception as e:
                logger.error(f"Error updating database filename for '{book.title}' (UUID: {book.uuid}): {e}")
        else:
            logger.info(f"Filename for '{book.title}' (UUID: {book.uuid}) in DB is already correct ('{new_filename_only}'). No DB update needed.")

    logger.info("--- Reorganization Summary ---")
    logger.info(f"Total books scanned: {len(all_books)}")
    logger.info(f"Series books processed: {processed_series_books}")
    logger.info(f"Files moved/renamed: {files_moved_or_renamed}")
    logger.info(f"DB filenames updated: {db_filenames_updated}")
    logger.info(f"Books skipped due to missing num_series (filename not prefixed): {skipped_due_to_missing_num_series}")
    logger.info(f"Books skipped due to invalid num_series (filename not prefixed): {skipped_due_to_invalid_num_series}")
    logger.info(f"Original files not found at expected locations: {files_not_found}")
    logger.info("Reorganization script finished.")

    book_manager.close()

if __name__ == '__main__':
    reorganize()
