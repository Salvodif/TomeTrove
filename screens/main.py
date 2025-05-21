--- START OF FILE screens/main.py ---
import os # Added for os.listdir
from pathlib import Path
from functools import partial # For passing arguments to callbacks

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container # Removed Horizontal, Vertical as they are not directly used here
from textual.widgets import Header, Footer, DataTable # Added DataTable for type hint clarity

from tools.logger import AppLogger
from configmanager import ConfigManager
from formvalidators import FormValidators
from filesystem import FileSystemHandler
from messages import BookAdded
from widgets.datatablebook import DataTableBook
from models import LibraryManager, Book
from screens.add import AddScreen
from screens.edit import EditScreen
from screens.settings import Settings # Corrected from SettingsScreen based on previous error
from screens.inputscreen import InputScreen
from screens.confirmationscreen import ConfirmationScreen


class MainScreen(Screen):
    BINDINGS = [
        ("ctrl+f", "search_book", "Search"),
        ("f5", "reset_search", "Reset Search"),
        ("e", "edit_book", "Edit"),
        ("ctrl+a", "add_book", "Add"),
        ("ctrl+r", "reverse_sort", "Sort Order"),
        ("ctrl+o", "open_book", "Open"),
        ("ctrl+s", "settings", "Settings"),
        ("ctrl+e", "delete_book_action", "Delete Book")
    ]

    def __init__(self, config_manager: ConfigManager, library_manager: LibraryManager):
        super().__init__()
        self.config_manager = config_manager
        self.library_manager = library_manager
        self.main_upload_dir = config_manager.paths["upload_dir_path"]
        self.logger = AppLogger.get_logger()

        self.sort_reverse = True
        self.sort_field = "added"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTableBook(id="books-table"),
            id="main-container")
        yield Footer()

    def on_mount(self) -> None:
        self.reload_table_data()

    def _format_tags_for_books(self, books: list[Book]) -> list[str]:
        formatted_tags_list = []
        for book in books:
            if book.tags and isinstance(book.tags, list):
                formatted_tags_list.append(", ".join(str(tag) for tag in book.tags if tag))
            else:
                formatted_tags_list.append("")
        return formatted_tags_list

    def _display_books_in_table(self, books: list[Book]) -> None:
        table = self.query_one("#books-table", DataTableBook)
        formatted_tags = self._format_tags_for_books(books)
        table.update_table(books, formatted_tags)

    def reload_table_data(self) -> None:
        books = self.library_manager.books.sort_books(self.sort_field, reverse=self.sort_reverse)
        self._display_books_in_table(books)

    def action_edit_book(self) -> None:
        table = self.query_one("#books-table", DataTableBook)
        book_uuid = table.current_uuid
        if book_uuid:
            book_to_edit = self.library_manager.books.get_book(book_uuid)
            if book_to_edit:
                self.app.push_screen(EditScreen(self.library_manager.books, book_to_edit))
            else:
                self.notify(f"Book with UUID {book_uuid} not found.", severity="error", title="Error")
        else:
            self.notify("No book selected to edit.", severity="warning", title="Selection Missing")

    def action_add_book(self) -> None:
        self.app.push_screen(AddScreen(self.library_manager.books, self.main_upload_dir))

    def action_settings(self) -> None:
        self.app.push_screen(Settings(self.config_manager))

    def action_open_book(self) -> None:
        try:
            table = self.query_one("#books-table", DataTableBook)
            book_uuid = table.current_uuid
            if not book_uuid:
                self.logger.warning("Attempt to open book without selection.")
                self.notify("No book selected.", severity="warning", title="Selection Missing")
                return

            book = self.library_manager.books.get_book(book_uuid)
            if not book:
                self.logger.error(f"Book with UUID {book_uuid} not found for opening.")
                self.notify(f"Book not found.", severity="error", title="Error")
                return

            is_valid, fs_name_or_error = FormValidators.validate_author_name(book.author)
            if not is_valid:
                self.notify(f"Invalid author name for path: {fs_name_or_error}", severity="error", title="Path Error")
                return

            book_path_str = self.library_manager.books.get_book_path(book)
            if not Path(book_path_str).exists():
                self.notify(f"File not found: {book_path_str}", severity="error", title="File Error")
                return
            FileSystemHandler.open_file_with_default_app(book_path_str)

        except ValueError as e:
            self.logger.error(f"Error preparing to open book: {e}", exc_info=True)
            self.notify(f"Error: {str(e)}", severity="error", title="Open Error")
        except RuntimeError as e:
            self.logger.error(f"Error opening book file: {e}", exc_info=True)
            self.notify(f"Could not open file: {str(e)}", severity="error", title="Open Error")
        except Exception as e:
            self.logger.error("Unexpected error during open book action.", exc_info=e)
            self.notify(f"An unexpected error occurred: {str(e)}", severity="error", title="Error")

    def _handle_delete_confirmation(self, confirmed: bool, book_uuid: str) -> None:
        if not confirmed:
            self.notify("Book deletion cancelled.", title="Cancelled")
            return

        book_to_delete = self.library_manager.books.get_book(book_uuid)
        if not book_to_delete:
            self.notify(f"Book with UUID {book_uuid} not found for deletion.", severity="error", title="Error")
            return

        book_title_for_msg = book_to_delete.title # Store for notification

        try:
            # 1. Remove the book from the TinyDB database
            self.library_manager.books.remove_book(book_to_delete.uuid)
            self.logger.info(
                f"Book removed from DB: '{book_title_for_msg}' "
                f"(Author: {book_to_delete.author}, UUID: {book_to_delete.uuid})"
            )

            # 2. Attempt to delete the book file from the filesystem
            file_operation_message_part = ""
            book_path_str = ""
            if book_to_delete.filename:
                try:
                    book_path_str = self.library_manager.books.get_book_path(book_to_delete)
                except ValueError as e:
                    self.logger.warning(
                        f"Could not determine path for book '{book_title_for_msg}' "
                        f"(filename: {book_to_delete.filename}): {e}. File may not be deleted."
                    )
                    file_operation_message_part = " (file path not resolved)"

            if book_path_str:  # A path was determined
                book_file = Path(book_path_str)
                if book_file.exists():
                    try:
                        book_file.unlink()
                        self.logger.info(f"Book file deleted from filesystem: {book_path_str}")
                        file_operation_message_part = " and its file"
                    except OSError as e:
                        self.logger.error(f"Error deleting file {book_path_str}: {e}")
                        file_operation_message_part = " (file deletion failed)"
                else:
                    self.logger.warning(f"Book file not found in filesystem for deletion: {book_path_str}")
                    file_operation_message_part = " (file not found)"
            elif book_to_delete.filename and not file_operation_message_part:
                 # This case is if filename exists but get_book_path failed earlier and set file_operation_message_part
                 # If file_operation_message_part is still empty, it means get_book_path didn't even run (e.g. invalid author early)
                 # However, the current logic determines book_path_str first, so this specific branch might be redundant
                 # if the `except ValueError` for `get_book_path` already sets `file_operation_message_part`.
                 # For safety, we can log if filename exists but no specific file message part was set.
                 self.logger.warning(
                    f"File '{book_to_delete.filename}' associated with book '{book_title_for_msg}' "
                    f"was not actioned (path resolution issue or other pre-check)."
                )
                 if not file_operation_message_part : file_operation_message_part = " (file not actioned)"


            # 3. Check and delete author's directory if empty
            dir_deleted_message_part = ""
            # Sanitize author name for filesystem and construct potential directory path
            book_author_fs_name = FormValidators.author_to_fsname(book_to_delete.author)
            if book_author_fs_name: # Only proceed if author name is valid for a directory
                author_dir_path = Path(self.library_manager.books.library_root) / book_author_fs_name
                
                if author_dir_path.exists() and author_dir_path.is_dir():
                    library_root_path = Path(self.library_manager.books.library_root)
                    # Safety check: ensure it's a subdirectory of the library root and not the root itself
                    if author_dir_path != library_root_path and library_root_path in author_dir_path.parents:
                        if not os.listdir(str(author_dir_path)): # Check if empty
                            try:
                                author_dir_path.rmdir() # Delete empty directory
                                self.logger.info(f"Empty author directory deleted: {author_dir_path}")
                                dir_deleted_message_part = " and empty author directory"
                            except OSError as e:
                                self.logger.error(f"Could not delete empty author directory {author_dir_path}: {e}")
                                dir_deleted_message_part = " (author dir not deleted due to error)"
                        else:
                            self.logger.info(f"Author directory {author_dir_path} is not empty, not deleted.")
                    else:
                        self.logger.warning(f"Skipping author directory deletion for an invalid or root path: {author_dir_path}")
                else:
                    self.logger.info(f"Author directory for '{book_author_fs_name}' not found or not a directory, not attempting deletion.")
            
            self.reload_table_data()
            self.notify(f"Book '{book_title_for_msg}' deleted from DB{file_operation_message_part}{dir_deleted_message_part}.", title="Deleted")

        except Exception as e:
            self.logger.error(f"Unexpected error during book deletion '{book_title_for_msg}': {e}", exc_info=True)
            self.notify(f"Error during deletion: {str(e)}", severity="error", title="Deletion Error")

    def action_delete_book_action(self) -> None:
        table = self.query_one("#books-table", DataTableBook)
        book_uuid = table.current_uuid
        if not book_uuid:
            self.notify("No book selected for deletion.", severity="warning", title="Selection Missing")
            return

        book_to_delete = self.library_manager.books.get_book(book_uuid)
        if not book_to_delete:
            self.notify(f"Book with UUID {book_uuid} not found.", severity="error", title="Error")
            return

        prompt_message = (
            f"Are you sure you want to permanently delete the book:\n"
            f"'{book_to_delete.title}' by {book_to_delete.author}?\n\n"
            f"This action will remove it from the database, attempt to delete the "
            f"associated file, and remove the author's directory if it becomes empty. "
            f"This cannot be undone."
        )
        callback_with_uuid = partial(self._handle_delete_confirmation, book_uuid=book_uuid)
        self.app.push_screen(
            ConfirmationScreen(prompt=prompt_message, confirm_label="Delete", cancel_label="Cancel"),
            callback=callback_with_uuid
        )

    def action_reverse_sort(self) -> None:
        table = self.query_one("#books-table", DataTableBook)
        column_mapping = { 0: "added", 1: "author", 2: "title", 3: "read", 4: "tags" }
        current_cursor_column = table.cursor_column
        new_sort_field = self.sort_field
        if current_cursor_column is not None and current_cursor_column in column_mapping:
            new_sort_field = column_mapping[current_cursor_column]

        if self.sort_field == new_sort_field:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_field = new_sort_field
            self.sort_reverse = True if self.sort_field == "added" else False
        self.reload_table_data()

    def on_book_added(self, event: BookAdded) -> None:
        self.reload_table_data()
        self.notify("Book added successfully!", title="Success")

    def action_search_book(self) -> None:
        def handle_search_query(query: str) -> None:
            if query:
                books = self.library_manager.books.search_books_by_text(query)
                if books:
                    self._display_books_in_table(books)
                    self.notify(f"Found {len(books)} book(s) matching '{query}'.", title="Search Results")
                else:
                    self._display_books_in_table([])
                    self.notify(f"No books found matching '{query}'.", title="Search Results")
            else:
                self.action_reset_search()
        self.app.push_screen(
            InputScreen(title="Search Book", placeholder="Enter title or author...", callback=handle_search_query)
        )

    def action_reset_search(self) -> None:
        self.reload_table_data()
        self.notify("Search reset. Displaying all books.", title="Search Reset")