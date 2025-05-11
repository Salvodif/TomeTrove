from pathlib import Path
import tinydb
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from formvalidators import FormValidators
from filesystem import FileSystemHandler

@dataclass
class Book:
    uuid: str
    author: str
    title: str
    added: datetime
    tags: List[str] = field(default_factory=list)
    filename: str = ""
    other_formats: List[str] = field(default_factory=list)
    series: Optional[str] = None
    num_series: Optional[float] = None
    description: Optional[str] = None
    read: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'Book':
        # Parsing del campo 'added'
        added_str = data['added']
        try:
            if '+' in added_str or added_str.endswith('Z'):
                added = datetime.fromisoformat(added_str)
            else:
                try:
                    added = datetime.strptime(added_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    added = datetime.strptime(added_str.split('.')[0], "%Y-%m-%dT%H:%M")
                added = added.replace(tzinfo=datetime.now().astimezone().tzinfo)
        except ValueError as e:
            added = datetime.now().astimezone()
            print(f"Errore nel parsing della data 'added' '{added_str}': {e}. Usata data corrente.")

        # Parsing del campo 'read'
        read_value = None
        read_data = data.get('read')
        if read_data and isinstance(read_data, str) and read_data.strip():  # Usa .get() per sicurezza
            read_str = str(read_data) # Ensure it's a string
            try:
                if 'T' in read_str:  # Formato ISO
                    read_dt = datetime.fromisoformat(read_str)
                    if read_dt.tzinfo is None:
                        read_dt = read_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                    read_value = read_dt.strftime("%Y-%m-%d %H:%M")
                else:  # Formato UI diretto (YYYY-MM-DD HH:MM)
                    read_value = read_str  # Assume già nel formato corretto
            except ValueError as e:
                print(f"Errore nel parsing della data 'read' '{read_str}': {e}")
                read_value = None

        return cls(
            uuid=data['uuid'],
            author=data['author'],
            title=data['title'],
            added=added,
            tags=data.get('tags', []),
            filename=data.get('filename', ''),
            other_formats=data.get('other_formats', []),
            series=data.get('series'),
            num_series=data.get('num_series'),
            description=data.get('description'),
            read=read_value
        )

    def to_dict(self) -> Dict:
        # Formatta added mantenendo microsecondi e timezone
        added_iso = self.added.isoformat()

        # Formatta read nello stesso formato se presente
        read_iso = None
        if self.read:
            try:
                # Converti dalla stringa UI a datetime
                read_dt = datetime.strptime(self.read, "%Y-%m-%d %H:%M")
                read_dt = read_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                read_iso = read_dt.isoformat()
            except ValueError:
                read_iso = None # Or log error, or re-raise

        return {
            'uuid': self.uuid,
            'author': self.author,
            'title': self.title,
            'added': added_iso,
            'tags': self.tags,
            'filename': self.filename,
            'other_formats': self.other_formats,
            'series': self.series,
            'num_series': self.num_series,
            'description': self.description,
            'read': read_iso
        }

    @property
    def formatted_date(self) -> str:
        """Formatta la data senza microsecondi per la visualizzazione"""
        return self.added.strftime("%Y-%m-%d %H:%M:%S")  # Esclude microsecondi

    @classmethod
    def parse_ui_date(cls, date_str: str) -> datetime:
        """Converte dal formato dell'interfaccia (Y-m-d H:M) a datetime con timezone"""
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(
            tzinfo=datetime.now().astimezone().tzinfo)

######################################################################################################
#
#                   TagsManager
#
######################################################################################################
class TagsManager:
    def __init__(self, library_root_path: str, db_file_name: str):
        self.db = tinydb.TinyDB(f"{library_root_path}/{db_file_name}")
        self.tags_table = self.db.table('tags')
        self._cache = None
        self._dirty = True

    def _ensure_cache(self):
        """Carica la cache se è obsoleta o non esiste"""
        if self._dirty or self._cache is None:
            self._cache = {tag.doc_id: tag for tag in self.tags_table.all()}
            self._dirty = False

    def get_all_tags(self) -> Dict[int, Dict[str, Any]]:
        """Ottiene tutti i tag dalla cache"""
        self._ensure_cache()
        return self._cache.copy()

    def get_all_tag_names(self) -> List[str]:
        """Ottiene una lista di nomi di tag unici e ordinati."""
        self._ensure_cache()
        if not self._cache:
            return []
        return sorted(list(set(tag_data['name'] for tag_data in self._cache.values() if 'name' in tag_data)))

    def get_tag_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Ottiene un tag specifico per nome"""
        self._ensure_cache()
        for tag in self._cache.values():
            if tag['name'] == name:
                return tag
        return None

    def add_tag(self, name: str, icon: str) -> int:
        """Aggiunge un nuovo tag"""
        tag_id = self.tags_table.insert({'name': name, 'icon': icon})
        self._dirty = True
        return tag_id

    def update_tag(self, tag_id: int, new_data: Dict[str, Any]):
        """Aggiorna un tag esistente"""
        self.tags_table.update(new_data, doc_ids=[tag_id])
        self._dirty = True

    def remove_tag(self, tag_id: int):
        """Rimuove un tag"""
        self.tags_table.remove(doc_ids=[tag_id])
        self._dirty = True

    def close(self):
        """Chiude la connessione al database"""
        self.db.close()
        self._cache = None
        self._dirty = True

#####################################################################################################
#                                       BookManager
#                    Gestisce l'interazione con il database TinyDB per i libri
#####################################################################################################
class BookManager:
    def __init__(self, library_root_path: str, db_file_name: str, tags_manager: Optional[TagsManager] = None): # Made Optional explicit
        self.db = tinydb.TinyDB(f"{library_root_path}/{db_file_name}")
        self.books_table = self.db.table('books')
        self._cache = None
        self._dirty = True
        self._library_root = library_root_path
        self.tags_manager = tags_manager

    @property
    def library_root(self) -> str:
        return self._library_root

    def _ensure_cache(self):
        """Carica la cache se è obsoleta o non esiste"""
        if self._dirty or self._cache is None:
            self._cache = {book['uuid']: Book.from_dict(book) 
                          for book in self.books_table.all()}
            self._dirty = False

    def add_book(self, book: Book):
        # Validazione nome autore
        is_valid, fs_name = FormValidators.validate_author_name(book.author)
        if not is_valid:
            raise ValueError(f"Nome autore non valido: {fs_name}")

        """Aggiunge un libro al database e invalida la cache"""
        self.books_table.insert(book.to_dict())
        self._dirty = True

    def get_book_path(self, book: Book) -> str:
        """Restituisce il percorso completo del libro"""
        if not book.filename:
            raise ValueError("Il libro non ha un filename associato")

        author_dir = FormValidators.author_to_fsname(book.author)
        return str(Path(self.library_root) / author_dir / book.filename)

    def ensure_directory(self, author: str) -> str:
        """Crea la directory dell'autore se non esiste"""
        author_dir = FormValidators.author_to_fsname(author)
        author_path = Path(self.library_root) / author_dir
        return FileSystemHandler.ensure_directory_exists(str(author_path))


################### UPDATE BOOK ###########################
    def update_book(self, uuid: str, new_data: Dict):
        """Aggiorna un libro esistente e invalida la cache"""
        q = tinydb.Query()
        if 'added' in new_data and isinstance(new_data['added'], str):
            new_data['added'] = datetime.strptime(
                new_data['added'], "%Y-%m-%dT%H:%M:%S%z").isoformat()

        # Converti il campo read nel formato corretto se presente
        if 'read' in new_data and isinstance(new_data['read'], str) and new_data['read'].strip():
            try:
                # Converti dalla stringa UI a datetime con timezone
                read_dt = datetime.strptime(new_data['read'], "%Y-%m-%d %H:%M")
                read_dt = read_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                new_data['read'] = read_dt.isoformat()
            except ValueError:
                # Se non è nel formato UI, assumi sia già nel formato ISO
                if 'T' in new_data['read']:  # Sembra già ISO
                    try:
                        dt = datetime.fromisoformat(new_data['read'])
                        if not dt.tzinfo:
                            dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                        new_data['read'] = dt.isoformat()
                    except ValueError:
                        new_data['read'] = None # Invalid ISO
                else:
                    new_data['read'] = None # Not UI, not ISO
        elif 'read' in new_data and not new_data['read']: # Handle empty string for read
            new_data['read'] = None


        self.books_table.update(new_data, q.uuid == uuid)
        self._dirty = True
#################################################################

################### REMOVE BOOK ###########################
    def remove_book(self, uuid: str):
        """Rimuove un libro dal database e invalida la cache"""
        BookQuery = tinydb.Query()
        self.books_table.remove(BookQuery.uuid == uuid)
        self._dirty = True

    def get_book(self, uuid: str) -> Optional[Book]:
        """Ottiene un libro specifico per UUID dalla cache"""
        self._ensure_cache()
        return self._cache.get(uuid)

    def get_all_books(self) -> List[Book]:
        """Ottiene tutti i libri dalla cache"""
        self._ensure_cache()
        return list(self._cache.values())
    
    def get_all_author_names(self) -> List[str]:
        """Ottiene una lista di nomi di autori unici e ordinati."""
        self._ensure_cache()
        if not self._cache:
            return []
        return sorted(list(set(book.author for book in self._cache.values() if book.author)))

    def search_books_by_text(self, text: str) -> List[Book]:
        """Cerca libri per testo in titolo o autore"""
        if not text:
            return self.get_all_books()
            
        self._ensure_cache()
        text_lower = text.lower()
        
        return [
            book for book in self._cache.values()
            if (book.title and text_lower in book.title.lower()) or
               (book.author and text_lower in book.author.lower())
        ]

################### SORT BOOKS ###########################
    def sort_books(self, field: str, reverse: bool = None) -> List[Book]:
        books = self.get_all_books()

        if not books:
            return []

        # Se reverse è None, usa un valore predefinito in base al campo
        if reverse is None:
            reverse = False if field != 'added' else True

        if field == 'added':
            books.sort(key=lambda x: x.added, reverse=reverse)
        elif hasattr(books[0], field):
            # Handle cases where field might be None for some books during sort
            books.sort(key=lambda x: str(getattr(x, field) or '').lower() if isinstance(getattr(x, field), str) else getattr(x, field), reverse=reverse)


        return books

    def close(self):
        """Chiude la connessione al database e pulisce la cache"""
        self.db.close()
        self._cache = None
        self._dirty = True

######################################################################
#
#       LibraryManager
#
######################################################################
class LibraryManager:
    """Contenitore per BookManager e TagsManager"""

    def __init__(self, library_root_path: str, db_file_name: str):
        self._library_root_path = library_root_path
        self._db_file_name = db_file_name
        self.__book_manager: Optional[BookManager] = None # Type hint for clarity
        self.__tags_manager: Optional[TagsManager] = None # Type hint for clarity
    
    @property
    def books(self) -> BookManager:
        """Accesso al BookManager"""
        if self.__book_manager is None:
            # Ensure TagsManager is initialized first if needed by BookManager
            self.__book_manager = BookManager(
                self._library_root_path, 
                self._db_file_name, 
                tags_manager=self.tags # Pass the TagsManager instance
            )
        return self.__book_manager
    
    @property
    def tags(self) -> TagsManager:
        """Accesso al TagsManager"""
        if self.__tags_manager is None:
            self.__tags_manager = TagsManager(self._library_root_path, self._db_file_name)
        return self.__tags_manager
    
    def close(self):
        """Chiude tutte le connessioni"""
        if self.__book_manager:
            self.__book_manager.close()
        if self.__tags_manager:
            self.__tags_manager.close()