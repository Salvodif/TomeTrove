from typing import List, Optional
from textual.widgets import DataTable


class DataTableBook(DataTable):
    def on_mount(self):
        self.add_column("Aggiunto", width=10)
        self.add_column("Autore", width=25)
        self.add_column("Titolo", width=90)
        self.add_column("Letto", width=5)
        self.add_column("Tags", width=30)
        self.cursor_type = "row"
        self._current_uuid = 0
        self._last_clicked_column = "added"

    def update_table(self, books, formatted_tags: Optional[List[str]] = None):
        self.clear()

        if not books: # Handle empty book list
             return

        # Ensure formatted_tags list matches books list length if provided
        if formatted_tags and len(formatted_tags) != len(books):
             # Fallback or error - let's fallback to raw tags for safety
             print("Warning: Mismatch between books and formatted_tags count. Falling back to raw tags.")
             formatted_tags = None # Reset to None

        for i, b in enumerate(books):
            read_date = "—"  # Valore predefinito
            if b.read is not None and len(b.read) > 0:
                read_date = "X"

            added_date = b.added.strftime("%Y-%m-%d")
            # tags_display = formatted_tags[i] if formatted_tags else ", ".join(b.tags)
            tags_display = ", ".join(b.tags)

            self.add_row(
                added_date,
                b.author,
                b.title,
                read_date,
                tags_display,
                key=b.uuid
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key.value is not None:
            self._current_uuid = event.row_key.value

    def on_data_table_header_selected(self, event):
        column_mapping = {
            0: "added",
            1: "author",
            2: "title",
            3: "read",
            4: "tags"
        }

        self.sort_field = column_mapping.get(event.column_index, "added")
        self.sort_reverse = False
        self.update_table()

    @property
    def current_column(self) -> Optional[int]:
        if self.cursor_row is not None and self.cursor_column is not None:
            return self.cursor_column
        return None

    @property
    def current_uuid(self):
        return self._current_uuid

    @property
    def last_clicked_column(self):
        return self._last_clicked_column