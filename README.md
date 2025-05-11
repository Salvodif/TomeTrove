<div align="center">
  <img src="https://raw.githubusercontent.com/salvodif/TomeTrove/assets/tometrove_logo_square_pastello_banner.png" width="300" alt="TomeTrove Logo" />
  <h1>📚 TomeTrove</h1>
  <p><em>A Python TUI application for managing your digital book library, built with Textual.</em></p>

  <!-- Badges -->
  <p align="center">
    <a href="https://www.python.org/downloads/">
      <img src="https://img.shields.io/badge/python-3.x-blue.svg" alt="Python Version">
    </a>
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT">
    </a>
    <a href="https://github.com/Textualize/textual">
      <img src="https://img.shields.io/badge/UI-Textual-brightgreen.svg" alt="Textual TUI">
    </a>
    <a href="https://tinydb.readthedocs.io/">
      <img src="https://img.shields.io/badge/database-TinyDB-orange.svg" alt="TinyDB">
    </a>
    <a href="https://github.com/salvodif/TomeTrove/stargazers">
      <img src="https://img.shields.io/github/stars/salvodif/TomeTrove?style=social" alt="GitHub Stars">
    </a>
    <a href="https://github.com/salvodif/TomeTrove/issues">
      <img src="https://img.shields.io/github/issues/salvodif/TomeTrove" alt="GitHub Issues">
    </a>
    <a href="https://github.com/salvodif/TomeTrove/network/members">
      <img src="https://img.shields.io/github/forks/salvodif/TomeTrove?style=social" alt="GitHub Forks">
    </a>
  </p>
</div>

TomeTrove is a command-line application built with [Textual](https://github.com/Textualize/textual) for managing your personal digital library of books (primarily PDFs, EPUBs, DOCX, etc.). It allows you to add, edit, view, search, and organize your books, all within a rich terminal user interface.

---

## 🚀 Features

*   **📚 Library Management**: View your book collection in a sortable, filterable table.
*   **➕ Add New Books**: Easily add new books from your filesystem.
    *   Files are copied into an organized library structure (by author).
    *   Automatic filename generation based on title and author for consistency.
*   **✏️ Edit Book Metadata**: Modify title, author, tags, series information, read status, description, and more.
*   **🏷️ Tagging System**: Organize books with custom tags.
    *   Autocomplete for existing tags when adding/editing.
*   **✍️ Author Autocomplete**: Suggests existing authors during input.
*   **🔎 Search Functionality**: Quickly find books by title or author.
*   **📖 Read Status**: Mark books as read and record the date (or clear read status).
*   **🛠️ PDF/File Metadata Update**: Optionally updates file metadata (Author, Title, Keywords, Description) using [ExifTool](https://exiftool.org/) when adding new books.
*   **📂 Open Books**: Launch books with your system's default application directly from the TUI.
*   **⚙️ Configuration**: Manage essential application paths (library, database, logs, ExifTool) via an in-app settings screen or by directly editing `config.json`.
*   **✨ Rich TUI**: Modern and responsive terminal interface powered by Textual, with interactive forms and tables.
*   **📝 Logging**: Application events and errors are logged for easier debugging.

---

## 📦 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/salvodif/TomeTrove.git
    cd TomeTrove
    ```

2.  **(Recommended) Create and activate a Python virtual environment:**
    ```bash
    python -m venv venv
    
    # On Linux / macOS
    source venv/bin/activate
     
    # On Windows (Command Prompt / PowerShell)
    .\venv\Scripts\activate 
    ```

3.  **Install Python dependencies:**
    Ensure you have a `requirements.txt` file with the following content:
    ```txt
    textual
    tinydb
    textual-autocomplete
    ```
    Then run:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install ExifTool (External Dependency for Metadata):**
    TomeTrove uses ExifTool to update file metadata (e.g., author, title in PDFs).
    *   Download from the [ExifTool Official Website](https://exiftool.org/).
    *   Follow their installation instructions for your operating system.
    *   Make sure its path is correctly configured in `config.json` or via the in-app settings.

---

## ⚙️ Configuration

Before the first run, or to customize paths, create/edit the `config.json` file in the same directory as `main.py`.
An example template can be found in the file `config.json.template`.
Here's an example structure (adjust paths for your system):

```json
{
  "paths": {
    "tinydb_file": "library.json",
    "library_path": "/path/with/yours/pdfs",
    "upload_dir_path": "/default/path/where/look/for/pdf/to/upload",
    "exiftool_path": "/exiftool/path/exiftool.exe",
    "log_dir": "/logs/path" 
  }
}
```
*   `tinydb_file`: Name of the TinyDB database file (e.g., `library.json`). It will be created inside your `library_path`.
*   `library_path`: The root directory where your book files will be organized (by author) and stored. **This is a critical path.**
*   `upload_dir_path`: Default directory the file browser will open to when adding new books.
*   `exiftool_path`: Full path to the ExifTool executable. **Required if you want file metadata to be updated.** For Windows, this would end in `.exe`. For Linux/macOS, it's usually just `exiftool` if it's in your system's PATH, or the full path to the executable.
*   `log_dir`: Directory where log files will be stored (can be relative to the script or an absolute path).

You can also configure these paths through the **Settings screen (`Ctrl+S`)** within the application after the first run.

---

## 💻 Usage

1.  Ensure you have followed the Installation and Configuration steps.
2.  Navigate to the `TomeTrove` project directory in your terminal (where `main.py` is located).
3.  Run the application:
    ```bash
    python main.py
    ```

The application will start, displaying your book library (empty at first). Use the keybindings below to navigate and manage your books.

### ➤ Keybindings (Main Screen)

| Key         | Action                        | Description                                                                           |
|-------------|-------------------------------|---------------------------------------------------------------------------------------|
| `Ctrl+A`    | Add Book                      | Opens the screen to add a new book to the library.                                    |
| `E`         | Edit Book                     | Opens the selected book's details for editing.                                        |
| `Ctrl+F`    | Search                        | Opens a prompt to search books by title or author.                                    |
| `F5`        | Reset Search                  | Clears the current search and displays all books.                                     |
| `Ctrl+O`    | Open Book                     | Opens the selected book file with the default app.                                    |
| `Ctrl+R`    | Reverse Sort / Sort by Column | Reverses the current sort order. If a column header is focused, sorts by that column. |
| `Ctrl+S`    | Settings                      | Opens the application settings screen.                                                |
| `Arrow Keys`| Navigate Table                | Move selection up/down in the book list.                                              |
| `Escape`    | Back / Cancel                 | Closes modals, forms, or navigates back.                                              |

<details>
<summary>💡 Example Workflow: Adding a Book</summary>

1.  Press `Ctrl+A`.
2.  The "Add Book" screen appears.
3.  Use the directory tree to navigate to and select your book file (PDF, EPUB, etc.).
4.  The selected file path will appear.
5.  Fill in the Title, Author (autocomplete available), Tags (autocomplete available), and other optional fields.
6.  Click the "Salva" (Save) button.
7.  The book is copied to your `library_path` (organized by author), metadata is (optionally) updated using ExifTool, and it's added to the database and main table.

</details>

---

## 🛠️ Key Components & Technology

*   **[Textual](https://github.com/Textualize/textual)**: Core framework for the Terminal User Interface (TUI).
*   **[TinyDB](https://tinydb.readthedocs.io/)**: A lightweight, document-oriented database used for storing book metadata in a JSON file.
*   **[textual-autocomplete](https://github.com/darrenburns/textual-autocomplete)**: Provides autocompletion for author and tag input fields.
*   **[ExifTool](https://exiftool.org/)**: An external command-line application for reading, writing, and editing meta information in a wide variety of files (used here for PDF/EPUB/DOCX metadata).
*   **Python `pathlib`**: For robust and cross-platform path manipulation.
*   **Python `subprocess`**: For interacting with ExifTool.
*   **Python `logging`**: For application logging.

---

## 🛠️ Auxiliary Scripts (in `tools/` directory)

The `tools/` directory contains several utility scripts to help manage your TomeTrove library and data.

### ➤ `import_calibre_to_tinydb.py`

This script is designed to import your existing book library from a Calibre export into TomeTrove's TinyDB database.

**Functionality:**
*   Reads a JSON file exported from Calibre (containing book metadata).
*   Copies book files (PDFs and other formats) from their original Calibre locations to the TomeTrove `library_path`, organizing them into author-specific subdirectories.
*   Attempts to update PDF metadata (title, author, tags) using ExifTool.
*   Creates corresponding entries in the TomeTrove `library.json` database.
*   Logs the import process, including any errors encountered.

**Usage:**
1.  **Export your Calibre library to JSON:**
    *   You can use Calibre's `calibredb list` command-line tool. Refer to the official Calibre documentation for detailed instructions: [calibredb list documentation](https://manual.calibre-ebook.com/generated/en/calibredb.html#list).
    *   A typical command might look like this (run from your terminal/command prompt):
        ```bash
        calibredb list --for-machine --fields authors,title,formats,tags,series,series_index,comments,last_modified > calibre_books.json
        ```
        This command exports the specified fields for all books into a JSON file named `calibre_books.json`. Make sure to include at least `authors`, `title`, and `formats`.
2.  **Place `calibre_books.json`:** Put the exported JSON file in the same directory as `import_calibre_to_tinydb.py` or specify its path when running the script (currently, the script defaults to looking for `calibre_books.json` in its own directory).
3.  **Configure Paths:** Ensure your `config.json` for TomeTrove has the correct `library_path` (where books will be copied) and `exiftool_path`.
4.  **Run the script:**
    ```bash
    python tools/import_calibre_to_tinydb.py
    ```
    *   The script will process the JSON, copy files, and create/update your `library.json`.
    *   Check the generated log file in the `logs/` directory (as specified in `config.json` or the script's default) for details and any errors.

**Important Notes for `import_calibre_to_tinydb.py`:**
*   The script assumes that the paths to your book files listed in the Calibre JSON export are accessible from where you run the script.
*   It tries to handle different text encodings for the JSON file but UTF-8 is preferred.
*   PDFs for which metadata update via ExifTool fails will be copied to a `02 - PDF no metadata updated` directory within your `library_path`.
*   Non-PDF files (e.g., EPUB, MOBI) associated with a book are copied to a `01 - non-PDF` directory within your `library_path`.

### ➤ `add_tags_in_db.py`

This utility script allows you to pre-populate or update the `tags` table in your TomeTrove `library.json` database with a predefined set of tags and their associated icons.

**Functionality:**
*   Connects to your `library.json` database.
*   Iterates through a predefined dictionary of tag names and icons.
*   If a tag already exists by name, it updates its icon.
*   If a tag does not exist, it inserts a new tag entry with the name and icon.

**Usage:**
1.  **Modify `tags_data` (Optional):** Open `tools/add_tags_in_db.py` and edit the `tags_data` dictionary if you want to change the default tags or their icons.
2.  **Specify Database Path:** Ensure the line `db = TinyDB('test_library.json')` (or similar) in the script points to your actual `library.json` file, which should be located within your configured `library_path`.
    *   *Recommendation:* It's best to modify this script to read the `library_path` and `tinydb_file` from your main `config.json` for consistency, rather than hardcoding `test_library.json`.
3.  **Run the script:**
    ```bash
    python tools/add_tags_in_db.py
    ```
    The script will print messages indicating which tags were added or updated.

### ➤ `checkpdf.py`

This script helps verify the integrity of your TomeTrove library by checking if the book files referenced in your `library.json` database actually exist at their expected locations within your `library_path`.

**Functionality:**
*   Reads your main `config.json` to get the `library_path` and `tinydb_file` path.
*   Iterates through all book entries in your `library.json`.
*   For each book, it constructs the expected file path (based on author and filename).
*   Checks if the file exists at that path.
*   Reports any missing files or entries with missing filename/author information.
*   Uses `colorama` for colored terminal output to highlight issues.

**Usage:**
1.  Ensure your main `config.json` is correctly configured with the paths to your library and database.
2.  Run the script from the root directory of your TomeTrove project:
    ```bash
    python tools/checkpdf.py
    ```
    The script will output a summary of any problems found.

### ➤ `count_non_pdf.ps1` (PowerShell Script)

This is a PowerShell script designed to count the number of non-PDF files present within a specified import/upload directory. It's useful for getting a quick overview before or after an import process if you're primarily interested in PDF files.

**Functionality:**
*   Prompts the user to enter the path to the directory to scan (defaults to the current directory if none is provided).
*   Recursively searches the specified directory and its subdirectories.
*   Counts all files that do *not* have a `.pdf` extension.
*   Outputs the total count of non-PDF files found.

**Usage (Windows PowerShell):**
1.  Open PowerShell.
2.  Navigate to the `tools/` directory:
    ```powershell
    cd path/to/TomeTrove/tools
    ```
3.  Run the script:
    ```powershell
    .\count_non_pdf.ps1
    ```
4.  When prompted, enter the path to the directory you want to analyze, or press Enter to scan the current directory (`tools/`).

---

## ⚠️ Limitations

*   **Metadata Updates**: File metadata updating (e.g., for PDFs) relies entirely on a correctly installed and configured ExifTool. If ExifTool is not found, misconfigured, or encounters an error with a specific file, metadata won't be updated (though the book will still be added to the TomeTrove library).
*   **File Organization**: Books are organized into subdirectories by author name within the main `library_path`. Renaming authors directly in the database will not automatically move or rename the corresponding physical files/folders.
*   **Error Handling**: While basic error handling and logging are implemented, complex edge cases or file corruption issues might not always be gracefully handled.
*   **No Cloud Sync**: TomeTrove is a local application. For cloud synchronization of your library, you would need to manage the `library_path` directory (containing your books and `library.json`) and `config.json` using a third-party service like Dropbox, OneDrive, Nextcloud, Syncthing, etc.
*   **Single User**: Designed as a single-user local application.
*   **Scalability**: For extremely large libraries (tens of thousands of books), TinyDB performance might eventually degrade.

---

## 🙌 Contributing

Contributions, issues, and feature requests are welcome!
Please feel free to:
*   Open an issue on the [TomeTrove GitHub repository](https://github.com/salvodif/TomeTrove/issues).
*   Fork the project and submit a pull request for bug fixes or new features.

When contributing, please try to:
*   Follow the existing code style.
*   Add comments to your code where necessary.
*   Test your changes thoroughly.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <em>Happy reading and organizing your digital tomes! 📚</em>
</div>