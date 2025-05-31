from typing import List
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Header, Footer, Label
from models import Book, LibraryManager
from widgets.datatablebook import DataTableBook
from tools.logger import AppLogger # Assuming AppLogger is the standard logger

class SeriesBooksScreen(Screen):
    """A screen to display books belonging to a specific series."""
    
    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, library_manager: LibraryManager, series_name: str, books: List[Book]):
        super().__init__()
        self.library_manager = library_manager
        self.series_name = series_name
        self.books = books
        self.logger = AppLogger.get_logger()
        self.logger.info(f"SeriesBooksScreen initialized for series: {self.series_name} with {len(self.books)} books.")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"Books in Series: {self.series_name}", classes="title")
        yield Container(DataTableBook(id="series-books-table"), id="series-books-container")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted. Populates the table."""
        try:
            table = self.query_one("#series-books-table", DataTableBook)
            table.update_table(self.books)
            self.logger.info(f"DataTableBook populated with {len(self.books)} books for series '{self.series_name}'.")
        except Exception as e:
            self.logger.error(f"Error populating DataTableBook in SeriesBooksScreen: {e}", exc_info=True)
            self.notify(f"Error loading books for series: {e}", severity="error", title="Load Error")


    def action_back(self) -> None:
        """Handles the 'back' action: pops the current screen."""
        self.app.pop_screen()
        self.logger.info("Popped SeriesBooksScreen.")

# Optional: action_open_book could be added here later if needed.
# from filesystem import FileSystemHandler
# from formvalidators import FormValidators
# from pathlib import Path
#
#    def action_open_book(self) -> None:
#        """Handles the 'open_book' action: opens the selected book file."""
#        try:
#            table = self.query_one("#series-books-table", DataTableBook)
#            book_uuid = table.current_uuid
#            if not book_uuid:
#                self.logger.warning("Attempt to open book without selection from SeriesBooksScreen.")
#                self.notify("No book selected.", severity="warning", title="Selection Missing")
#                return
#
#            book = self.library_manager.books.get_book(book_uuid)
#            if not book:
#                self.logger.error(f"Book with UUID {book_uuid} not found for opening from SeriesBooksScreen.")
#                self.notify(f"Book not found.", severity="error", title="Error")
#                return
#
#            is_valid, fs_name_or_error = FormValidators.validate_author_name(book.author)
#            if not is_valid:
#                self.notify(f"Invalid author name for path: {fs_name_or_error}", severity="error", title="Path Error")
#                return
#
#            book_path_str = self.library_manager.books.get_book_path(book)
#            if not Path(book_path_str).exists():
#                self.notify(f"File not found: {book_path_str}", severity="error", title="File Error")
#                return
#            FileSystemHandler.open_file_with_default_app(book_path_str)
#
#        except ValueError as e:
#            self.logger.error(f"Error preparing to open book from SeriesBooksScreen: {e}", exc_info=True)
#            self.notify(f"Error: {str(e)}", severity="error", title="Open Error")
#        except RuntimeError as e:
#            self.logger.error(f"Error opening book file from SeriesBooksScreen: {e}", exc_info=True)
#            self.notify(f"Could not open file: {str(e)}", severity="error", title="Open Error")
#        except Exception as e:
#            self.logger.error("Unexpected error during open book action from SeriesBooksScreen.", exc_info=e)
#            self.notify(f"An unexpected error occurred: {str(e)}", severity="error", title="Error")

# Ensure BINDINGS would include ("ctrl+o", "open_book", "Open Book") if action_open_book is enabled.
