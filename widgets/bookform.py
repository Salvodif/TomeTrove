from pathlib import Path
from typing import Optional, List
from textual.app import ComposeResult
from textual.widgets import Input, Button, TextArea, DirectoryTree, Label, Checkbox
from textual.containers import Vertical, Horizontal, VerticalScroll
from datetime import datetime

from textual_autocomplete import AutoComplete, DropdownItem, TargetState


class AuthorAutoComplete(AutoComplete):
    def __init__(self,
                 target: Input | str,
                 all_authors: List[str],
                 **kwargs):
        super().__init__(target, candidates=None, **kwargs) # Pass None to candidates, we use get_candidates
        self.all_authors = sorted(list(set(all_authors if all_authors else [])))

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """
        Called by the AutoComplete widget to get the list of dropdown items.
        """
        prefix = self.get_search_string(target_state) # Get what the user has typed
        if not prefix:
            return []

        matches: list[DropdownItem] = []
        for author_name in self.all_authors:
            if author_name.lower().startswith(prefix.lower()):
                matches.append(DropdownItem(main=author_name)) # prefix can be an icon etc.
        return matches


class TagAutoComplete(AutoComplete):
    def __init__(self,
                 target: Input | str,
                 all_tags: List[str],
                 **kwargs):
        super().__init__(target, candidates=None, **kwargs)
        self.all_tags = sorted(list(set(all_tags if all_tags else [])))

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        prefix = self.get_search_string(target_state)

        current_tag_prefix = prefix
        if ',' in prefix:
            parts = prefix.split(',')
            current_tag_prefix = parts[-1].lstrip() # Get the last part, remove leading space

        if not current_tag_prefix:
            return []

        matches: list[DropdownItem] = []
        for tag_name in self.all_tags:
            if tag_name.lower().startswith(current_tag_prefix.lower()):
                matches.append(DropdownItem(main=tag_name))
        return matches

    def apply_completion(self, value: str, state: TargetState) -> None:
        """
        Override to correctly insert the completed tag in a comma-separated list.
        """
        target_input_widget = self.target # Get the actual Input widget

        current_text = state.text
        cursor_pos = state.cursor_position

        start_of_current_tag = 0
        last_comma_before_cursor = current_text.rfind(',', 0, cursor_pos)
        if last_comma_before_cursor != -1:
            start_of_current_tag = last_comma_before_cursor + 1

            while start_of_current_tag < cursor_pos and current_text[start_of_current_tag].isspace():
                start_of_current_tag += 1

        prefix_text = current_text[:start_of_current_tag]
        suffix_text = current_text[cursor_pos:]

        new_text_parts = []
        if prefix_text.strip().endswith(','): # if there was already a comma
             new_text_parts.append(prefix_text)
             new_text_parts.append(value)
        elif prefix_text.strip(): # if there was text before, but no comma
            new_text_parts.append(prefix_text)
            if not prefix_text.endswith(" "): new_text_parts.append(" ") # ensure space
            new_text_parts.append(value)
        else: # first tag
            new_text_parts.append(value)

        # Add a comma and space for the next tag, then the suffix
        new_text_parts.append(", ") 

        # Reconstruct the full text
        final_text = "".join(new_text_parts) + suffix_text.lstrip(", ") # Avoid double commas from suffix

        # More refined reconstruction:
        existing_tags_before = [t.strip() for t in current_text[:start_of_current_tag].split(',') if t.strip()]
        all_tags_list = existing_tags_before + [value]

        # Get tags that were after the cursor originally
        tags_after_cursor = [t.strip() for t in suffix_text.split(',') if t.strip()]
        all_tags_list.extend(tags_after_cursor)

        # Join them back, ensuring uniqueness if desired (not doing it here for simplicity)
        final_reconstructed_text = ", ".join(tag for tag in all_tags_list if tag)


        with self.prevent(Input.Changed): # Prevent feedback loop
            target_input_widget.value = final_reconstructed_text
            # Try to place cursor after the inserted tag + ", "
            # Calculate new cursor position: length of prefix + new tag + ", "
            new_cursor_pos = len(", ".join(existing_tags_before + [value])) + 2 if existing_tags_before else len(value) + 2
            target_input_widget.cursor_position = new_cursor_pos
        
        # This will trigger a rebuild of options via _handle_target_update
        # self.post_completion() # Default hides, which is fine


class BookForm:
    def __init__(self,
                 book=None,
                 start_directory: str = ".",
                 add_new_book: bool = True,
                 all_authors: Optional[List[str]] = None,
                 all_tags: Optional[List[str]] = None):

        _authors = all_authors if all_authors is not None else []
        _tags = all_tags if all_tags is not None else []
        self.book_data = book

        self.author_target_input = Input(placeholder="Autore", value=book.author if book else "", classes="form-input", id="author_input_target")
        self.tags_target_input = Input(placeholder="Tags (separati da virgola)", value=", ".join(book.tags) if book and book.tags else "", classes="form-input", id="tags_input_target")

        self.author_autocomplete = AuthorAutoComplete(
            target=f"#{self.author_target_input.id}", # Target by ID
            all_authors=_authors,
            prevent_default_tab=False, # Allow tabbing out after selection
            prevent_default_enter=True # Prevent form submission on enter if dropdown open
        )
        self.tags_autocomplete = TagAutoComplete(
            target=f"#{self.tags_target_input.id}", # Target by ID
            all_tags=_tags,
            prevent_default_tab=False,
            prevent_default_enter=True
        )


        self.title_input = Input(placeholder="Titolo", value=book.title if book else "", classes="form-input")
        self.series_input = Input(placeholder="Serie", value=book.series if book and book.series else "", classes="form-input")
        self.num_series_input = Input(placeholder="Numero serie", value=str(book.num_series) if book and book.num_series is not None else "", classes="form-input")
        self.read_input = Input(placeholder="Data lettura (YYYY-MM-DD HH:MM)", value=book.read if book and book.read else "", classes="form-input")
        self.description_input = TextArea(book.description if book and book.description else "", language="markdown", classes="form-input")
        self.save_button = Button("Salva", id="save", variant="primary", classes="button-primary")

        self.file_tree: Optional[DirectoryTree] = None
        self.selected_file_label: Optional[Label] = None
        self.add_new_book = add_new_book

        if self.add_new_book: # Add mode
            self.file_tree = DirectoryTree(f"{start_directory}", id="file-browser")
            self.file_tree.show_hidden = False
            self.file_tree.filter_dirs = True
            self.file_tree.valid_extensions = {".pdf", ".epub", ".docx", }
            self.selected_file_label = Label("Nessun file selezionato", id="selected-file")

            self.read_input.disabled = True 
        else: # Edit mode (not show_file_browser)
            self.read_status_label = Label("Letto?", classes="form-label")
            self.read_checkbox = Checkbox("", value=bool(book.read) if book else False, classes="form-checkbox", id="read_status_checkbox")
            self.read_checkbox.tooltip = "Spunta se hai letto questo libro"
            self._update_read_input_state() # Initialize state based on checkbox/book data for Edit mode

        form_elements = []
        if self.add_new_book and self.file_tree and self.selected_file_label: # Add mode
            form_elements.extend([
                Label("Seleziona file:", classes="form-label-heading"),
                Horizontal(self.file_tree),
                self.selected_file_label,
            ])

        form_elements.extend([
            Horizontal(Label("Titolo:", classes="form-label"), self.title_input, classes="form-row"),
            Horizontal(Label("Autore:", classes="form-label"), self.author_target_input, classes="form-row"),
            Horizontal(Label("Tags:", classes="form-label"), self.tags_target_input, classes="form-row"),
            Horizontal(Label("Serie:", classes="form-label"), self.series_input, classes="form-row"),
            Horizontal(Label("Numero:", classes="form-label"), self.num_series_input,classes="form-row"),
        ])

        if not self.add_new_book and self.read_status_label and self.read_checkbox: # Edit mode
            form_elements.append(
                Horizontal(
                    self.read_status_label,
                    self.read_checkbox,
                    self.read_input,
                    classes="form-row",
                    id="read-status-row"
                )
            )
        # In Add mode (self.add_new_book is True), this block is skipped,
        # and read_input (though it exists) is not added to the layout.

        form_elements.append(
            Horizontal(
                 Label("Descrizione:", classes="form-label"),
                 self.description_input,
                 classes="form-row"
            )
        )

        self.form_container = VerticalScroll(
            Vertical(*form_elements, id="form-content"),
            id="form-container"
        )

    def _update_read_input_state(self) -> None:
        """Aggiorna lo stato del campo read_input basandosi sulla checkbox (only for Edit mode)."""
        if self.add_new_book or not self.read_checkbox: # If in Add mode or checkbox doesn't exist
            self.read_input.disabled = True # Ensure it's disabled for Add mode
            return

        # This logic now only applies if not show_file_browser (i.e., Edit mode)
        if self.read_checkbox.value:
            if not self.read_input.value.strip():
                today = datetime.now().strftime("%Y-%m-%d %H:%M")
                self.read_input.value = today
            self.read_input.disabled = False
        else:
            self.read_input.value = ""
            self.read_input.disabled = True

    def handle_read_checkbox_change(self) -> None:
        """Called by the parent screen when the checkbox changes (only for Edit mode)."""
        if not self.add_new_book: # Only handle if in Edit mode
            self._update_read_input_state()

    def compose_form(self) -> ComposeResult:
        """
        This method now just returns the main form container.
        The AutoComplete widgets will be composed by the parent screen.
        """
        yield self.form_container


    def get_autocomplete_widgets(self) -> List[AutoComplete]:
        """Helper to get the autocomplete widgets for the parent screen to compose."""
        return [self.author_autocomplete, self.tags_autocomplete]

    def get_values(self):
        filename_path = None
        try:
            if self.add_new_book and self.selected_file_label: # Add mode
                label_content = str(self.selected_file_label.renderable)
                if label_content != "Nessun file selezionato" and label_content.strip() != "Errore nella selezione":
                    candidate_path = Path(label_content)
                    if candidate_path.is_file():
                        filename_path = candidate_path
            elif not self.add_new_book and self.book_data and self.book_data.filename: # Edit mode
                if self.book_data.filename:
                    filename_path = Path(self.book_data.filename)
        except Exception:
            filename_path = None

        num_series_value = None
        try:
            if self.num_series_input.value.strip():
                num_series_value = float(self.num_series_input.value)
        except (ValueError, TypeError):
            num_series_value = None

        read_value = None
        if not self.add_new_book and self.read_checkbox: # Edit mode
            if self.read_checkbox.value:
                read_value = self.read_input.value.strip() if self.read_input.value.strip() else None
        # In Add mode (add_new_book is True), read_value remains None

        return {
            'title': self.title_input.value.strip(),
            'author': self.author_target_input.value.strip(),
            'tags': [tag.strip() for tag in self.tags_target_input.value.split(",") if tag.strip()],
            'series': self.series_input.value.strip() if self.series_input.value.strip() else None,
            'num_series': num_series_value,
            'read': read_value,
            'description': self.description_input.text.strip() if self.description_input.text.strip() else None,
            'filename': filename_path
        }


    def validate(self):
        if not self.title_input.value.strip():
            return "Il titolo è obbligatorio"
        if not self.author_target_input.value.strip():
            return "L'autore è obbligatorio"

        if self.num_series_input.value.strip():
            try:
                float(self.num_series_input.value)
            except ValueError:
                 return "Numero serie deve essere un numero valido (es. 1 o 2.5)"

        # Validate read_input only if in Edit mode and checkbox is checked
        if not self.add_new_book and self.read_checkbox and self.read_checkbox.value: # Edit mode
            if self.read_input.value.strip():
                try:
                    datetime.strptime(self.read_input.value.strip(), "%Y-%m-%d %H:%M")
                except ValueError:
                    return "Formato data lettura non valido (usare YYYY-MM-DD HH:MM)"
            else:
                return "La data di lettura è richiesta se il libro è segnato come letto."

        if self.add_new_book: # Add mode file validation
            if self.selected_file_label:
                 label_content = str(self.selected_file_label.renderable)
                 if label_content == "Nessun file selezionato" or label_content.strip() == "Errore nella selezione":
                    # For adding, file selection is usually mandatory.
                    # Check if this form is for a new book (no self.book_data)
                    if not self.book_data:
                         return "È necessario selezionare un file per un nuovo libro."
        return None