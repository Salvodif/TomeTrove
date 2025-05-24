
import os # Added for os.listdir
from pathlib import Path
from functools import partial # For passing arguments to callbacks

from typing import Optional, List # Added Optional, List
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
from screens.settings import SettingsScreen
from screens.inputscreen import InputScreen
from screens.confirmationscreen import ConfirmationScreen
from screens.serieslist import SeriesListScreen # Import SeriesListScreen


class MainScreen(Screen):
    """Main application screen for displaying and managing books."""
    BINDINGS = [
        ("ctrl+f", "search_book", "Search"),
        ("f5", "reset_search", "Reset Search"),
        ("e", "edit_book", "Edit"),
        ("ctrl+a", "add_book", "Add"),
        ("ctrl+r", "reverse_sort", "Sort Order"), # Toggle sort order for the current field
        ("ctrl+o", "open_book", "Open"),
        ("ctrl+s", "settings", "Settings"),
        ("ctrl+e", "delete_book_action", "Delete Book"),
        ("ctrl+p", "filter_by_series", "Filter Series"),
        ("alt+s", "show_series_list", "Series List")
    ]

    def __init__(self, config_manager: ConfigManager, library_manager: LibraryManager):
        super().__init__()
        self.config_manager = config_manager
        self.library_manager = library_manager
        self.current_series_filter: Optional[str] = None
        self.main_upload_dir = config_manager.paths["upload_dir_path"]
        self.logger = AppLogger.get_logger()

        # Default sort order: newest first
        self.sort_reverse = True 
        self.sort_field = "added"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTableBook(id="books-table"),
            id="main-container")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted. Loads initial table data."""
        self.reload_table_data()

    def _display_books_in_table(self, books: list[Book]) -> None:
        """Updates the DataTable with the provided list of books."""
        table = self.query_one("#books-table", DataTableBook)
        table.update_table(books)

    def reload_table_data(self) -> None:
        """Reloads and sorts books, then updates the table display."""
        books: List[Book] 
        if self.current_series_filter:
            books = self.library_manager.books.get_books_by_series(self.current_series_filter)
            # Sort the filtered books
            if books: # Ensure books list is not empty before trying to access books[0] or sorting
                # Determine sort key
                if self.sort_field == 'tags':
                    sort_key = lambda b: (", ".join(b.tags) if b.tags else "").lower()
                elif hasattr(books[0], self.sort_field):
                    sort_key = lambda b: (val.lower() if isinstance(val := getattr(b, self.sort_field), str) 
                                          else val if val is not None else "")
                else: # Fallback if sort_field is somehow invalid for the book object
                    sort_key = lambda b: ""
                
                books.sort(key=sort_key, reverse=self.sort_reverse)
        else:
            books = self.library_manager.books.sort_books(self.sort_field, reverse=self.sort_reverse)
        self._display_books_in_table(books)

    def action_filter_by_series(self) -> None:
        """Handles the 'filter_by_series' action: opens an input dialog for series name."""
        series_names = self.library_manager.books.get_all_series_names()
        if not series_names:
            self.notify("No series available to filter by.", title="Filter Series")
            return

        def handle_series_input(series_name_input: str) -> None:
            """Callback for the series input dialog."""
            series_name = series_name_input.strip()
            if not series_name:
                self.current_series_filter = None
                self.reload_table_data()
                self.notify("Series filter cleared. Displaying all books.", title="Filter Cleared")
                return

            if series_name not in series_names:
                self.notify(f"Series '{series_name}' not found. Displaying all books.", title="Filter Series", severity="warning")
                self.current_series_filter = None
                self.reload_table_data()
                return
            
            self.current_series_filter = series_name
            self.reload_table_data()
            self.notify(f"Showing books in series: '{series_name}'. Press F5 or Ctrl+P (empty) to reset.", title="Filter Active")

        self.notify(f"Available series: {', '.join(series_names)}", title="Available Series", timeout=8)
        self.app.push_screen(
            InputScreen(
                title="Filter by Series",
                placeholder="Enter series name (or empty to clear)",
                prompt="Type series name to filter. F5 also clears.",
                callback=handle_series_input
            )
        )

    def action_edit_book(self) -> None:
        """Handles the 'edit_book' action: opens the EditScreen for the selected book."""
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
        """Handles the 'add_book' action: opens the AddScreen."""
        self.app.push_screen(AddScreen(self.library_manager.books, self.main_upload_dir))

    def action_settings(self) -> None:
        """Handles the 'settings' action: opens the SettingsScreen."""
        self.app.push_screen(SettingsScreen(self.config_manager))

    def action_open_book(self) -> None:
        """Handles the 'open_book' action: opens the selected book file with the default application."""
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

    def _delete_book_from_database(self, book_to_delete: Book) -> bool:
        """Removes the book from the TinyDB database."""
        try:
            self.library_manager.books.remove_book(book_to_delete.uuid)
            self.logger.info(
                f"Book removed from DB: '{book_to_delete.title}' "
                f"(Author: {book_to_delete.author}, UUID: {book_to_delete.uuid})"
            )
            return True
        except Exception as e: # More general catch for potential DB issues
            self.logger.error(
                f"Error removing book '{book_to_delete.title}' (UUID: {book_to_delete.uuid}) from DB: {e}",
                exc_info=True
            )
            return False

    def _delete_book_file(self, book_to_delete: Book) -> tuple[bool, str]:
        """Deletes the book's physical file."""
        file_deleted = False
        message_part = ""

        if book_to_delete.filename:
            book_path_str = ""
            try:
                book_path_str = self.library_manager.books.get_book_path(book_to_delete)
            except ValueError as e:
                self.logger.warning(
                    f"Could not determine path for book '{book_to_delete.title}' "
                    f"(filename: {book_to_delete.filename}): {e}. File may not be deleted."
                )
                message_part = " (file path not resolved)"

            if book_path_str:
                book_file = Path(book_path_str)
                if book_file.exists():
                    try:
                        book_file.unlink()
                        file_deleted = True
                        self.logger.info(f"Book file deleted from filesystem: {book_path_str}")
                        message_part = " and its file"
                    except OSError as e:
                        self.logger.error(f"Error deleting file {book_path_str}: {e}")
                        message_part = " (file deletion failed)"
                else:
                    self.logger.warning(f"Book file not found for deletion: {book_path_str}")
                    message_part = " (file not found)"
            elif not message_part: # Filename exists, but path wasn't obtained and no specific error already set.
                self.logger.warning(
                    f"File '{book_to_delete.filename}' for book '{book_to_delete.title}' "
                    f"was not processed (e.g., path resolution issue)."
                )
                message_part = " (file not processed)"
        else:
            # No filename associated with the book, so no file to delete.
            # This is a normal case, not an error.
            message_part = "" # Or " (no file associated)" if explicit mention is desired
            
        return file_deleted, message_part

    def _delete_author_directory_if_empty(self, book_to_delete: Book) -> tuple[bool, str]:
        """Deletes the author's directory if it's empty."""
        dir_deleted = False
        message_part = ""
        
        book_author_fs_name = FormValidators.author_to_fsname(book_to_delete.author)
        if book_author_fs_name:
            author_dir_path = Path(self.library_manager.books.library_root) / book_author_fs_name
            
            if author_dir_path.exists() and author_dir_path.is_dir():
                library_root_path = Path(self.library_manager.books.library_root)
                # Safety check: ensure it's a subdirectory of the library root and not the root itself
                if author_dir_path != library_root_path and library_root_path in author_dir_path.parents:
                    try:
                        if not os.listdir(str(author_dir_path)): # Check if empty
                            author_dir_path.rmdir() # Delete empty directory
                            dir_deleted = True
                            self.logger.info(f"Empty author directory deleted: {author_dir_path}")
                            message_part = " and empty author directory"
                        else:
                            self.logger.info(f"Author directory {author_dir_path} is not empty, not deleted.")
                    except OSError as e:
                        self.logger.error(f"Could not delete empty author directory {author_dir_path}: {e}")
                        message_part = " (author dir not deleted due to error)"
                else:
                    self.logger.warning(f"Skipping author directory deletion for an invalid or root path: {author_dir_path}")
            else:
                self.logger.info(f"Author directory for '{book_author_fs_name}' not found or not a directory, not attempting deletion.")
        else:
            self.logger.warning(f"Could not determine valid filesystem name for author '{book_to_delete.author}', skipping directory deletion check.")

        return dir_deleted, message_part

    def _handle_delete_confirmation(self, confirmed: bool, book_uuid: str) -> None:
        """Callback for the delete confirmation dialog."""
        if not confirmed:
            self.notify("Book deletion cancelled.", title="Cancelled")
            return

        book_to_delete = self.library_manager.books.get_book(book_uuid)
        if not book_to_delete:
            self.notify(f"Book with UUID {book_uuid} not found for deletion.", severity="error", title="Error")
            return

        book_title_for_msg = book_to_delete.title 

        try:
            db_deleted = self._delete_book_from_database(book_to_delete)

            if db_deleted:
                _file_deleted, file_message_part = self._delete_book_file(book_to_delete)
                _dir_deleted, dir_message_part = self._delete_author_directory_if_empty(book_to_delete)
                
                self.reload_table_data()
                self.notify(
                    f"Book '{book_title_for_msg}' deleted from DB{file_message_part}{dir_message_part}.",
                    title="Deleted"
                )
            else:
                # If DB deletion failed, notify and potentially skip file/dir operations
                self.notify(
                    f"Failed to delete book '{book_title_for_msg}' from the database.",
                    severity="error",
                    title="Deletion Error"
                )

        except Exception as e:
            self.logger.error(f"Unexpected error during book deletion '{book_title_for_msg}': {e}", exc_info=True)
            self.notify(f"Error during deletion: {str(e)}", severity="error", title="Deletion Error")

    def action_delete_book_action(self) -> None:
        """Handles the 'delete_book_action': prompts for confirmation then deletes the selected book."""
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
        """Handles the 'reverse_sort' action: changes sort field or reverses current sort order."""
        table = self.query_one("#books-table", DataTableBook)
        # Updated column mapping for the new "Series" column
        column_mapping = { 0: "added", 1: "author", 2: "title", 3: "series", 4: "read", 5: "tags" }
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
        """Event handler for when a new book is added."""
        self.reload_table_data()
        self.notify("Book added successfully!", title="Success")

    def action_search_book(self) -> None:
        """Handles the 'search_book' action: opens an input dialog for search query."""
        def handle_search_query(query: str) -> None:
            """Callback for the search input dialog."""
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
        """Handles the 'reset_search' action: clears search and reloads all books."""
        self.current_series_filter = None
        self.reload_table_data()
        self.notify("All filters reset. Displaying all books.", title="Filters Reset")

    def action_show_series_list(self) -> None:
        """Handles the 'show_series_list' action: opens the SeriesListScreen."""
        self.logger.debug("MainScreen: action_show_series_list triggered.")
        self.app.push_screen(SeriesListScreen(self.library_manager))
