from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Static
from textual.containers import Vertical, Horizontal # MODIFICATO QUI
from typing import Optional

class ConfirmationScreen(Screen[bool]):
    """A screen to ask for user confirmation."""

    DEFAULT_CSS = """
    ConfirmationScreen {
        align: center middle;
    }

    #confirm_dialog {
        width: auto;
        max-width: 80%;
        height: auto;
        padding: 2 4;
        border: thick $primary;
        background: $surface;
    }

    #confirm_prompt {
        width: auto; /* Ensures the label takes the width of its content */
        padding-bottom: 1;
        content-align: center middle; /* Aligns text content within the label */
        text-align: center; /* Aligns the label itself if its width is larger than text */
    }
    
    #confirm_buttons {
        width: 100%; /* Make the horizontal layout take full width of the dialog */
        align: center middle; /* Center buttons within the layout */
        padding-top: 1;
    }

    Button {
        min-width: 10; /* Ensure buttons have a decent minimum width */
        margin: 0 1;
    }
    """

    def __init__(
        self,
        prompt: str = "Are you sure?",
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self._prompt = prompt
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm_dialog"):
            yield Static(self._prompt, id="confirm_prompt")
            with Horizontal(id="confirm_buttons"): # MODIFICATO QUI
                yield Button(self._confirm_label, variant="primary", id="confirm_action")
                yield Button(self._cancel_label, variant="error", id="cancel_action")

    def on_mount(self) -> None:
        """Focus the confirm button when the screen is mounted."""
        self.query_one("#confirm_action", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss the screen with a result when a button is pressed."""
        if event.button.id == "confirm_action":
            self.dismiss(True)
        elif event.button.id == "cancel_action":
            self.dismiss(False)