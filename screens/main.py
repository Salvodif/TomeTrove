from pathlib import Path
from functools import partial # For passing arguments to callbacks

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Header, Footer, DataTable # Added DataTable for type hint clarity

from tools.logger import AppLogger
from configmanager import ConfigManager
from formvalidators import FormValidators # Assuming this has English-friendly or internal validation
from filesystem import FileSystemHandler # Assuming this has English-friendly or internal methods
from messages import BookAdded
from widgets.datatablebook import DataTableBook # Assuming this is our custom DataTable
from models import LibraryManager, Book # Added Book for type hint clarity
from screens.add import AddScreen
from screens.edit import EditScreen
from screens.settings import SettingsScreen # Renamed from Settings for clarity if it's a screen
from screens.inputscreen import InputScreen
from screens.confirmationscreen import ConfirmationScreen # Import the new confirmation screen


class MainScreen(Screen):
    BINDINGS = [
        ("ctrl+f", "search_book", "Search"),
        ("f5", "reset_search", "Reset Search"),
        ("e", "edit_book", "Edit"),
        ("ctrl+a", "add_book", "Add"),
        ("ctrl+r", "reverse_sort", "Sort Order"), # "Order" changed to "Sort Order" for clarity
        ("ctrl+o", "open_book", "Open"),
        ("ctrl+s", "settings", "Settings"),
        ("ctrl+e", "delete_book_action", "Delete Book") # Changed action name to avoid conflict if any base class has 'delete_book'
    ]

    def __init__(self, config_manager: ConfigManager, library_manager: LibraryManager):
        super().__init__()
        self.config_manager = config_manager
        self.library_manager = library_manager
        self.main_upload_dir = config_manager.paths["upload_dir_path"]
        self.logger = AppLogger.get_logger() # Assuming AppLogger.get_logger() is fine

        self.sort_reverse = True # Default to newest first for 'added'
        self.sort_field = "added" # Default sort field
        # self.theme = "nord" # Theme setting, if used

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTableBook(id="books-table"), # Our custom DataTable for books
            id="main-container")
        yield Footer()

    def on_mount(self) -> None:
        """Load initial data when the screen is mounted."""
        self.reload_table_data()

    def _format_tags_for_books(self, books: list[Book]) -> list[str]:
        """Helper method to format tags for a list of books."""
        formatted_tags_list = []
        for book in books:
            if book.tags and isinstance(book.tags, list):
                # Join the tag strings directly, ensuring tags are strings and not empty
                formatted_tags_list.append(", ".join(str(tag) for tag in book.tags if tag))
            else:
                formatted_tags_list.append("") # Append an empty string if the book has no tags
        return formatted_tags_list

    def _display_books_in_table(self, books: list[Book]) -> None:
        """Formats tags and updates the DataTable with the given books."""
        table = self.query_one("#books-table", DataTableBook)
        formatted_tags = self._format_tags_for_books(books)
        table.update_table(books, formatted_tags) # Assuming update_table handles empty lists

    def reload_table_data(self) -> None:
        """Reloads books from the library manager based on current sort order and updates the table."""
        books = self.library_manager.books.sort_books(self.sort_field, reverse=self.sort_reverse)
        self._display_books_in_table(books)

    def action_edit_book(self) -> None:
        """Handles the edit book action."""
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
        """Handles the add book action."""
        self.app.push_screen(AddScreen(self.library_manager.books, self.main_upload_dir))

    def action_settings(self) -> None:
        """Opens the settings screen."""
        # Assuming SettingsScreen is the correct name if it's a Screen class
        self.app.push_screen(SettingsScreen(self.config_manager))


    def action_open_book(self) -> None:
        """Handles the open book action."""
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

            # Validate author name for filesystem compatibility
            is_valid, fs_name_or_error = FormValidators.validate_author_name(book.author)
            if not is_valid:
                self.notify(f"Invalid author name for path: {fs_name_or_error}", severity="error", title="Path Error")
                return

            # Get full book path
            book_path_str = self.library_manager.books.get_book_path(book)

            # Check if file exists
            if not Path(book_path_str).exists():
                self.notify(f"File not found: {book_path_str}", severity="error", title="File Error")
                return

            # Open the book with the default application
            FileSystemHandler.open_file_with_default_app(book_path_str)

        except ValueError as e: # Catch specific errors like invalid book data for path
            self.logger.error(f"Error preparing to open book: {e}", exc_info=True)
            self.notify(f"Error: {str(e)}", severity="error", title="Open Error")
        except RuntimeError as e: # Catch errors from FileSystemHandler.open_file_with_default_app
            self.logger.error(f"Error opening book file: {e}", exc_info=True)
            self.notify(f"Could not open file: {str(e)}", severity="error", title="Open Error")
        except Exception as e:
            self.logger.error("Unexpected error during open book action.", exc_info=e)
            self.notify(f"An unexpected error occurred: {str(e)}", severity="error", title="Error")


    def _handle_delete_confirmation(self, confirmed: bool, book_uuid: str) -> None:
        """Callback for the delete confirmation dialog."""
        if not confirmed:
            self.notify("Book deletion cancelled.", title="Cancelled")
            return

        book_to_delete = self.library_manager.books.get_book(book_uuid)
        if not book_to_delete:
            self.notify(f"Book with UUID {book_uuid} not found for deletion.", severity="error", title="Error")
            return

        try:
            book_path_str = ""
            # 1. Get the full path of the book file (if a filename exists)
            if book_to_delete.filename:
                try:
                    book_path_str = self.library_manager.books.get_book_path(book_to_delete)
                except ValueError as e:
                    self.logger.warning(
                        f"Could not determine path for book '{book_to_delete.title}' "
                        f"(filename: {book_to_delete.filename}): {e}. File may not be deleted."
                    )
            
            # 2. Remove the book from the TinyDB database
            self.library_manager.books.remove_book(book_to_delete.uuid)
            self.logger.info(
                f"Book removed from DB: '{book_to_delete.title}' "
                f"(Author: {book_to_delete.author}, UUID: {book_to_delete.uuid})"
            )

            # 3. Delete the book file from the filesystem
            deleted_file_msg = ""
            if book_path_str:  # Only if a valid path was determined
                book_file = Path(book_path_str)
                if book_file.exists():
                    try:
                        book_file.unlink()  # Delete the file
                        self.logger.info(f"Book file deleted from filesystem: {book_path_str}")
                        deleted_file_msg = " and its file"
                    except OSError as e:
                        self.logger.error(f"Error deleting file {book_path_str}: {e}")
                        self.notify(
                            f"Error deleting file: {e}. The book record was removed from the DB.",
                            severity="error", title="File Deletion Error"
                        )
                else:
                    self.logger.warning(f"Book file not found in filesystem for deletion: {book_path_str}")
            elif book_to_delete.filename: # Filename existed but path couldn't be resolved
                 self.logger.warning(
                    f"File '{book_to_delete.filename}' associated with book '{book_to_delete.title}' "
                    f"was not deleted (path could not be determined)."
                )


            self.reload_table_data()  # Update the table display
            self.notify(f"Book '{book_to_delete.title}'{deleted_file_msg} successfully deleted.", title="Deleted")

        except Exception as e:
            self.logger.error(f"Unexpected error during book deletion '{book_to_delete.title}': {e}", exc_info=True)
            self.notify(f"Error during deletion: {str(e)}", severity="error", title="Deletion Error")


    def action_delete_book_action(self) -> None: # Renamed to avoid potential conflicts
        """Handles the delete book action with confirmation."""
        table = self.query_one("#books-table", DataTableBook)
        book_uuid = table.current_uuid

        if not book_uuid:
            self.notify("No book selected for deletion.", severity="warning", title="Selection Missing")
            return

        book_to_delete = self.library_manager.books.get_book(book_uuid)
        if not book_to_delete:
            # This case should ideally not happen if current_uuid is valid and from the table
            self.notify(f"Book with UUID {book_uuid} not found.", severity="error", title="Error")
            return

        prompt_message = (
            f"Are you sure you want to permanently delete the book:\n"
            f"'{book_to_delete.title}' by {book_to_delete.author}?\n\n"
            f"This action will also delete the associated file (if found) and cannot be undone."
        )
        
        # Use functools.partial to pass book_uuid to the callback
        # Or a lambda: callback=lambda confirmed: self._handle_delete_confirmation(confirmed, book_uuid)
        callback_with_uuid = partial(self._handle_delete_confirmation, book_uuid=book_uuid)
        
        self.app.push_screen(
            ConfirmationScreen(prompt=prompt_message, confirm_label="Delete", cancel_label="Cancel"),
            callback=callback_with_uuid # Pass the callable that will receive the boolean result
        )


    def action_reverse_sort(self) -> None:
        """Reverses the sort order or changes the sort column."""
        table = self.query_one("#books-table", DataTableBook)
        
        # Mapping from column index to field name
        # Ensure this matches the order of columns in your DataTableBook
        column_mapping = {
            0: "added",    # Assuming 'Added Date' is the first column
            1: "author",   # Assuming 'Author' is the second
            2: "title",    # Assuming 'Title' is the third
            3: "read",     # Assuming 'Read Date' is the fourth
            4: "tags"      # Assuming 'Tags' is the fifth
        }

        current_cursor_column = table.cursor_column # Get the current column index of the cursor
        
        new_sort_field = self.sort_field # Default to current sort field
        if current_cursor_column is not None and current_cursor_column in column_mapping:
            new_sort_field = column_mapping[current_cursor_column]

        if self.sort_field == new_sort_field:
            # If sorting by the same field, just toggle reverse
            self.sort_reverse = not self.sort_reverse
        else:
            # If changing to a new field, set it and default reverse (e.g., False, or True for 'added')
            self.sort_field = new_sort_field
            # Default sort order for 'added' is descending (newest first), ascending for others.
            self.sort_reverse = True if self.sort_field == "added" else False
        
        self.reload_table_data() # Reload and display sorted books

    def on_book_added(self, event: BookAdded) -> None:
        """Updates the table when a new book is added."""
        self.reload_table_data()
        # The event.book might contain the added book's details if needed
        self.notify("Book added successfully!", title="Success")


    def action_search_book(self) -> None: # Renamed from action_search
        """Opens an input box for searching books."""
        def handle_search_query(query: str) -> None:
            if query:
                # Perform search using the library manager's method
                books = self.library_manager.books.search_books_by_text(query)
                if books:
                    self._display_books_in_table(books)
                    self.notify(f"Found {len(books)} book(s) matching '{query}'.", title="Search Results")
                else:
                    self._display_books_in_table([]) # Clear table or show no results
                    self.notify(f"No books found matching '{query}'.", title="Search Results")
            else: # If query is empty, reset to show all books
                self.action_reset_search()

        self.app.push_screen(
            InputScreen(
                title="Search Book", # Translated
                placeholder="Enter title or author...", # Translated
                callback=handle_search_query
            )
        )

    def action_reset_search(self) -> None:
        """Resets the search and shows all books in the current sort order."""
        self.reload_table_data()
        self.notify("Search reset. Displaying all books.", title="Search Reset")