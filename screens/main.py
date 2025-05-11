from pathlib import Path
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container
from textual.widgets import Header, Footer


from tools.logger import AppLogger
from configmanager import ConfigManager
from formvalidators import FormValidators
from filesystem import FileSystemHandler
from messages import BookAdded
from tag_formatter import TagFormatter
from widgets.datatablebook import DataTableBook
from models import LibraryManager
from screens.add import AddScreen
from screens.edit import EditScreen
from screens.settings import Settings
from screens.inputscreen import InputScreen


class MainScreen(Screen):
    BINDINGS = [
        ("ctrl+f", "search", "Cerca"),
        ("f5", "reset_search", "Reset ricerca"),
        ("e", "edit_book", "Modifica"),
        ("ctrl+a", "add_book", "Aggiungi"),
        ("ctrl+r", "reverse_sort", "Ordine"),
        ("ctrl+o", "open_book", "Apri"),
        ("ctrl+s", "settings", "Settings")
    ]

    def __init__(self, config_manager: ConfigManager, library_manager: LibraryManager):
        super().__init__()
        self.config_manager = config_manager
        self.library_manager = library_manager
        self.main_upload_dir = config_manager.paths["upload_dir_path"]
        self.logger = AppLogger.get_logger()

        # Inizializza il formattatore di tag
        # tags_data = library_manager.tags.get_all_tags()
        # self.tag_formatter = TagFormatter(tags_data)

        self.sort_reverse = False
        self.sort_field = "added"
        self.theme = "nord"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTableBook(id="books-table"),
            id="main-container")
        yield Footer()

    def on_mount(self):
        self.update_table()

    def update_table(self):
        books = self.library_manager.books.sort_books('added')

        # Prepara i tag formattati (senza icone)
        formatted_tags = []
        for book in books:
            # Check if book.tags exists, is a list, and is not empty
            if book.tags and isinstance(book.tags, list):
                 # Join the tag strings directly
                 formatted_tags.append(", ".join(str(tag) for tag in book.tags if tag)) # Ensure tags are strings and not empty
            else:
                 formatted_tags.append("") # Append an empty string if the book has no tags

        table = self.query_one("#books-table", DataTableBook)
        table.update_table(books, formatted_tags)

    def action_edit_book(self):
        table = self.query_one("#books-table", DataTableBook)

        book_uuid = table.current_uuid

        b = self.library_manager.books.get_book(book_uuid)

        if b:
            self.app.push_screen(EditScreen(self.library_manager.books, b))

    def action_add_book(self):
        self.app.push_screen(AddScreen(self.library_manager.books, self.main_upload_dir))

    def action_settings(self):
        self.app.push_screen(Settings(self.config_manager))

    def action_open_book(self):
        try:
            table = self.query_one("#books-table", DataTableBook)
            book_uuid = table.current_uuid
            book = self.library_manager.books.get_book(book_uuid)

            if not book:
                self.logger.warning("Tentativo di apertura libro senza selezione")
                self.notify("Nessun libro selezionato", severity="error")
                return

            # Verifica validità nome autore
            is_valid, fs_name = FormValidators.validate_author_name(book.author)
            if not is_valid:
                self.notify(f"Nome autore non valido: {fs_name}", severity="error")
                return

            # Ottieni percorso completo del libro
            book_path = self.library_manager.books.get_book_path(book)

            # Verifica esistenza file
            if not Path(book_path).exists():
                self.notify(f"File non trovato: {book_path}", severity="error")
                return

            # Apri il libro
            FileSystemHandler.open_file_with_default_app(book_path)

        except Exception as e:
            self.logger.error("Errore durante l'apertura di un libro", exc_info=e)
            self.notify(f"Errore durante l'apertura: {str(e)}", severity="error")


    def action_reverse_sort(self):
        table = self.query_one("#books-table", DataTableBook)

        column_mapping = {
            0: "added",
            1: "author",
            2: "title",
            3: "read",
            4: "tags"
        }

        # Ottieni la colonna corrente del cursore
        current_col = table.current_column
        
        # Se il cursore è su una colonna valida, usa quella per l'ordinamento
        if current_col is not None and current_col in column_mapping:
            self.sort_field = column_mapping[current_col]

        # Inverti l'ordine
        self.sort_reverse = not self.sort_reverse

        # Ordina e aggiorna la tabella
        sorted_books = self.library_manager.books.sort_books(self.sort_field, self.sort_reverse)
        table.update_table(sorted_books)

    def on_book_added(self, event: BookAdded) -> None:
        """Aggiorna la tabella quando viene aggiunto un nuovo libro"""
        self.update_table()
        self.notify("Libro aggiunto con successo!", title="Successo")

    def action_search(self) -> None:
        """Apre una input box per la ricerca"""
        def handle_search(query: str) -> None:
            if query:
                # Esegui la ricerca usando il nuovo metodo
                books = self.library_manager.books.search_books_by_text(query)
                
                # Formatta i tag
                formatted_tags = []
                for book in books:
                    formatted = []
                    for tag_name in book.tags:
                        tag_info = next(
                            (t for t in self.library_manager.tags.get_all_tags().values() 
                            if t['name'] == tag_name),
                            None
                        )
                        if tag_info:
                            formatted.append(f"{tag_info['icon']} {tag_name}")
                        else:
                            formatted.append(tag_name)
                    formatted_tags.append(", ".join(formatted))

                # Aggiorna la tabella
                table = self.query_one("#books-table", DataTableBook)
                table.update_table(books, formatted_tags)

        self.app.push_screen(
            InputScreen(
                title="Cerca libro",
                placeholder="Inserisci titolo o autore...",
                callback=handle_search
            )
        )

    def action_reset_search(self) -> None:
        """Resetta la ricerca e mostra tutti i libri"""
        self.update_table()