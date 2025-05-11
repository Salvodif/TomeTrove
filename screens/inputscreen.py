from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, Button

class InputScreen(ModalScreen[str]):
    """Screen per l'input di ricerca"""
    
    def __init__(self, title: str, placeholder: str, callback: callable):
        super().__init__()
        self.title = title
        self.placeholder = placeholder
        self.callback = callback
    
    def compose(self) -> ComposeResult:
        yield Input(placeholder=self.placeholder, id="search-input")
        yield Button("Cerca", id="search-button")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-button":
            input = self.query_one("#search-input", Input)
            self.callback(input.value)
            self.dismiss()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.callback(event.value)
        self.dismiss()