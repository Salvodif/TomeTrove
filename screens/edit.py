from datetime import datetime
from typing import Optional, Callable # Added Optional, Callable

from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Button, Label, Checkbox, Input # Added Input
from textual.markup import escape

from textual_autocomplete import AutoComplete # Changed import

from tools.logger import AppLogger
from models import BookManager, Book # Added Book for type hint
from widgets.bookform import BookForm

class EditScreen(Screen):
    BINDINGS = [("escape", "back", "Torna indietro")]

    def __init__(self,
                 bookmanager: BookManager,
                 book: Book,
                 on_save_callback: Optional[Callable[[Book], None]] = None):
        super().__init__()
        self.bookmanager = bookmanager
        self.book = book
        self.on_save_callback = on_save_callback
        self.form = BookForm(book,
                             add_new_book=False,
                             all_authors=self.bookmanager.get_all_author_names(),
                             all_tags=self.bookmanager.tags_manager.get_all_tag_names()  if self.bookmanager.tags_manager else [],
                             all_series=self.bookmanager.get_all_series_names()
                            )


        self.logger = AppLogger.get_logger()


    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="form-screen-container", id="edit-container"):
            yield Label(f"Modifica: {self.book.title}", id="edit-title-label", classes="title")
            yield self.form.form_container
            yield self.form.author_autocomplete
            yield self.form.tags_autocomplete
            yield self.form.series_autocomplete
            yield Horizontal(
                Button("Annulla", id="cancel"),
                self.form.save_button,
                classes="button-bar"
            )
        yield Footer()

    def on_mount(self) -> None:
        if self.form.title_input:
            self.form.title_input.focus()

    @on(Checkbox.Changed, "#read_status_checkbox")
    def handle_checkbox_change(self, event: Checkbox.Changed) -> None:
        self.form.handle_read_checkbox_change()

    @on(Button.Pressed, "#save")
    def save_changes(self) -> None:
        try:
            error = self.form.validate()
            if error:
                self.logger.warning(f"Validazione fallita durante modifica libro: {escape(error)}")
                self.notify(escape(error), severity="error", timeout=5)
            else:
                values = self.form.get_values()
                self.logger.debug(f"EditScreen save_changes - Values from form: {values}")
                self.logger.info(f"Modifica libro: {self.book.uuid} con valori: {values}")
                updated_book_data = self.bookmanager.update_book(self.book.uuid, values)

                # It's better if update_book returns the updated book object or data.
                # For now, we'll assume self.book is sufficiently representative,
                # or the callback primarily acts as a trigger.
                # If updated_book_data is the actual updated Book object, use that.
                # Let's assume update_book returns the updated book for correctness.
                # If not, self.book (original or partially modified) is passed.
                # For this example, let's assume BookManager.update_book returns the updated Book.
                # If it just returns a status, then self.book (original) would be passed.
                # The task description implies the callback needs a Book object.

                # Re-fetch the book to get the most up-to-date version to pass to callback
                refreshed_book = self.bookmanager.get_book(self.book.uuid)
                if refreshed_book: # Ensure book still exists
                    if self.on_save_callback:
                        self.on_save_callback(refreshed_book)
                    self.notify("Libro aggiornato con successo!", severity="information")
                    self.app.pop_screen()
                else:
                    # This case should ideally not happen if update was successful
                    self.logger.error(f"Book {self.book.uuid} not found after update.")
                    self.notify("Libro aggiornato, ma si è verificato un problema nel ricaricamento.", severity="warning")
                    self.app.pop_screen() # Still pop, or handle as error

        except Exception as e:
            self.logger.error("Errore durante la modifica di un libro", exc_info=e)
            self.notify(escape(f"Errore durante il salvataggio: {e}"), severity="error", timeout=5)

    @on(Button.Pressed, "#cancel")
    def cancel_edits(self) -> None:
        self.app.pop_screen()

    def action_back(self):
        self.app.pop_screen()

    async def _suggest_next_series_number(self, series_name: Optional[str]) -> None:
        if series_name and series_name.strip() and not self.form.num_series_input.value.strip():
            # Only suggest if num_series is currently empty.
            # This check is important for EditScreen to avoid overwriting an existing number
            # just because the series name was confirmed or re-selected.
            try:
                books_in_series = self.bookmanager.get_books_by_series(series_name.strip())
                if not books_in_series:
                    self.form.num_series_input.value = "1"
                    self.notify(f"Suggerito il numero 1 per la nuova serie '{series_name.strip()}'.")
                    return

                max_num_series = 0
                found_valid_num = False
                for book_item in books_in_series: # Renamed to book_item to avoid conflict with self.book
                    # Exclude the current book being edited from consideration for max_num_series
                    if book_item.uuid == self.book.uuid:
                        continue
                    if book_item.num_series is not None:
                        try:
                            current_num = float(book_item.num_series)
                            if current_num > max_num_series:
                                max_num_series = current_num
                            found_valid_num = True
                        except ValueError:
                            self.logger.warning(f"Libro '{book_item.title}' nella serie '{series_name.strip()}' ha num_series non valido: {book_item.num_series}")

                if found_valid_num:
                    suggested_num = int(max_num_series) + 1
                    self.form.num_series_input.value = str(suggested_num)
                    self.notify(f"Suggerito il numero {suggested_num} per la serie '{series_name.strip()}'.")
                else:
                    # If no other numbered books found (or only the current book was found and skipped), suggest 1
                    self.form.num_series_input.value = "1"
                    self.notify(f"Suggerito il numero 1 per la serie '{series_name.strip()}' (nessun altro libro numerato trovato).")

            except Exception as e:
                self.logger.error(f"Errore nel suggerire il numero di serie per '{series_name.strip()}': {e}")

    @on(AutoComplete.Selected, "#form_series_autocomplete") # Changed decorator event
    async def handle_series_completion(self, event: AutoComplete.Selected) -> None: # Changed event type
        if event.control == self.form.series_autocomplete:
            completed_series_name = event.value # Changed to get value from event
            await self._suggest_next_series_number(completed_series_name)

    @on(Input.Blurred, "#series_input_target")
    async def handle_series_input_blur(self, event: Input.Blurred) -> None:
        series_name = self.form.series_target_input.value
        all_series_names = []
        try:
            all_series_names = self.bookmanager.get_all_series_names()
        except Exception as e:
            self.logger.error(f"Failed to get series names for blur handler: {e}")

        if series_name and series_name.strip():
            stripped_series_name = series_name.strip()
            if stripped_series_name in all_series_names:
                # Only call suggestion if num_series is empty, to respect existing values.
                if not self.form.num_series_input.value.strip():
                    await self._suggest_next_series_number(stripped_series_name)
            elif not self.form.num_series_input.value.strip(): # New series and num_series is empty
                self.form.num_series_input.value = "1"
                self.notify(f"Suggerito il numero 1 per la nuova serie '{stripped_series_name}'.")