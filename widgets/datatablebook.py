from typing import List, Optional
from textual.widgets import DataTable


class DataTableBook(DataTable):
    """A DataTable widget specialized for displaying book information."""
    def on_mount(self):
        """Sets up the table columns when the widget is mounted."""
        self.add_column("Added", width=10)      # Column for "Aggiunto"
        self.add_column("Author", width=25)     # Column for "Autore"
        self.add_column("Title", width=90)      # Column for "Titolo"
        self.add_column("Read", width=5)        # Column for "Letto"
        self.add_column("Tags", width=30)
        self.cursor_type = "row"
        self._current_uuid = 0 # Stores the UUID of the currently highlighted/selected row

    def update_table(self, books):
        """Clears and repopulates the table with a list of book objects."""
        self.clear()

        if not books: # Handle empty book list
             return

        for i, b in enumerate(books):
            read_date = "—"  # Default value for read status
            if b.read is not None: # If 'read' field has a value (datetime object), mark as read
                read_date = "X"

            added_date = b.added.strftime("%Y-%m-%d") # Format added date
            tags_display = ", ".join(b.tags) # Join tags into a comma-separated string

            self.add_row(
                added_date,
                b.author,
                b.title,
                read_date,
                tags_display,
                key=b.uuid # Use book's UUID as the row key
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Event handler for when a row is highlighted."""
        if event.row_key.value is not None:
            self._current_uuid = event.row_key.value

    @property
    def current_column(self) -> Optional[int]:
        """Gets the index of the currently focused column, if any."""
        if self.cursor_row is not None and self.cursor_column is not None:
            return self.cursor_column
        return None

    @property
    def current_uuid(self):
        """Gets the UUID of the currently highlighted/selected row."""
        return self._current_uuid
