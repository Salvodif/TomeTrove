from typing import List
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Container
from textual import on
from models import LibraryManager # To access BookManager
from tools.logger import AppLogger # Assuming AppLogger is the standard logger

# Import SeriesBooksScreen from .seriesbooklist
from .seriesbooklist import SeriesBooksScreen

class SeriesListScreen(Screen):
    """A screen to display a list of all book series."""

    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, library_manager: LibraryManager):
        super().__init__()
        self.library_manager = library_manager
        self.logger = AppLogger.get_logger()
        self.series_names: List[str] = []
        self.logger.info("SeriesListScreen initialized.")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Book Series", classes="title")
        yield Container(DataTable(id="series-list-table", cursor_type="row"), id="series-list-container")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted. Fetches and displays series names."""
        self.logger.debug("SeriesListScreen: on_mount called.")

        try:
            self.series_names = self.library_manager.books.get_all_series_names()
            table = self.query_one("#series-list-table", DataTable)
            table.add_column("Series Name", key="series_name")

            if self.series_names:
                for name in self.series_names:
                    table.add_row(name, key=name) # Use series name as key
                self.logger.info(f"Displayed {len(self.series_names)} series names.")
            else:
                self.logger.info("No series found in the library.")
                self.notify("No series found in the library.")
                # Optional: Display a message in the table or container.
                # For example, by adding a row with a message or updating a Label.
        except Exception as e:
            self.logger.error(f"Error mounting SeriesListScreen: {e}", exc_info=True)
            self.notify(f"Error loading series list: {e}", severity="error", title="Load Error")


    @on(DataTable.RowSelected, "#series-list-table")
    def on_series_selected(self, event: DataTable.RowSelected) -> None:
        """Handles the selection of a series from the table."""
        try:
            # event.row_key.value should give the series name because we set key=name in add_row
            selected_series_name = event.row_key.value 
            if selected_series_name:
                self.logger.info(f"Series selected: {selected_series_name}")
                books_in_series = self.library_manager.books.get_books_by_series(selected_series_name)
                if books_in_series:
                    self.logger.info(f"Found {len(books_in_series)} books for series '{selected_series_name}'. Pushing SeriesBooksScreen.")
                    self.app.push_screen(SeriesBooksScreen(self.library_manager, selected_series_name, books_in_series))
                else:
                    self.logger.info(f"No books found for series '{selected_series_name}', though series name exists. Not navigating.")
                    self.notify(f"No books found in series '{selected_series_name}'.") # User feedback
            else:
                self.logger.warning("Series selection event triggered with no selected_series_name.")
        except Exception as e:
            self.logger.error(f"Error handling series selection: {e}", exc_info=True)
            self.notify(f"Error processing series selection: {e}", severity="error", title="Selection Error")


    def action_back(self) -> None:
        """Handles the 'back' action: pops the current screen."""
        self.app.pop_screen()
        self.logger.info("Popped SeriesListScreen.")
