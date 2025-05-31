from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll, Horizontal
from textual.screen import Screen
from textual.widgets import Input, Button, Header, Footer, Label

from configmanager import ConfigManager

class SettingsScreen(Screen):
    BINDINGS = [
        ("escape", "back", "Torna indietro"),
    ]

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self._configpaths = config_manager.paths

    def compose(self) -> ComposeResult:
        yield Header()

        with VerticalScroll(classes="form-screen-container", id="settings-main-content"):
            yield Label("Impostazioni Percorsi", classes="title", id="settings-title")

            # Path for TinyDB
            with Horizontal(classes="form-row"):
                yield Label("Database:", classes="form-label")
                yield Input(
                    value=self._configpaths.get('tinydb_file', ''),
                    id="tinydb_file",
                    placeholder="Es: /dati/database.json",
                    classes="form-input"
                )

            # Path for Library
            with Horizontal(classes="form-row"):
                yield Label("Libreria:", classes="form-label")
                yield Input(
                    value=self._configpaths.get('library_path', ''),
                    id="library-path",
                    placeholder="Es: /immagini/libreria",
                    classes="form-input"
                )

            # Path for Upload Directory
            with Horizontal(classes="form-row"):
                yield Label("Upload:", classes="form-label")
                yield Input(
                    value=self._configpaths.get('upload_dir_path', ''),
                    id="upload_dir_path",
                    placeholder="Es: /upload/nuove_foto",
                    classes="form-input"
                )

            # Path for ExifTool
            with Horizontal(classes="form-row"):
                yield Label("ExifTool:", classes="form-label")
                yield Input(
                    value=self._configpaths.get('exiftool_path', ''),
                    id="exiftool-path",
                    placeholder="Es: /usr/bin/exiftool",
                    classes="form-input"
                )

            # Path for Log Directory
            with Horizontal(classes="form-row"):
                yield Label("Log:", classes="form-label")
                yield Input(
                    value=self._configpaths.get('log_dir', ''),
                    id="log_dir",
                    placeholder="Es: /var/log/mia_app",
                    classes="form-input"
                )

            # Button Bar
            with Horizontal(classes="button-bar"):
                yield Button("Salva", id="save-button", variant="primary", classes="button-primary")
                yield Button("Annulla", id="cancel-button")

        yield Footer()

    @on(Button.Pressed, "#save-button")
    def handle_save(self, event: Button.Pressed):
        tinydb_file = self.query_one("#tinydb_file", Input).value
        library_path = self.query_one("#library-path", Input).value
        upload_dir_path = self.query_one("#upload_dir_path", Input).value
        exiftool_path = self.query_one("#exiftool-path", Input).value
        log_dir = self.query_one("#log_dir", Input).value

        self.config_manager.update_paths({
            'tinydb_file': tinydb_file,
            'library_path': library_path,
            'upload_dir_path': upload_dir_path,
            'exiftool_path': exiftool_path,
            'log_dir': log_dir
        })

        self.notify("Percorsi aggiornati con successo!")
        self.dismiss()

    @on(Button.Pressed, "#cancel-button")
    def handle_cancel(self, event: Button.Pressed):
        self.dismiss()

    def action_back(self):
        """Torna alla schermata principale senza salvare"""
        self.dismiss()
