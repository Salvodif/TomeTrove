from textual import message

class BookAdded(message.Message):
    """Messaggio inviato quando un nuovo libro viene aggiunto"""
    def __init__(self, book=None):
        self.book = book
        super().__init__()