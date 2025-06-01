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

from typing import Optional # Added for type hinting

class TestBookManagerFunctionality(unittest.TestCase): # Renamed class

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

    def _clear_all_books(self):
        """Helper to remove all books for tests needing a clean slate."""
        self.logger.debug("Clearing all books from BookManager for test.")
        all_books = list(self.book_manager.get_all_books()) # Get a copy of the list to iterate
        for book in all_books:
            try:
                # Need to remove the actual file too if it exists,
                # otherwise remove_book might fail or leave orphaned files.
                # This is tricky because remove_book itself tries to delete files.
                # For simplicity in tests, ensure files are removed if they exist,
                # or that remove_book can handle their absence.
                # Let's assume remove_book handles file deletion and its absence gracefully for now.
                # If a file associated with a book from setup doesn't exist, it's fine.
                # The core of the tests here isn't about file operations of remove_book.
                self.book_manager.remove_book(book.uuid)
            except Exception as e:
                self.logger.warning(f"Error clearing book {book.uuid} for test: {e}")
        # After removing, re-initialize cache and dirty flag might be good if remove_book doesn't fully reset.
        # However, a well-behaved remove_book should update the cache.
        # Let's assume BookManager's remove_book correctly updates its internal state.
        # Verify by checking if get_all_books is empty.
        if list(self.book_manager.get_all_books()):
             self.logger.error("Failed to clear all books for test.")
             # This might indicate an issue with remove_book or get_all_books after removal.

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
        # This test uses the initial book setup, so no need to clear.
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

    def test_get_all_series_names(self):
        self.logger.debug("Running test_get_all_series_names...")
        self._clear_all_books() # Ensure a clean slate

        common_added_date = datetime.now(timezone.utc)
        books_data = [
            Book(uuid="s1", title="T1", author="A", added=common_added_date, series="Alpha Series", filename="f1.pdf"),
            Book(uuid="s2", title="T2", author="A", added=common_added_date, series="Beta Series", filename="f2.pdf"),
            Book(uuid="s3", title="T3", author="A", added=common_added_date, series="Alpha Series", filename="f3.pdf"),
            Book(uuid="s4", title="T4", author="A", added=common_added_date, series=None, filename="f4.pdf"),
            Book(uuid="s5", title="T5", author="A", added=common_added_date, series="", filename="f5.pdf"),
            Book(uuid="s6", title="T6", author="A", added=common_added_date, series="gamma Series", filename="f6.pdf"),
        ]
        for book in books_data:
            # Create dummy files for these books if BookManager.add_book expects them
            # For this test, we only care about series names, so physical files might not be strictly needed
            # if add_book allows it or if we bypass file system interactions.
            # Assuming add_book is robust enough or we ensure necessary file structures if it's strict.
            # For simplicity, let's assume add_book doesn't strictly require file existence for this metadata test.
            # If add_book *does* require file existence and tries to manage them, this needs more setup.
            # Let's assume the focus is on the DB interaction for series names.
            # To be safe, let's create minimal author dirs and dummy files.
            author_fsname = FormValidators.author_to_fsname(book.author)
            author_dir = Path(self.library_root) / author_fsname
            author_dir.mkdir(parents=True, exist_ok=True)
            if book.filename:
                with open(author_dir / book.filename, "w") as f:
                    f.write("dummy")
            self.book_manager.add_book(book)

        series_names = self.book_manager.get_all_series_names()
        self.assertEqual(series_names, ["Alpha Series", "Beta Series", "gamma Series"])
        self.logger.debug("test_get_all_series_names completed.")

    def test_get_books_by_series(self):
        self.logger.debug("Running test_get_books_by_series...")
        self._clear_all_books()

        common_added_date = datetime.now(timezone.utc)
        book_a1 = Book(uuid="a1", title="Book A1", author="Auth", added=common_added_date, series="Series A", filename="a1.pdf")
        book_a2 = Book(uuid="a2", title="Book A2", author="Auth", added=common_added_date, series="Series A", filename="a2.pdf")
        book_b1 = Book(uuid="b1", title="Book B1", author="Auth", added=common_added_date, series="Series B", filename="b1.pdf")
        book_c1 = Book(uuid="c1", title="Book C1", author="Auth", added=common_added_date, series=None, filename="c1.pdf")

        books_to_add = [book_a1, book_a2, book_b1, book_c1]
        for book in books_to_add:
            author_fsname = FormValidators.author_to_fsname(book.author)
            author_dir = Path(self.library_root) / author_fsname
            author_dir.mkdir(parents=True, exist_ok=True)
            if book.filename:
                with open(author_dir / book.filename, "w") as f:
                    f.write("dummy")
            self.book_manager.add_book(book)

        books_a_results = self.book_manager.get_books_by_series("Series A")
        self.assertEqual(len(books_a_results), 2)
        result_uuids_a = sorted([b.uuid for b in books_a_results])
        self.assertEqual(result_uuids_a, ["a1", "a2"])

        books_b_results = self.book_manager.get_books_by_series("Series B")
        self.assertEqual(len(books_b_results), 1)
        self.assertEqual(books_b_results[0].uuid, "b1")

        books_none_results = self.book_manager.get_books_by_series("NonExistent Series")
        self.assertEqual(len(books_none_results), 0)

        books_empty_str_results = self.book_manager.get_books_by_series("")
        self.assertEqual(len(books_empty_str_results), 0) # Assuming series="" is not a valid query target
        self.logger.debug("test_get_books_by_series completed.")

    def _get_suggested_next_series_number(self, books_in_series: list[Book], current_book_uuid_to_exclude: Optional[str] = None) -> int:
        max_num_series = 0.0 # Use float for intermediate calcs
        found_valid_num = False

        for book in books_in_series:
            if current_book_uuid_to_exclude and book.uuid == current_book_uuid_to_exclude:
                continue
            if book.num_series is not None: # num_series can be str, int, float, or None
                try:
                    # Convert to string first to handle various numeric types robustly before float conversion
                    current_num = float(str(book.num_series))
                    if current_num > max_num_series:
                        max_num_series = current_num
                    found_valid_num = True
                except (ValueError, TypeError):
                    # Log this as it might indicate bad data, but don't fail the suggestion.
                    self.logger.debug(f"Could not parse num_series '{book.num_series}' for book '{book.uuid}' as float.")
                    pass # Ignore invalid num_series values for max calculation

        if found_valid_num:
            return int(max_num_series) + 1
        else:
            return 1

    def test_suggest_num_new_series(self):
        self.logger.debug("Running test_suggest_num_new_series...")
        self.assertEqual(self._get_suggested_next_series_number([]), 1)
        self.logger.debug("test_suggest_num_new_series completed.")

    def test_suggest_num_existing_series_no_numbers(self):
        self.logger.debug("Running test_suggest_num_existing_series_no_numbers...")
        book1 = Book(uuid="s1", title="T1", series="S", num_series=None, author="A", added=datetime.now(timezone.utc), filename="f.pdf")
        self.assertEqual(self._get_suggested_next_series_number([book1]), 1)
        self.logger.debug("test_suggest_num_existing_series_no_numbers completed.")

    def test_suggest_num_existing_series_with_numbers(self):
        self.logger.debug("Running test_suggest_num_existing_series_with_numbers...")
        dt = datetime.now(timezone.utc)
        books = [
            Book(uuid="s1", title="T1", series="S", num_series=1, author="A", added=dt, filename="f1.pdf"),
            Book(uuid="s2", title="T2", series="S", num_series=2, author="A", added=dt, filename="f2.pdf"),
            Book(uuid="s3", title="T3", series="S", num_series=4, author="A", added=dt, filename="f3.pdf"),
        ]
        self.assertEqual(self._get_suggested_next_series_number(books), 5)
        self.logger.debug("test_suggest_num_existing_series_with_numbers completed.")

    def test_suggest_num_existing_series_with_float_numbers(self):
        self.logger.debug("Running test_suggest_num_existing_series_with_float_numbers...")
        dt = datetime.now(timezone.utc)
        books = [
            Book(uuid="s1", title="T1", series="S", num_series=1.0, author="A", added=dt, filename="f1.pdf"),
            Book(uuid="s2", title="T2", series="S", num_series=2.5, author="A", added=dt, filename="f2.pdf"),
        ]
        # int(2.5) + 1 = 2 + 1 = 3
        self.assertEqual(self._get_suggested_next_series_number(books), 3)
        self.logger.debug("test_suggest_num_existing_series_with_float_numbers completed.")

    def test_suggest_num_existing_series_with_invalid_numbers(self):
        self.logger.debug("Running test_suggest_num_existing_series_with_invalid_numbers...")
        dt = datetime.now(timezone.utc)
        books = [
            Book(uuid="s1", title="T1", series="S", num_series="abc", author="A", added=dt, filename="f1.pdf"),
            Book(uuid="s2", title="T2", series="S", num_series=2.0, author="A", added=dt, filename="f2.pdf"),
            Book(uuid="s3", title="T3", series="S", num_series=None, author="A", added=dt, filename="f3.pdf"),
        ]
        # Max valid is 2.0, so suggests 3
        self.assertEqual(self._get_suggested_next_series_number(books), 3)
        self.logger.debug("test_suggest_num_existing_series_with_invalid_numbers completed.")

    def test_suggest_num_edit_mode_excludes_current_book(self):
        self.logger.debug("Running test_suggest_num_edit_mode_excludes_current_book...")
        dt = datetime.now(timezone.utc)
        book1 = Book(uuid="curr", title="Current", series="S", num_series=3.0, author="A", added=dt, filename="fc.pdf")
        book2 = Book(uuid="oth1", title="Other1", series="S", num_series=1.0, author="A", added=dt, filename="f1.pdf")
        book3 = Book(uuid="oth2", title="Other2", series="S", num_series=5.0, author="A", added=dt, filename="f2.pdf")
        self.assertEqual(self._get_suggested_next_series_number([book1, book2, book3], current_book_uuid_to_exclude="curr"), 6)

        book4 = Book(uuid="curr2", title="Current2", series="S", num_series=5.0, author="A", added=dt, filename="fc2.pdf")
        book5 = Book(uuid="oth3", title="Other3", series="S", num_series=1.0, author="A", added=dt, filename="f3.pdf")
        self.assertEqual(self._get_suggested_next_series_number([book4, book5], current_book_uuid_to_exclude="curr2"), 2)

        book6 = Book(uuid="curr3", title="Current3", series="S", num_series=1.0, author="A", added=dt, filename="fc3.pdf")
        self.assertEqual(self._get_suggested_next_series_number([book6], current_book_uuid_to_exclude="curr3"), 1)

        # Test case: current book is the only one with a high number, others are lower or none
        book7 = Book(uuid="curr4", title="Current4", series="S", num_series=10.0, author="A", added=dt, filename="fc4.pdf")
        book8 = Book(uuid="oth4", title="Other4", series="S", num_series=2.0, author="A", added=dt, filename="f4.pdf")
        book9 = Book(uuid="oth5", title="Other5", series="S", num_series=None, author="A", added=dt, filename="f5.pdf")
        self.assertEqual(self._get_suggested_next_series_number([book7, book8, book9], current_book_uuid_to_exclude="curr4"), 3)
        self.logger.debug("test_suggest_num_edit_mode_excludes_current_book completed.")


if __name__ == '__main__':
    # This allows running the tests directly from this file
    # For more complex setups, you might run tests using 'python -m unittest discover'
    unittest.main()
