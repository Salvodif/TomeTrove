from pathlib import Path
import tinydb
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import logging

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
    read: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'Book':
        logger = logging.getLogger(__name__)
        added_str = data['added']
        added = None
        try:
            # Attempt to parse ISO 8601 format directly
            added = datetime.fromisoformat(added_str)
            if added.tzinfo is None:
                added = added.replace(tzinfo=datetime.now().astimezone().tzinfo)
        except ValueError:
            # Fallback to other formats if ISO parsing fails
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", 
                        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
                try:
                    # Strip sub-second precision if not supported by format
                    added_str_to_parse = added_str
                    if "%f" not in fmt and "." in added_str_to_parse:
                        added_str_to_parse = added_str_to_parse.split('.')[0]
                    
                    added = datetime.strptime(added_str_to_parse, fmt)
                    if added.tzinfo is None: # Make naive datetime aware
                        added = added.replace(tzinfo=datetime.now().astimezone().tzinfo)
                    break 
                except ValueError:
                    continue
            if added is None: # If all parsing attempts fail
                logger.error(f"Error parsing 'added' date '{added_str}'. Using current UTC time.")
                added = datetime.now(timezone.utc)


        read_value = None
        read_data = data.get('read')
        if read_data and isinstance(read_data, str) and read_data.strip():
            read_str = str(read_data)
            try:
                read_value = datetime.fromisoformat(read_str)
                if read_value.tzinfo is None:
                    read_value = read_value.replace(tzinfo=datetime.now().astimezone().tzinfo)
            except ValueError:
                try:
                    read_value = datetime.strptime(read_str, "%Y-%m-%d %H:%M")
                    if read_value.tzinfo is None: # Make naive datetime aware
                        read_value = read_value.replace(tzinfo=datetime.now().astimezone().tzinfo)
                except ValueError as e:
                    logger.warning(f"Error parsing 'read' date '{read_str}': {e}. Setting to None.")
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
        # Ensure 'added' is always a datetime object before calling isoformat
        if not isinstance(self.added, datetime):
            # This case should ideally not happen if from_dict is correct
            # and added is always initialized properly.
            # For robustness, convert to datetime if it's a string, or handle error
            logger = logging.getLogger(__name__)
            logger.error(f"Book.added is not a datetime object: {self.added}. Attempting conversion or defaulting.")
            # Attempt to parse if string, otherwise, this indicates a deeper issue
            if isinstance(self.added, str):
                try:
                    self.added = datetime.fromisoformat(self.added)
                    if self.added.tzinfo is None:
                         self.added = self.added.replace(tzinfo=datetime.now().astimezone().tzinfo)
                except ValueError:
                    self.added = datetime.now(timezone.utc) # Fallback
            else: # Not a string, not a datetime - critical issue
                 self.added = datetime.now(timezone.utc)


        added_iso = self.added.isoformat()
        read_iso = None
        if self.read is not None:
            if isinstance(self.read, datetime):
                read_iso = self.read.isoformat()
            else:
                # This case implies self.read was not converted to datetime correctly
                # or was set to a non-datetime, non-None value.
                logger = logging.getLogger(__name__)
                logger.warning(f"Book.read is not a datetime object: {self.read}. Storing as None.")
                read_iso = None # Or handle as an error case

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
        """Formats the date for display, excluding microseconds."""
        # Ensure self.added is a datetime object before formatting
        if isinstance(self.added, datetime):
            return self.added.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # This case should ideally not happen. Log an error or return a default.
            logger = logging.getLogger(__name__)
            logger.error(f"Book.added is not a datetime object: {self.added} in formatted_date. Returning empty string.")
            return "" # Or raise an error, or return a sensible default

    @classmethod
    def parse_ui_date(cls, date_str: str) -> datetime:
        """Converts a date string from UI format (Y-m-d H:M) to a timezone-aware datetime object."""
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=datetime.now().astimezone().tzinfo)

######################################################################################################
#
#                   TagsManager
#
######################################################################################################
class TagsManager:
    """Manages tags in the TinyDB database."""
    def __init__(self, library_root_path: str, db_file_name: str):
        self.db = tinydb.TinyDB(str(Path(library_root_path) / db_file_name))
        self.tags_table = self.db.table('tags')
        self._cache = None
        self._dirty = True

    def _ensure_cache(self):
        """Loads the cache if it's outdated or doesn't exist."""
        if self._dirty or self._cache is None:
            self._cache = {tag.doc_id: tag for tag in self.tags_table.all()}
            self._dirty = False

    def get_all_tags(self) -> Dict[int, Dict[str, Any]]:
        """Gets all tags from the cache."""
        self._ensure_cache()
        return self._cache.copy()

    def get_all_tag_names(self) -> List[str]:
        """Gets a list of unique and sorted tag names."""
        self._ensure_cache()
        if not self._cache:
            return []
        return sorted(list(set(tag_data['name'] for tag_data in self._cache.values() if 'name' in tag_data)))

    def get_tag_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Gets a specific tag by name."""
        self._ensure_cache()
        for tag in self._cache.values():
            if tag['name'] == name:
                return tag
        return None

    def add_tag(self, name: str, icon: str) -> int:
        """Adds a new tag."""
        tag_id = self.tags_table.insert({'name': name, 'icon': icon})
        self._dirty = True
        return tag_id

    def update_tag(self, tag_id: int, new_data: Dict[str, Any]):
        """Updates an existing tag."""
        self.tags_table.update(new_data, doc_ids=[tag_id])
        self._dirty = True

    def remove_tag(self, tag_id: int):
        """Removes a tag."""
        self.tags_table.remove(doc_ids=[tag_id])
        self._dirty = True

    def close(self):
        """Closes the database connection and clears the cache."""
        self.db.close()
        self._cache = None
        self._dirty = True

#####################################################################################################
#                                       BookManager
#                    Manages interaction with the TinyDB database for books.
#####################################################################################################
class BookManager:
    """Manages books in the TinyDB database."""
    def __init__(self, library_root_path: str, db_file_name: str, tags_manager: Optional[TagsManager] = None): # Made Optional explicit
        self.db = tinydb.TinyDB(str(Path(library_root_path) / db_file_name))
        self.books_table = self.db.table('books')
        self._cache = None
        self._dirty = True
        self._library_root = library_root_path
        self.tags_manager = tags_manager

    @property
    def library_root(self) -> str:
        return self._library_root

    def _ensure_cache(self):
        """Loads the cache if it's outdated or doesn't exist."""
        if self._dirty or self._cache is None:
            self._cache = {book['uuid']: Book.from_dict(book) 
                          for book in self.books_table.all()}
            self._dirty = False

    def add_book(self, book: Book):
        # Validate author name
        is_valid, fs_name = FormValidators.validate_author_name(book.author)
        if not is_valid:
            raise ValueError(f"Invalid author name: {fs_name}")

        """Adds a book to the database and invalidates the cache."""
        self.books_table.insert(book.to_dict())
        self._dirty = True

    def get_book_path(self, book: Book) -> str:
        """Returns the full path of the book file."""
        if not book.filename:
            raise ValueError("Book has no associated filename")

        author_dir = FormValidators.author_to_fsname(book.author)
        return str(Path(self.library_root) / author_dir / book.filename)

    def ensure_directory(self, author: str) -> str:
        """Creates the author's directory if it doesn't exist."""
        author_dir = FormValidators.author_to_fsname(author)
        author_path = Path(self.library_root) / author_dir
        return FileSystemHandler.ensure_directory_exists(str(author_path))


################### UPDATE BOOK ###########################
    def update_book(self, uuid: str, new_data: Dict):
        """Updates an existing book and invalidates the cache."""
        q = tinydb.Query()
        
        # Process 'added' field
        if 'added' in new_data:
            if isinstance(new_data['added'], datetime):
                new_data['added'] = new_data['added'].isoformat()
            elif isinstance(new_data['added'], str):
                # Attempt to parse if it's a string, assuming ISO 8601 or fallback
                try:
                    dt = datetime.fromisoformat(new_data['added'])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                    new_data['added'] = dt.isoformat()
                except ValueError:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Invalid date string for 'added' in update_book: {new_data['added']}. Keeping original or consider error handling.")
                    # Decide on error handling: raise error, log and skip, or try other parsing
            # If it's neither datetime nor string, it might be an issue depending on input types

        # Process 'read' field
        if 'read' in new_data:
            if isinstance(new_data['read'], datetime):
                new_data['read'] = new_data['read'].isoformat()
            elif isinstance(new_data['read'], str):
                if not new_data['read'].strip(): # Empty string
                    new_data['read'] = None
                else:
                    # Attempt to parse if it's a non-empty string
                    try:
                        # Try ISO format first
                        dt = datetime.fromisoformat(new_data['read'])
                        if dt.tzinfo is None:
                             dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                        new_data['read'] = dt.isoformat()
                    except ValueError:
                        # Fallback to UI format if ISO fails
                        try:
                            dt = Book.parse_ui_date(new_data['read']) # Uses the class method
                            new_data['read'] = dt.isoformat()
                        except ValueError:
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Invalid date string for 'read' in update_book: {new_data['read']}. Setting to None.")
                            new_data['read'] = None
            elif new_data['read'] is None:
                pass # Already None, which is the desired state for storage
            else: # Not datetime, not string, not None
                logger = logging.getLogger(__name__)
                logger.warning(f"Unexpected type for 'read' in update_book: {type(new_data['read'])}. Setting to None.")
                new_data['read'] = None

        self.books_table.update(new_data, q.uuid == uuid)
        self._dirty = True
#################################################################

################### REMOVE BOOK ###########################
    def remove_book(self, uuid: str):
        """Removes a book from the database and invalidates the cache."""
        BookQuery = tinydb.Query()
        self.books_table.remove(BookQuery.uuid == uuid)
        self._dirty = True

    def get_book(self, uuid: str) -> Optional[Book]:
        """Gets a specific book by UUID from the cache."""
        self._ensure_cache()
        return self._cache.get(uuid)

    def get_all_books(self) -> List[Book]:
        """Gets all books from the cache."""
        self._ensure_cache()
        return list(self._cache.values())
    
    def get_all_author_names(self) -> List[str]:
        """Gets a list of unique and sorted author names."""
        self._ensure_cache()
        if not self._cache:
            return []
        return sorted(list(set(book.author for book in self._cache.values() if book.author)))

    def get_all_series_names(self) -> List[str]:
        """Gets a list of unique and sorted series names."""
        self._ensure_cache()
        if not self._cache:
            return []
        
        series_names = set()
        for book in self._cache.values():
            if book.series and book.series.strip():
                series_names.add(book.series)
        return sorted(list(series_names))

    def get_books_by_series(self, series_name: str) -> List[Book]:
        """Gets a list of books belonging to a specific series."""
        self._ensure_cache()
        if not self._cache:
            return []
        
        return [book for book in self._cache.values() if book.series == series_name]

    def search_books_by_text(self, text: str) -> List[Book]:
        """Searches books by text in title or author."""
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
        """Sorts books by a given field."""
        books = self.get_all_books()

        if not books:
            return []

        # If reverse is None, use a default value based on the field
        if reverse is None:
            reverse = False if field != 'added' else True

        if field == 'added':
            books.sort(key=lambda x: x.added, reverse=reverse)
        elif hasattr(books[0], field):
            # Handle cases where field might be None for some books during sort
            books.sort(key=lambda x: str(getattr(x, field) or '').lower() if isinstance(getattr(x, field), str) else getattr(x, field), reverse=reverse)


        return books

    def close(self):
        """Closes the database connection and clears the cache."""
        self.db.close()
        self._cache = None
        self._dirty = True

######################################################################
#
#       LibraryManager
#
######################################################################
class LibraryManager:
    """Container for BookManager and TagsManager."""

    def __init__(self, library_root_path: str, db_file_name: str):
        self._library_root_path = library_root_path
        self._db_file_name = db_file_name
        self.__book_manager: Optional[BookManager] = None
        self.__tags_manager: Optional[TagsManager] = None
    
    @property
    def books(self) -> BookManager:
        """Access to the BookManager instance."""
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
        """Access to the TagsManager instance."""
        if self.__tags_manager is None:
            self.__tags_manager = TagsManager(self._library_root_path, self._db_file_name)
        return self.__tags_manager
    
    def close(self):
        """Closes all manager connections."""
        if self.__book_manager:
            self.__book_manager.close()
        if self.__tags_manager:
            self.__tags_manager.close()