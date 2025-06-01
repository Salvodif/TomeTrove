import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Callable

# Application classes
from screens.main import MainScreen, DescendingDateTime
from models import Book, LibraryManager, BookManager
from configmanager import ConfigManager
from textual._context import active_app # For setting active_app context
from textual.app import App # For type hint if needed, and for active_app.set
# Assuming InputScreen is needed for the mock logic
from screens.inputscreen import InputScreen

# Helper to create Book instances easily
def create_book(
    uuid: str,
    title: str,
    author: str,
    added: datetime,
    series: Optional[str] = None,
    num_series: Optional[float] = None,
    filename: Optional[str] = "default.epub",
    tags: Optional[List[str]] = None,
    read: bool = False,
) -> Book:
    book = Book(
        uuid=uuid,
        title=title,
        author=author,
        added=added,
        series=series,
        num_series=num_series,
        filename=filename if filename is not None else "default.epub",
        tags=tags if tags is not None else [],
        read=read
    )

    book.date_added_db = added.isoformat()
    book.last_modified_db = datetime.now().isoformat()
    book.path_in_library = f"{author}/{filename}" if author and filename else None
    book.size = 1024
    book.file_type = Path(filename).suffix if filename else ".epub"
    book.publisher = "Test Publisher"
    book.publication_date = "2023-01-01"
    book.isbn = "1234567890123"
    book.rating = 0
    book.notes = ""
    book.cover_image_path = None

    if not hasattr(book, 'added') or book.added is None : book.added = added
    if not hasattr(book, 'series'): book.series = series
    if not hasattr(book, 'num_series'): book.num_series = num_series
    if not hasattr(book, 'title') or book.title is None : book.title = title

    return book


@pytest.fixture
def mock_config_manager():
    cm = MagicMock(spec=ConfigManager)
    cm.paths = {"upload_dir_path": "/fake/uploads", "library_root": "/fake/library"}
    return cm

@pytest.fixture
def mock_book_manager():
    bm = MagicMock(spec=BookManager)
    bm.search_books_by_text = MagicMock()
    bm.get_book = MagicMock()
    bm.get_book_path = MagicMock()
    return bm

@pytest.fixture
def mock_library_manager(mock_book_manager):
    lm = MagicMock(spec=LibraryManager)
    lm.books = mock_book_manager
    lm.library_root = "/fake/library"
    return lm

@pytest.fixture
def main_screen_with_app(mock_config_manager, mock_library_manager):
    mock_app_instance = MagicMock(spec=App)
    mock_app_instance.push_screen = MagicMock()
    mock_app_instance.is_headless = True
    mock_app_instance.title = "Test App"
    mock_app_instance.sub_title = "Test Sub App"
    mock_app_instance._installed_screens = {}

    with patch('screens.main.AppLogger.get_logger', MagicMock(return_value=MagicMock())) as mock_logger_patch:
        app_token = active_app.set(mock_app_instance)
        try:
            screen = MainScreen(config_manager=mock_config_manager, library_manager=mock_library_manager)
            screen._app = mock_app_instance
        finally:
            active_app.reset(app_token)

        screen.notify = MagicMock()

        screen.mock_datatable_widget = MagicMock()
        screen.mock_datatable_widget.current_uuid = None

        def query_one_side_effect(selector, expected_type):
            if selector == "#books-table":
                return screen.mock_datatable_widget
            return MagicMock()
        screen.query_one = MagicMock(side_effect=query_one_side_effect)
        screen.logger = mock_logger_patch()

    return screen, mock_app_instance

# Timestamps for sorting
t1 = datetime(2023, 1, 1, 10, 0, 0)
t2 = datetime(2023, 1, 2, 10, 0, 0)
t3 = datetime(2023, 1, 3, 10, 0, 0)
t4 = datetime(2023, 1, 4, 10, 0, 0)

book_list_for_sorting = [
    create_book(uuid="b1", title="Book A", author="Author X", added=t1, series="Alpha", num_series=1.0),
    create_book(uuid="b2", title="Book B", author="Author Y", added=t2, series="Alpha", num_series=2.0),
    create_book(uuid="b3", title="Book C", author="Author Z", added=t3, series="Beta", num_series=1.0),
    create_book(uuid="b4", title="Book D", author="Author X", added=t1, series=None, num_series=None),
    create_book(uuid="b5", title="Book E", author="Author Y", added=t4, series="", num_series=1.0),
    create_book(uuid="b6", title="book F", author="Author Z", added=t2, series="alpha", num_series=3.0),
    create_book(uuid="b7", title="Book G", author="Author X", added=t3, series="Alpha", num_series=None),
    create_book(uuid="b8", title="Book H", author="Author Y", added=t4, series="Beta", num_series=0.5),
]

def get_sort_key_for_main_screen(book: Book):
    return (
        DescendingDateTime(book.added),
        (0 if book.series is None or book.series.strip() == '' else 1,
         book.series.strip().lower() if book.series and book.series.strip() else ''),
        (0 if book.num_series is None else 1,
         book.num_series if book.num_series is not None else float('-inf')),
        book.title.lower() if book.title else ''
    )

expected_order_generated = sorted(list(book_list_for_sorting), key=get_sort_key_for_main_screen)


def test_search_book_sorting(main_screen_with_app):
    main_screen, mock_app = main_screen_with_app
    main_screen.library_manager.books.search_books_by_text.return_value = list(book_list_for_sorting)
    main_screen._display_books_in_table = MagicMock()

    def mock_push_screen_side_effect(screen_instance_pushed):
        # Check if it's the InputScreen for search by checking its title attribute
        # and if it has a callback attribute (which InputScreen should have)
        if isinstance(screen_instance_pushed, InputScreen) and \
           "Search Book" in getattr(screen_instance_pushed, "title", "") and \
           hasattr(screen_instance_pushed, 'callback') and \
           callable(screen_instance_pushed.callback):
            screen_instance_pushed.callback("test_query") # Call the original callback

    mock_app.push_screen = MagicMock(side_effect=mock_push_screen_side_effect)

    app_token = active_app.set(mock_app)
    try:
        main_screen.action_search_book()
    finally:
        active_app.reset(app_token)

    main_screen.library_manager.books.search_books_by_text.assert_called_once_with("test_query")
    main_screen._display_books_in_table.assert_called_once()

    args, _ = main_screen._display_books_in_table.call_args
    sorted_books_by_action = args[0]

    assert [b.uuid for b in sorted_books_by_action] == [b.uuid for b in expected_order_generated]

def test_reload_search_after_edit(main_screen_with_app):
    main_screen, mock_app = main_screen_with_app
    main_screen.last_search_query = "test_query"
    edited_book_sample = create_book(uuid="b_edited", title="Edited Book", author="Author X", added=t1)
    main_screen.library_manager.books.search_books_by_text.return_value = list(book_list_for_sorting)
    main_screen._display_books_in_table = MagicMock()

    app_token = active_app.set(mock_app)
    try:
        main_screen._handle_edit_completion(edited_book_sample)
    finally:
        active_app.reset(app_token)

    main_screen.library_manager.books.search_books_by_text.assert_called_once_with("test_query")
    main_screen._display_books_in_table.assert_called_once()
    args, _ = main_screen._display_books_in_table.call_args
    sorted_books_after_edit = args[0]
    assert [b.uuid for b in sorted_books_after_edit] == [b.uuid for b in expected_order_generated]

    main_screen.last_search_query = None
    main_screen.library_manager.books.search_books_by_text.reset_mock()
    main_screen._display_books_in_table.reset_mock()
    main_screen.reload_table_data = MagicMock()

    app_token = active_app.set(mock_app)
    try:
        main_screen._handle_edit_completion(edited_book_sample)
    finally:
        active_app.reset(app_token)

    main_screen.reload_table_data.assert_called_once()
    main_screen.library_manager.books.search_books_by_text.assert_not_called()

@pytest.mark.asyncio
async def test_open_book_directory_success(main_screen_with_app):
    main_screen, mock_app = main_screen_with_app
    main_screen.mock_datatable_widget.current_uuid = "book1_uuid"
    mock_book = create_book(uuid="book1_uuid", title="Test Book", author="Test Author", added=datetime.now(), filename="book.epub")
    main_screen.library_manager.books.get_book.return_value = mock_book
    main_screen.library_manager.books.get_book_path.return_value = "/fake/library/Test Author/book.epub"

    with patch('screens.main.FileSystemHandler.open_file_with_default_app') as mock_open_fs, \
         patch('pathlib.Path.is_file', MagicMock(return_value=True)):

        app_token = active_app.set(mock_app)
        try:
            await main_screen.action_open_book_directory()
        finally:
            active_app.reset(app_token)

    mock_open_fs.assert_called_once_with("/fake/library/Test Author")
    main_screen.notify.assert_called_with("Attempting to open directory: /fake/library/Test Author", title="Open Directory")

@pytest.mark.asyncio
async def test_open_book_directory_no_selection(main_screen_with_app):
    main_screen, mock_app = main_screen_with_app
    main_screen.mock_datatable_widget.current_uuid = None
    with patch('screens.main.FileSystemHandler.open_file_with_default_app') as mock_open_fs:
        app_token = active_app.set(mock_app)
        try:
            await main_screen.action_open_book_directory()
        finally:
            active_app.reset(app_token)

    main_screen.notify.assert_called_with("No book selected to open its directory.", severity="warning", title="Selection Missing")
    mock_open_fs.assert_not_called()

@pytest.mark.asyncio
async def test_open_book_directory_book_not_found(main_screen_with_app):
    main_screen, mock_app = main_screen_with_app
    main_screen.mock_datatable_widget.current_uuid = "unknown_uuid"
    main_screen.library_manager.books.get_book.return_value = None
    with patch('screens.main.FileSystemHandler.open_file_with_default_app') as mock_open_fs:
        app_token = active_app.set(mock_app)
        try:
            await main_screen.action_open_book_directory()
        finally:
            active_app.reset(app_token)
    main_screen.notify.assert_called_with("Book not found.", severity="error", title="Error")
    mock_open_fs.assert_not_called()

@pytest.mark.asyncio
async def test_open_book_directory_path_value_error(main_screen_with_app):
    main_screen, mock_app = main_screen_with_app
    main_screen.mock_datatable_widget.current_uuid = "book1_uuid"
    mock_book = create_book(uuid="book1_uuid", title="Test Book", author="Test Author", added=datetime.now(), filename=None)
    main_screen.library_manager.books.get_book.return_value = mock_book
    main_screen.library_manager.books.get_book_path.side_effect = ValueError("Book has no filename.")
    with patch('screens.main.FileSystemHandler.open_file_with_default_app') as mock_open_fs:
        app_token = active_app.set(mock_app)
        try:
            await main_screen.action_open_book_directory()
        finally:
            active_app.reset(app_token)
    main_screen.notify.assert_called_with("Cannot determine book path: Book has no filename.", severity="warning", title="Directory Error")
    mock_open_fs.assert_not_called()

@pytest.mark.asyncio
async def test_open_book_directory_path_not_file(main_screen_with_app):
    main_screen, mock_app = main_screen_with_app
    main_screen.mock_datatable_widget.current_uuid = "book1_uuid"
    mock_book = create_book(uuid="book1_uuid", title="Test Book", author="Test Author", added=datetime.now(), filename="book.epub")
    main_screen.library_manager.books.get_book.return_value = mock_book
    main_screen.library_manager.books.get_book_path.return_value = "/fake/library/Test Author/not_a_file"
    with patch('screens.main.FileSystemHandler.open_file_with_default_app') as mock_open_fs, \
         patch('pathlib.Path.is_file', MagicMock(return_value=False)):
        app_token = active_app.set(mock_app)
        try:
            await main_screen.action_open_book_directory()
        finally:
            active_app.reset(app_token)
    main_screen.notify.assert_called_with("Book path is invalid. Cannot open directory.", severity="warning", title="Directory Error")
    mock_open_fs.assert_not_called()

@pytest.mark.asyncio
async def test_open_book_directory_runtime_error_on_open(main_screen_with_app):
    main_screen, mock_app = main_screen_with_app
    main_screen.mock_datatable_widget.current_uuid = "book1_uuid"
    mock_book = create_book(uuid="book1_uuid", title="Test Book", author="Test Author", added=datetime.now(), filename="book.epub")
    main_screen.library_manager.books.get_book.return_value = mock_book
    main_screen.library_manager.books.get_book_path.return_value = "/fake/library/Test Author/book.epub"
    with patch('screens.main.FileSystemHandler.open_file_with_default_app', side_effect=RuntimeError("OS error")) as mock_open_fs, \
         patch('pathlib.Path.is_file', MagicMock(return_value=True)):
        app_token = active_app.set(mock_app)
        try:
            await main_screen.action_open_book_directory()
        finally:
            active_app.reset(app_token)
    main_screen.notify.assert_called_with("Could not open directory: OS error", severity="error", title="Open Error")
    mock_open_fs.assert_called_once_with("/fake/library/Test Author")
