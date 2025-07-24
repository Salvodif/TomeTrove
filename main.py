from textual.app import App
from textual.message import Message

from messages import BookAdded
from configmanager import ConfigManager
from models import LibraryManager
from screens.main import MainScreen
from tools.logger import AppLogger

class TomeTrove(App):
    CSS_PATH = "styles.css"
    
    def __init__(self, config_manager: ConfigManager, library_manager: LibraryManager):
        super().__init__()
        self.config_manager = config_manager
        self.library_manager = library_manager
        self.logger = AppLogger(config_manager).get_logger()
        self.logger.info("Applicazione avviata")

    def on_mount(self):
        self.push_screen(MainScreen(self.config_manager, self.library_manager))

    def on_message(self, message: Message) -> None:
        """Inoltra i messaggi alle schermate attive"""
        if isinstance(message, BookAdded):
            self.logger.info(f"Nuovo libro aggiunto: {message.book.title}")
            for screen in self.screen_stack:
                if hasattr(screen, "on_book_added"):
                    screen.on_book_added(message)

    def on_exception(self, exception: Exception) -> None:
        """Gestisce le eccezioni non catturate"""
        self.logger.error(f"Eccezione non gestita: {type(exception).__name__}", exc_info=exception)
        super().on_exception(exception)

import json
import shutil

def run_app():
    try:
        config_manager = ConfigManager("config.json")
    except RuntimeError:
        shutil.copy("config.json.template", "config.json")
        config_manager = ConfigManager("config.json")

    library_manager = LibraryManager(
        config_manager.paths['library_path'],
        config_manager.paths['tinydb_file']
    )

    # Aggiungi logging per i percorsi
    logger = AppLogger(config_manager).get_logger()
    logger.info(f"Percorso della libreria: {config_manager.paths['library_path']}")
    logger.info(f"Percorso del file TinyDB: {config_manager.paths['tinydb_file']}")

    app = TomeTrove(config_manager, library_manager)
    app.run()

if __name__ == "__main__":
    run_app()