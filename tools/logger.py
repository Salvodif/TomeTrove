import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from configmanager import ConfigManager

class AppLogger:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.logger = logging.getLogger("TomeTrove")
        self.start_time = datetime.now()  # Memorizza il momento dell'avvio
        self.setup_logging()

    def setup_logging(self) -> None:
        """Configura il sistema di logging con un nuovo file per ogni avvio"""
        log_dir = Path(self.config_manager.paths.get('log_dir', 'logs'))
        log_dir.mkdir(exist_ok=True)
        
        # Crea un nome file con timestamp preciso (data e ora)
        log_file = log_dir / f"bookmanager_{self.start_time.strftime('%Y%m%d_%H%M%S')}.log"
        
        # Rimuovi tutti gli handler esistenti per evitare duplicati
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()
        
        # Configurazione con RotatingFileHandler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        
        # Logga l'avvio dell'applicazione
        self.logger.info(f"Avvio applicazione - TomeTrove v1.2 - {self.start_time}")

    @staticmethod
    def get_logger(name: Optional[str] = None) -> logging.Logger:
        """Restituisce un logger configurato"""
        return logging.getLogger(name or "TomeTrove")

    def log_exception(self, message: str, exc_info: Exception) -> None:
        """Registra un'eccezione con messaggio personalizzato"""
        self.logger.error(message, exc_info=exc_info)