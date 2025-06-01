from pathlib import Path
from typing import Optional, List
from textual.app import ComposeResult
from textual.widgets import Input, Button, TextArea, DirectoryTree, Label, Checkbox
from textual.containers import Vertical, Horizontal, VerticalScroll
from datetime import datetime
from textual.message import Message # Added import

from textual_autocomplete import AutoComplete, DropdownItem, TargetState


class SeriesSelectedInternalMessage(Message):
    def __init__(self, series_name: str, autocomplete_control: AutoComplete) -> None:
        super().__init__()
        self.series_name = series_name
        self.autocomplete_control = autocomplete_control

class AuthorAutoComplete(AutoComplete):
    """An AutoComplete widget for author names."""
    def __init__(self,
                 target: Input | str,
                 all_authors: List[str],
                 **kwargs):
        # Pass None to candidates; we use get_candidates to dynamically fetch them.
        super().__init__(target, candidates=None, **kwargs) 
        self.all_authors = sorted(list(set(all_authors if all_authors else [])))

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """
        Called by the AutoComplete widget to get the list of dropdown items
        based on the current input.
        """
        prefix = self.get_search_string(target_state) # Get what the user has typed.
        if not prefix:
            return []

        matches: list[DropdownItem] = []
        for author_name in self.all_authors:
            if author_name.lower().startswith(prefix.lower()):
                # 'main' is the text displayed in the dropdown.
                matches.append(DropdownItem(main=author_name)) 
        return matches


class TagAutoComplete(AutoComplete):
    """An AutoComplete widget for tags, supporting comma-separated input."""
    def __init__(self,
                 target: Input | str,
                 all_tags: List[str],
                 **kwargs):
        super().__init__(target, candidates=None, **kwargs)
        self.all_tags = sorted(list(set(all_tags if all_tags else [])))

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """
        Gets candidate tags based on the currently typed part of a tag
        in a comma-separated list.
        """
        prefix = self.get_search_string(target_state)

        current_tag_prefix = prefix
        if ',' in prefix:
            parts = prefix.split(',')
            current_tag_prefix = parts[-1].lstrip() # Consider only the part after the last comma.

        if not current_tag_prefix:
            return []

        matches: list[DropdownItem] = []
        for tag_name in self.all_tags:
            if tag_name.lower().startswith(current_tag_prefix.lower()):
                matches.append(DropdownItem(main=tag_name))
        return matches

    def apply_completion(self, value: str, state: TargetState) -> None:
        """
        Overrides the default behavior to correctly insert the completed tag
        into a comma-separated list.
        """
        target_input_widget = self.target # The Input widget this AutoComplete is attached to.

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
        if prefix_text.strip().endswith(','): # If there was already a comma.
             new_text_parts.append(prefix_text)
             new_text_parts.append(value)
        elif prefix_text.strip(): # If there was text before, but no comma.
            new_text_parts.append(prefix_text)
            if not prefix_text.endswith(" "): new_text_parts.append(" ") # Ensure space.
            new_text_parts.append(value)
        else: # This is the first tag.
            new_text_parts.append(value)

        # Add a comma and space for the next tag, then the suffix.
        new_text_parts.append(", ") 

        # Reconstruct the full text.
        # Avoid double commas from suffix (e.g. if user typed ", " and then completed).
        final_text = "".join(new_text_parts) + suffix_text.lstrip(", ") 

        # More refined reconstruction to handle existing tags robustly.
        existing_tags_before = [t.strip() for t in current_text[:start_of_current_tag].split(',') if t.strip()]
        all_tags_list = existing_tags_before + [value]

        # Get tags that were after the cursor originally.
        tags_after_cursor = [t.strip() for t in suffix_text.split(',') if t.strip()]
        all_tags_list.extend(tags_after_cursor)

        # Join them back.
        final_reconstructed_text = ", ".join(tag for tag in all_tags_list if tag)
        # If there are any tags, add a trailing comma and space for the next tag.
        if final_reconstructed_text:
            final_reconstructed_text += ", "


        with self.prevent(Input.Changed): # Prevent feedback loop from Input.Changed event.
            self.target.value = final_reconstructed_text
            target_input_widget.value = final_reconstructed_text

            # Calculate new cursor position: after the inserted tag + ", " (or just after the text if no tags yet).
            if final_reconstructed_text: # If text exists (meaning a completion happened and we added ", ")
                new_cursor_pos = len(final_reconstructed_text)
            else: # Should not happen if a completion was applied, but as a fallback
                new_cursor_pos = len(value)

            self.target.cursor_position = new_cursor_pos
            target_input_widget.cursor_position = new_cursor_pos
        
        self.post_completion() # Default behavior hides the dropdown, which is usually fine.


class SeriesAutoComplete(AutoComplete):
    """An AutoComplete widget for series names."""
    def __init__(self,
                 target: Input | str,
                 all_series: List[str],
                 **kwargs):
        # Pass None to candidates; we use get_candidates to dynamically fetch them.
        super().__init__(target, candidates=None, **kwargs)
        self.all_series = sorted(list(set(all_series if all_series else [])))

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """
        Called by the AutoComplete widget to get the list of dropdown items
        based on the current input.
        """
        search_string = self.get_search_string(target_state) # Get what the user has typed.
        if not search_string:
            return []

        matches: list[DropdownItem] = []
        for series_name in self.all_series:
            if series_name.lower().startswith(search_string.lower()):
                # 'main' is the text displayed in the dropdown.
                matches.append(DropdownItem(main=series_name))
        return matches

    def post_completion(self) -> None:
        # It's crucial to get the value *before* calling super().post_completion()
        # if super().post_completion() might clear the input or change focus in a way
        # that makes self.target.value unreliable.
        # However, the docs say post_completion is called *after* apply_completion,
        # so the value should be stable in self.target.value.

        selected_series_name = ""
        # self.target is the Input widget instance in this application's setup
        if isinstance(self.target, Input):
            selected_series_name = self.target.value
        # else:
            # If self.target could be an ID string, we'd need to query the input:
            # try:
            #     input_widget = self.app.query_one(self.target, Input)
            #     selected_series_name = input_widget.value
            # except Exception:
            #     pass # Or log error

        super().post_completion() # Call parent's post_completion (usually hides dropdown)

        if selected_series_name: # Only post if a name was actually retrieved
            self.post_message(SeriesSelectedInternalMessage(selected_series_name, self))


class BookForm:
    """
    A form class (not a direct Textual widget) that composes and manages
    input fields for adding or editing book details.
    It provides methods to get form values and validate them.
    The actual display and layout are handled by the parent screen (AddScreen/EditScreen)
    which composes the widgets returned by this class.
    """
    def __init__(self,
                 book=None, # Optional Book object for editing
                 start_directory: str = ".", # Starting directory for file browser in add mode
                 add_new_book: bool = True, # True for Add mode, False for Edit mode
                 all_authors: Optional[List[str]] = None, # List of all authors for autocomplete
                 all_tags: Optional[List[str]] = None, # List of all tags for autocomplete
                 all_series: Optional[List[str]] = None): # List of all series for autocomplete

        _authors = all_authors if all_authors is not None else []
        _tags = all_tags if all_tags is not None else []
        _series = all_series if all_series is not None else []
        self.book_data = book # Store the book object if editing

        self.author_target_input = Input(placeholder="Author", value=book.author if book else "", classes="form-input", id="author_input_target")
        self.tags_target_input = Input(placeholder="Tags (comma-separated)", value=", ".join(book.tags) if book and book.tags else "", classes="form-input", id="tags_input_target")

        self.author_autocomplete = AuthorAutoComplete(
            target=f"#{self.author_target_input.id}", # Target by ID for Textual to find the Input
            all_authors=_authors,
            prevent_default_tab=False, # Allow tabbing out after selection
            prevent_default_enter=True # Prevent form submission on enter if dropdown is open
        )
        self.tags_autocomplete = TagAutoComplete(
            target=f"#{self.tags_target_input.id}", # Target by ID
            all_tags=_tags,
            prevent_default_tab=False,
            prevent_default_enter=True
        )
        self.series_target_input = Input(placeholder="Series", value=book.series if book and book.series else "", classes="form-input", id="series_input_target")
        self.series_autocomplete = SeriesAutoComplete(
            target=f"#{self.series_target_input.id}",
            all_series=_series,
            prevent_default_tab=False,
            prevent_default_enter=True,
            id="form_series_autocomplete" # Added static ID
        )

        self.title_input = Input(placeholder="Title", value=book.title if book else "", classes="form-input")
        self.num_series_input = Input(placeholder="Series Number", value=str(book.num_series) if book and book.num_series is not None else "", classes="form-input")
        read_value_str = book.read.strftime("%Y-%m-%d %H:%M") if book and book.read and isinstance(book.read, datetime) else ""
        self.read_input = Input(placeholder="Read Date (YYYY-MM-DD HH:MM)", value=read_value_str, classes="form-input")
        self.description_input = TextArea(book.description if book and book.description else "", language="markdown", classes="form-input")
        self.save_button = Button("Save", id="save", variant="primary", classes="button-primary")

        self.file_tree: Optional[DirectoryTree] = None
        self.selected_file_label: Optional[Label] = None
        self.add_new_book = add_new_book # Mode: True for Add, False for Edit

        if self.add_new_book: # Configuration for "Add Book" mode
            self.file_tree = DirectoryTree(f"{start_directory}", id="file-browser")
            self.file_tree.show_hidden = False
            self.file_tree.filter_dirs = True # Only show directories, user clicks to expand
            self.file_tree.valid_extensions = {".pdf", ".epub", ".docx", } # Filter files by these extensions
            self.selected_file_label = Label("No file selected", id="selected-file")
            self.read_input.disabled = True # Read date is not applicable when adding a new book
        else: # Configuration for "Edit Book" mode
            self.read_status_label = Label("Read?", classes="form-label")
            self.read_checkbox = Checkbox("", value=bool(book.read) if book else False, classes="form-checkbox", id="read_status_checkbox")
            self.read_checkbox.tooltip = "Check if you have read this book"
            self._update_read_input_state() # Initialize read_input state based on checkbox/book data

        # Assemble form elements for layout
        form_elements = []
        if self.add_new_book and self.file_tree and self.selected_file_label: # Add file browser for "Add" mode
            form_elements.extend([
                Label("Select File:", classes="form-label-heading"),
                Horizontal(self.file_tree), # DirectoryTree itself is scrollable if content exceeds height
                self.selected_file_label,
            ])

        form_elements.extend([
            Horizontal(Label("Title:", classes="form-label"), self.title_input, classes="form-row"),
            Horizontal(Label("Author:", classes="form-label"), self.author_target_input, classes="form-row"),
            Horizontal(Label("Tags:", classes="form-label"), self.tags_target_input, classes="form-row"),
            Horizontal(Label("Series:", classes="form-label"), self.series_target_input, classes="form-row"),
            Horizontal(Label("Number:", classes="form-label"), self.num_series_input,classes="form-row"),
        ])

        if not self.add_new_book and self.read_status_label and self.read_checkbox: # Add read status controls for "Edit" mode
            form_elements.append(
                Horizontal(
                    self.read_status_label,
                    self.read_checkbox,
                    self.read_input,
                    classes="form-row",
                    id="read-status-row"
                )
            )
        # In "Add" mode, read_input is created but not added to the layout (and is disabled).

        form_elements.append(
            Horizontal(
                 Label("Description:", classes="form-label"),
                 self.description_input, # TextArea itself can be made scrollable via styles if needed
                 classes="form-row"
            )
        )
        # The VerticalScroll wraps all form elements, allowing scrolling if the form is too long.
        self.form_container = VerticalScroll(
            Vertical(*form_elements, id="form-content"),
            id="form-container"
        )

    def _update_read_input_state(self) -> None:
        """Updates the state of the read_input field based on the read_checkbox (Edit mode only)."""
        if self.add_new_book or not self.read_checkbox: # Guard for "Add" mode or if checkbox isn't created
            if self.read_input: self.read_input.disabled = True 
            return

        # Logic for "Edit" mode
        if self.read_checkbox.value: # If checkbox is checked
            if not self.read_input.value.strip(): # And read_input is empty
                today = datetime.now().strftime("%Y-%m-%d %H:%M")
                self.read_input.value = today # Default to current date/time
            self.read_input.disabled = False # Enable input
        else: # If checkbox is not checked
            self.read_input.value = "" # Clear input
            self.read_input.disabled = True # Disable input

    def handle_read_checkbox_change(self) -> None:
        """Called by the parent screen when the read_checkbox changes state (Edit mode only)."""
        if not self.add_new_book: # Only act if in "Edit" mode
            self._update_read_input_state()

    def compose_form(self) -> ComposeResult:
        """
        Yields the main form container for the parent screen to compose.
        AutoComplete widgets are handled separately by the parent screen.
        """
        yield self.form_container


    def get_autocomplete_widgets(self) -> List[AutoComplete]:
        """Helper to get the AutoComplete widgets for the parent screen to compose."""
        return [self.author_autocomplete, self.tags_autocomplete, self.series_autocomplete]

    def get_values(self):
        """
        Retrieves all values from the form fields.
        Returns a dictionary with field names as keys.
        """
        filename_path = None
        try:
            if self.add_new_book and self.selected_file_label: # "Add" mode: get path from label
                label_content = str(self.selected_file_label.renderable)
                if label_content != "No file selected" and label_content.strip() != "Error in selection":
                    candidate_path = Path(label_content)
                    if candidate_path.is_file():
                        filename_path = candidate_path
            elif not self.add_new_book and self.book_data and self.book_data.filename: # "Edit" mode: use existing filename
                if self.book_data.filename: # Ensure it's not empty
                    filename_path = Path(self.book_data.filename) # This will be just the filename string
        except Exception: # Catch any error during path processing
            filename_path = None

        num_series_value = None
        try:
            if self.num_series_input.value.strip():
                num_series_value = float(self.num_series_input.value)
        except (ValueError, TypeError): # Handle non-numeric input
            num_series_value = None

        read_value = None
        if not self.add_new_book and self.read_checkbox: # "Edit" mode: get from read_input if checkbox is checked
            if self.read_checkbox.value:
                read_value = self.read_input.value.strip() if self.read_input.value.strip() else None
        # In "Add" mode, read_value remains None as read_input is disabled.

        return {
            'title': self.title_input.value.strip(),
            'author': self.author_target_input.value.strip(),
            'tags': [tag.strip() for tag in self.tags_target_input.value.split(",") if tag.strip()],
            'series': self.series_target_input.value.strip() if self.series_target_input.value.strip() else None,
            'num_series': num_series_value,
            'read': read_value, # This will be a string or None
            'description': self.description_input.text.strip() if self.description_input.text.strip() else None,
            'filename': filename_path # This will be a Path object or None
        }


    def validate(self):
        """
        Validates the form fields.
        Returns an error message string if validation fails, otherwise None.
        """
        if not self.title_input.value.strip():
            return "Title is required"
        if not self.author_target_input.value.strip():
            return "Author is required"

        if self.num_series_input.value.strip():
            try:
                float(self.num_series_input.value)
            except ValueError:
                 return "Series number must be a valid number (e.g., 1 or 2.5)"

        # Validate read_input only if in "Edit" mode and checkbox is checked
        if not self.add_new_book and self.read_checkbox and self.read_checkbox.value:
            if self.read_input.value.strip():
                try:
                    datetime.strptime(self.read_input.value.strip(), "%Y-%m-%d %H:%M")
                except ValueError:
                    return "Invalid read date format (use YYYY-MM-DD HH:MM)"
            else: # Checkbox is checked but date field is empty
                return "Read date is required if the book is marked as read."

        if self.add_new_book: # File validation for "Add" mode
            if self.selected_file_label:
                 label_content = str(self.selected_file_label.renderable)
                 if label_content == "No file selected" or label_content.strip() == "Error in selection":
                    # For adding a new book, file selection is mandatory.
                    if not self.book_data: # Ensure it's truly a new book, not an edit scenario misconfigured
                         return "A file must be selected for a new book."
        return None