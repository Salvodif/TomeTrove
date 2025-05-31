import unittest
import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime, timezone
import logging # Optional: for debugging tests

# Assuming models.py, formvalidators.py, filesystem.py are in the parent directory (project root)
# If your project structure is different, you might need to adjust sys.path or use relative imports
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import BookManager, Book # noqa: E402
from formvalidators import FormValidators # noqa: E402
from filesystem import FileSystemHandler # noqa: E402

# Configure basic logging for tests (optional)
# logging.basicConfig(level=logging.DEBUG)

class TestBookManagerFileNameUpdates(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Setting up test case...")
        # Create a temporary directory for the library root
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.library_root = self.temp_dir_obj.name
        self.db_name = "test_db.json" # Using a specific name for clarity

        self.logger.debug(f"Temporary library root: {self.library_root}")

        # Initialize BookManager
        # Note: BookManager creates its db file inside library_root if db_file_name is relative
        self.book_manager = BookManager(library_root_path=self.library_root, db_file_name=self.db_name)

        # Ensure no old DB exists - BookManager handles DB creation, but good for sanity.
        db_path = Path(self.library_root) / self.db_name
        if db_path.exists():
            self.logger.debug(f"Deleting pre-existing test DB at {db_path}")
            db_path.unlink()
        # Re-initialize BookManager to ensure it creates a fresh DB
        self.book_manager.close() # Close previous instance if any
        self.book_manager = BookManager(library_root_path=self.library_root, db_file_name=self.db_name)


        # --- Initial Book for most tests ---
        self.initial_author = "Old Author"
        self.initial_title = "Old Title"
        self.initial_ext = ".pdf" # Common extension for testing
        self.initial_filename_stem = FormValidators.title_to_fsname(self.initial_title)
        self.initial_filename = self.initial_filename_stem + self.initial_ext

        self.initial_author_fsname = FormValidators.author_to_fsname(self.initial_author)
        self.author_dir_path = Path(self.library_root) / self.initial_author_fsname
        self.author_dir_path.mkdir(parents=True, exist_ok=True)

        self.initial_book_file_path = self.author_dir_path / self.initial_filename
        with open(self.initial_book_file_path, "w") as f:
            f.write("dummy content for old title")
        self.logger.debug(f"Created initial book file: {self.initial_book_file_path}")

        self.book_uuid = "test-uuid-12345"
        # Make sure 'added' is a datetime object as expected by Book dataclass
        added_datetime = datetime.now(timezone.utc)

        self.book_to_add = Book(
            uuid=self.book_uuid,
            author=self.initial_author,
            title=self.initial_title,
            added=added_datetime,
            filename=self.initial_filename,
            tags=[]
            # Optional fields like series, num_series, description, read will default to None or empty list
        )
        self.book_manager.add_book(self.book_to_add)
        self.logger.debug(f"Added initial book to DB: UUID {self.book_uuid}")

    def tearDown(self):
        self.logger.debug("Tearing down test case...")
        self.book_manager.close()
        self.temp_dir_obj.cleanup()
        self.logger.debug(f"Cleaned up temporary directory: {self.library_root}")

    def test_change_title(self):
        self.logger.debug("Running test_change_title...")
        new_title = "New Title For Book"
        new_filename_expected_stem = FormValidators.title_to_fsname(new_title)
        new_filename_expected = new_filename_expected_stem + self.initial_ext
        # File path remains in the same author's directory
        new_file_path_expected = self.author_dir_path / new_filename_expected

        self.book_manager.update_book(self.book_uuid, {"title": new_title})

        updated_book = self.book_manager.get_book(self.book_uuid) # Changed from get_book_by_uuid
        self.assertIsNotNone(updated_book, "Book not found after update")
        # updated_book is now directly a Book object

        self.assertEqual(updated_book.title, new_title)
        self.assertEqual(updated_book.filename, new_filename_expected)
        self.assertTrue(new_file_path_expected.exists(), f"New file path {new_file_path_expected} does not exist.")
        self.assertFalse(self.initial_book_file_path.exists(), f"Old file path {self.initial_book_file_path} still exists.")
        self.logger.debug("test_change_title completed.")


    def test_change_author(self):
        self.logger.debug("Running test_change_author...")
        new_author = "New Author Name"
        new_author_fsname = FormValidators.author_to_fsname(new_author)
        new_author_dir_path_expected = Path(self.library_root) / new_author_fsname

        # Filename itself (string) doesn't change based on author, but its directory location does
        new_file_path_expected = new_author_dir_path_expected / self.initial_filename

        self.book_manager.update_book(self.book_uuid, {"author": new_author})

        updated_book = self.book_manager.get_book(self.book_uuid) # Changed from get_book_by_uuid
        self.assertIsNotNone(updated_book, "Book not found after update")
        # updated_book is now directly a Book object

        self.assertEqual(updated_book.author, new_author)
        self.assertEqual(updated_book.filename, self.initial_filename) # Filename string in DB is unchanged
        self.assertTrue(new_author_dir_path_expected.exists(), f"New author directory {new_author_dir_path_expected} was not created.")
        self.assertTrue(new_file_path_expected.exists(), f"File was not moved to {new_file_path_expected}.")
        self.assertFalse(self.initial_book_file_path.exists(), f"Old file {self.initial_book_file_path} was not moved.")
        self.logger.debug("test_change_author completed.")

    def test_change_title_and_author(self):
        self.logger.debug("Running test_change_title_and_author...")
        new_title = "Another New Great Title"
        new_author = "Another New Great Author"

        new_filename_expected_stem = FormValidators.title_to_fsname(new_title)
        new_filename_expected = new_filename_expected_stem + self.initial_ext # Preserving original extension

        new_author_fsname = FormValidators.author_to_fsname(new_author)
        new_author_dir_path_expected = Path(self.library_root) / new_author_fsname
        new_file_path_expected = new_author_dir_path_expected / new_filename_expected

        self.book_manager.update_book(self.book_uuid, {"title": new_title, "author": new_author})

        updated_book = self.book_manager.get_book(self.book_uuid) # Changed from get_book_by_uuid
        self.assertIsNotNone(updated_book, "Book not found after update")
        # updated_book is now directly a Book object

        self.assertEqual(updated_book.title, new_title)
        self.assertEqual(updated_book.author, new_author)
        self.assertEqual(updated_book.filename, new_filename_expected)
        self.assertTrue(new_author_dir_path_expected.exists(), f"New author directory {new_author_dir_path_expected} was not created.")
        self.assertTrue(new_file_path_expected.exists(), f"New file {new_file_path_expected} does not exist.")
        self.assertFalse(self.initial_book_file_path.exists(), f"Old file {self.initial_book_file_path} still exists.")
        self.logger.debug("test_change_title_and_author completed.")

    def test_update_book_with_no_initial_filename_and_no_file(self):
        self.logger.debug("Running test_update_book_with_no_initial_filename_and_no_file...")
        no_file_uuid = "no-file-uuid-67890"
        no_file_author = "Author For No File Yet"
        no_file_title = "Title For No File Yet"

        no_file_book = Book(
            uuid=no_file_uuid,
            author=no_file_author,
            title=no_file_title,
            added=datetime.now(timezone.utc),
            filename="", # Explicitly no filename
            tags=[]
            # Optional fields will default
        )
        self.book_manager.add_book(no_file_book)
        self.logger.debug(f"Added book with no filename: {no_file_uuid}")

        updated_title = "Title Updated For Book That Had No File"
        # Assuming .epub is the default if not otherwise determinable, as per update_book logic
        # or if 'file_extension' is passed in new_data.
        # The `update_book` logic has a default of `.epub` if extension cannot be found.
        expected_new_filename = FormValidators.title_to_fsname(updated_title) + ".epub"

        self.book_manager.update_book(no_file_uuid, {"title": updated_title})

        updated_book = self.book_manager.get_book(no_file_uuid) # Changed from get_book_by_uuid
        self.assertIsNotNone(updated_book, "Book not found after update (no_file_uuid).")
        # updated_book is now directly a Book object

        self.assertEqual(updated_book.title, updated_title)
        self.assertEqual(updated_book.filename, expected_new_filename, "Filename in DB was not updated as expected.")

        # Check that no file was attempted to be created or renamed from a non-existent location
        # The main check is that filename in DB is correct and no errors occurred.
        # The actual file path for this new filename should not exist as no file was ever associated.
        expected_author_fsname = FormValidators.author_to_fsname(no_file_author) # Author didn't change
        expected_file_path = Path(self.library_root) / expected_author_fsname / expected_new_filename
        self.assertFalse(expected_file_path.exists(), f"File {expected_file_path} should not exist as it was never created.")
        self.logger.debug("test_update_book_with_no_initial_filename_and_no_file completed.")


    def test_file_extension_preservation(self):
        self.logger.debug("Running test_file_extension_preservation...")
        # Create a book with a different extension
        ext_book_uuid = "ext-uuid-abcde"
        ext_title = "Extension Test Title Special"
        ext_author = "Extension Test Author Special"
        ext_actual = ".mobi" # Using a different extension

        ext_filename_stem = FormValidators.title_to_fsname(ext_title)
        ext_filename = ext_filename_stem + ext_actual

        ext_author_fsname = FormValidators.author_to_fsname(ext_author)
        ext_author_dir_path = Path(self.library_root) / ext_author_fsname
        ext_author_dir_path.mkdir(parents=True, exist_ok=True)

        original_ext_book_file_path = ext_author_dir_path / ext_filename
        with open(original_ext_book_file_path, "w") as f:
            f.write("dummy mobi content")
        self.logger.debug(f"Created book file with extension {ext_actual}: {original_ext_book_file_path}")

        ext_book = Book(
            uuid=ext_book_uuid,
            author=ext_author,
            title=ext_title,
            added=datetime.now(timezone.utc),
            filename=ext_filename,
            tags=[]
            # Optional fields will default
        )
        self.book_manager.add_book(ext_book)
        self.logger.debug(f"Added book for extension test: {ext_book_uuid}")

        new_title_for_ext_test = "New Extension Test Title Special"
        new_filename_expected_stem = FormValidators.title_to_fsname(new_title_for_ext_test)
        # Crucially, the new filename must preserve the original .mobi extension
        new_filename_expected = new_filename_expected_stem + ext_actual
        new_file_path_expected = ext_author_dir_path / new_filename_expected

        self.book_manager.update_book(ext_book_uuid, {"title": new_title_for_ext_test})

        updated_book = self.book_manager.get_book(ext_book_uuid) # Changed from get_book_by_uuid
        self.assertIsNotNone(updated_book, "Book not found after update (ext_book_uuid).")
        # updated_book is now directly a Book object

        self.assertEqual(updated_book.filename, new_filename_expected)
        self.assertTrue(new_file_path_expected.exists(), f"New file path {new_file_path_expected} with preserved extension does not exist.")
        self.assertFalse(original_ext_book_file_path.exists(), f"Old file path {original_ext_book_file_path} with original extension still exists.")
        self.logger.debug("test_file_extension_preservation completed.")

if __name__ == '__main__':
    # This allows running the tests directly from this file
    # For more complex setups, you might run tests using 'python -m unittest discover'
    unittest.main()
