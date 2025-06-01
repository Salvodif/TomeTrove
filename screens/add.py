import shutil
import subprocess

from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4
from textual import on
from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.markup import escape
from textual.widgets import Header, Footer, Label, DirectoryTree, Button, Input # Added Input

from textual_autocomplete import AutoComplete, ItemSelected as AutoCompleteItemSelected # Updated import

from tools.logger import AppLogger
from messages import BookAdded
from models import Book, BookManager # BookManager has TagsManager
from formvalidators import FormValidators
from widgets.bookform import BookForm


class AddScreen(Screen):
    BINDINGS = [("escape", "back", "Torna indietro")]

    def __init__(self, bookmanager: BookManager, start_directory: str = "."):
        super().__init__()
        self.bookmanager = bookmanager
        self.start_directory = start_directory
        self.logger = AppLogger.get_logger() # Initialize logger early

        all_authors: List[str] = []
        all_tags: List[str] = []
        all_series: List[str] = []

        try:
            all_authors = self.bookmanager.get_all_author_names()
        except Exception as e:
            self.logger.error(f"Failed to get author names for autocomplete: {e}")
        
        if self.bookmanager.tags_manager:
            try:
                all_tags = self.bookmanager.tags_manager.get_all_tag_names()
            except Exception as e:
                self.logger.error(f"Failed to get tag names for autocomplete: {e}")
        else:
            self.logger.warning("TagsManager not available in BookManager; tag autocompletion will be empty.")

        try:
            all_series = self.bookmanager.get_all_series_names()
        except Exception as e:
            self.logger.error(f"Failed to get series names for autocomplete: {e}")

        self.form = BookForm(
            start_directory=start_directory,
            add_new_book=True,
            all_authors=all_authors,
            all_tags=all_tags,
            all_series=all_series
            )

        # The actual AutoComplete widgets are now part of BookForm's attributes
        self.author_autocomplete_widget = self.form.author_autocomplete
        self.tags_autocomplete_widget = self.form.tags_autocomplete
        self.series_autocomplete_widget = self.form.series_autocomplete

    def compose(self) -> ComposeResult:
        yield Header()
        # BookForm.compose_form() yields its main container
        yield self.form.form_container 
        
        # Yield autocomplete widgets separately as they are not part of form_container
        yield self.author_autocomplete_widget
        yield self.tags_autocomplete_widget
        yield self.series_autocomplete_widget

        yield Horizontal(
            self.form.save_button,
            classes="button-bar"
        )
        yield Footer()

    def on_mount(self):
        if self.form.file_tree:
            self.form.file_tree.focus()
        else:
            # This case should ideally not happen if show_file_browser is True
            self.logger.warning("File tree not found on mount for AddScreen, focusing title input.")
            if self.form.title_input:
                self.form.title_input.focus()

    @on(DirectoryTree.FileSelected)
    def handle_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()
        if self.form.selected_file_label:
            try:
                # Make sure event.path is a file before updating
                # DirectoryTree.FileSelected should only trigger for files with valid_extensions
                p = Path(event.path)
                if p.is_file():
                    self.form.selected_file_label.update(str(p))
                else:
                    self.notify(f"Selezione non valida: {event.path} non è un file.", severity="error")
                    self.form.selected_file_label.update("Errore nella selezione")
            except Exception as e:
                self.notify(f"Errore selezione file: {e}", severity="error")
                if self.form.selected_file_label: # Check again in case of error during update
                    self.form.selected_file_label.update("Errore nella selezione")

    @on(Button.Pressed, "#save")
    def on_button_pressed(self, event: Button.Pressed):
        error = self.form.validate()
        if error:
            self.logger.warning(f"Validazione fallita: {error}")
            self.notify(escape(error), severity="error", timeout=5)
            return

        try:
            values = self.form.get_values()
            
            # The 'filename' from get_values is a Path object to the source file (or Path(existing_filename))
            # For AddScreen, it must be a valid source file path.
            original_path = values['filename'] 
            if not original_path or not isinstance(original_path, Path) or not original_path.is_file():
                self.logger.warning("Tentativo di aggiunta libro senza un file valido selezionato.")
                self.notify(escape("Seleziona un file valido!"), severity="error", timeout=5)
                return

            fs_author = FormValidators.author_to_fsname(values['author'])
            fs_title = FormValidators.title_to_fsname(values['title'])

            new_filename = f"{fs_title} - {fs_author}{original_path.suffix}"
            author_dir = self.bookmanager.ensure_directory(values['author'])
            dest_path = Path(author_dir) / new_filename

            if dest_path.exists():
                # Basic check to prevent overwriting, could be made more sophisticated (e.g. confirm with user)
                self.notify(f"Un file con nome '{new_filename}' esiste già in '{author_dir}'. Scegli un titolo o autore diverso.", severity="error", timeout=7)
                return

            shutil.copy2(original_path, dest_path)

            if dest_path.suffix.lower() in ['.pdf', '.docx', '.epub']:
                self.update_file_metadata(dest_path, values)

            book = Book(
                uuid=str(uuid4()),
                author=values['author'],
                title=values['title'],
                added=datetime.now().astimezone(),
                tags=values['tags'],
                series=values['series'],
                num_series=values['num_series'],
                read=values['read'],
                description=values['description'],
                filename=new_filename
            )

            self.bookmanager.add_book(book)
            self.app.post_message(BookAdded(book))
            self.notify("Libro aggiunto con successo!", severity="info") # Changed from success for less aggressive color
            self.app.pop_screen()

        except ValueError as ve: # Catch specific validation errors like invalid author name
            self.logger.error(f"Errore di validazione durante l'aggiunta del libro: {ve}", exc_info=False) # No need for full stacktrace for ValueErrors often
            self.notify(escape(str(ve)), severity="error", timeout=5)
        except Exception as e:
            self.logger.error("Errore generico durante l'aggiunta di un libro", exc_info=e)
            error_message = escape(str(e)) # escape for safety
            self.notify(error_message, severity="error", timeout=5)


    def update_file_metadata(self, file_path: Path, values: dict) -> Optional[bool]:
        try:
            if hasattr(self.app, 'config_manager') and self.app.config_manager:
                 exiftool_path = self.app.config_manager.paths.get('exiftool_path', 'exiftool')
            else:
                self.logger.warning("ConfigManager non trovato, usando 'exiftool' di default.")
                exiftool_path = 'exiftool' # Default fallback

            commands = [
                exiftool_path,
                '-overwrite_original', # Important to modify the file in place
                f'-Author={values["author"]}',
                f'-Title={values["title"]}',
            ]
            if values["tags"]:
                commands.append(f'-Keywords={", ".join(values["tags"])}')

            if values['description']:
                # Exiftool description argument might need careful quoting depending on shell/content
                commands.append(f'-Description={values["description"]}')

            commands.append(str(file_path)) # File path must be last

            self.logger.debug(f"Exiftool command: {' '.join(commands)}")

            result = subprocess.run(commands, capture_output=True, text=True, check=False, cwd=str(file_path.parent))

            if result.returncode != 0:
                error_output = result.stderr.strip()
                if "image files updated" in error_output.lower() and result.returncode ==0:
                    self.logger.info(f"Exiftool updated metadata for {file_path} with warnings: {error_output}")
                    return True

                self.logger.error(f"Exiftool error for {file_path}: {error_output} (stdout: {result.stdout.strip()})")
                self.notify(escape(f"Errore Exiftool: {error_output}"), severity="error", timeout=7)
                return False

            self.logger.info(f"Exiftool successfully updated metadata for {file_path}")
            return True

        except FileNotFoundError:
            self.logger.warning(f"Exiftool non trovato a '{exiftool_path}'. Metadati non aggiornati.")
            self.notify(escape(f"Exiftool non trovato. Metadati non aggiornati."), severity="warning", timeout=5)
            return None # None indicates tool not found or similar setup issue
        except Exception as e:
            self.logger.error(f"Errore aggiornamento metadati per {file_path}: {str(e)}", exc_info=True) 
            user_message = f"Errore aggiornamento metadati per {file_path.name}. Controllare i log." 
            self.notify(user_message, severity="error", timeout=7) 
            return False

    def action_back(self):
        self.app.pop_screen()

    async def _suggest_next_series_number(self, series_name: Optional[str]) -> None:
        if series_name and series_name.strip() and not self.form.num_series_input.value.strip():
            try:
                books_in_series = self.bookmanager.get_books_by_series(series_name.strip())
                if not books_in_series:
                    self.form.num_series_input.value = "1"
                    self.notify(f"Suggerito il numero 1 per la nuova serie '{series_name.strip()}'.")
                    return

                max_num_series = 0
                found_valid_num = False
                for book in books_in_series:
                    if book.num_series is not None:
                        try:
                            current_num = float(book.num_series)
                            if current_num > max_num_series:
                                max_num_series = current_num
                            found_valid_num = True
                        except ValueError:
                            self.logger.warning(f"Libro '{book.title}' nella serie '{series_name.strip()}' ha num_series non valido: {book.num_series}")

                if found_valid_num:
                    suggested_num = int(max_num_series) + 1
                    self.form.num_series_input.value = str(suggested_num)
                    self.notify(f"Suggerito il numero {suggested_num} per la serie '{series_name.strip()}'.")
                else:
                    self.form.num_series_input.value = "1"
                    self.notify(f"Suggerito il numero 1 per la serie '{series_name.strip()}' (nessun libro numerato trovato).")

            except Exception as e:
                self.logger.error(f"Errore nel suggerire il numero di serie per '{series_name.strip()}': {e}")
                # Non notificare l'utente per errori interni, solo loggare.

    async def on_auto_complete_item_selected(self, message: AutoCompleteItemSelected) -> None:
        # Check if the message came from the series autocomplete widget
        if message.control == self.series_autocomplete_widget:
            completed_series_name = message.value # 'value' usually holds the selected item's string value
            if completed_series_name: # Ensure value is not None or empty
                await self._suggest_next_series_number(completed_series_name)

    @on(Input.Blurred, "#series_input_target") # ID of self.form.series_target_input
    async def handle_series_input_blur(self, event: Input.Blurred) -> None:
        series_name = self.form.series_target_input.value
        # Check if this series actually exists to prevent suggesting for brand new series names
        # unless the requirement is to suggest "1" for any new series name typed.
        all_series_names = []
        try:
            all_series_names = self.bookmanager.get_all_series_names()
        except Exception as e:
            self.logger.error(f"Failed to get series names for blur handler: {e}")
            # Proceeding without all_series_names means we might suggest "1" for an existing series
            # if the get_books_by_series call also fails or returns empty. This is acceptable degradation.

        if series_name and series_name.strip():
            stripped_series_name = series_name.strip()
            if stripped_series_name in all_series_names:
                await self._suggest_next_series_number(stripped_series_name)
            elif not self.form.num_series_input.value.strip(): # New series and num_series is empty
                self.form.num_series_input.value = "1"
                self.notify(f"Suggerito il numero 1 per la nuova serie '{stripped_series_name}'.")