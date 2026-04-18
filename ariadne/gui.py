"""
Ariadne GUI — Tkinter-based graphical user interface prototype.

This is a simple GUI for ingesting files and searching the memory system.
A full-featured PyQt6 GUI is planned for P6.

Run with: python -m ariadne.gui
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from pathlib import Path

from ariadne import __version__
from ariadne.memory import VectorStore
from ariadne.ingest import (
    MarkdownIngestor,
    WordIngestor,
    PPTIngestor,
    PDFIngestor,
    TxtIngestor,
    ConversationIngestor,
    MindMapIngestor,
    CodeIngestor,
    ExcelIngestor,
    CsvIngestor,
)

INGESTORS = {
    ".md": MarkdownIngestor,
    ".docx": WordIngestor,
    ".pptx": PPTIngestor,
    ".pdf": PDFIngestor,
    ".txt": TxtIngestor,
    ".mm": MindMapIngestor,
    ".xmind": MindMapIngestor,
    ".py": CodeIngestor,
    ".java": CodeIngestor,
    ".cpp": CodeIngestor,
    ".c": CodeIngestor,
    ".js": CodeIngestor,
    ".ts": CodeIngestor,
    ".xlsx": ExcelIngestor,
    ".xls": ExcelIngestor,
    ".csv": CsvIngestor,
}


class AriadneGUI:
    """Main GUI application."""

    def __init__(self, root):
        self.root = root
        self.root.title(f"Ariadne — Knowledge Memory v{__version__}")
        self.root.geometry("900x700")

        self.store = VectorStore()
        self.selected_files = []

        self._create_widgets()
        self._update_stats()

    def _create_widgets(self):
        """Create all GUI widgets."""
        # Header
        header = ttk.Frame(self.root, padding=10)
        header.pack(fill=tk.X)

        ttk.Label(
            header,
            text="Ariadne — Cross-Source AI Memory",
            font=("Arial", 16, "bold")
        ).pack(side=tk.LEFT)

        ttk.Label(
            header,
            text=f"v{__version__}",
            foreground="gray"
        ).pack(side=tk.LEFT, padx=5)

        # Main content area
        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel: File ingestion
        left_frame = ttk.LabelFrame(main, text="Ingest Files", padding=10)
        main.add(left_frame, weight=1)

        # File list
        self.file_listbox = tk.Listbox(left_frame, height=10, selectmode=tk.EXTENDED)
        self.file_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Add Files", command=self._add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Add Folder", command=self._add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Clear", command=self._clear_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Ingest", command=self._ingest_files, style="Accent.TButton").pack(side=tk.RIGHT, padx=2)

        # Progress
        self.progress = ttk.Progressbar(left_frame, mode="determinate")
        self.progress.pack(fill=tk.X, pady=5)

        # Stats
        self.stats_label = ttk.Label(left_frame, text="Documents: 0", foreground="gray")
        self.stats_label.pack(anchor=tk.W)

        # Right panel: Search
        right_frame = ttk.LabelFrame(main, text="Search Memory", padding=10)
        main.add(right_frame, weight=2)

        # Search entry
        search_frame = ttk.Frame(right_frame)
        search_frame.pack(fill=tk.X, pady=5)

        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<Return>", lambda e: self._do_search())

        ttk.Button(search_frame, text="Search", command=self._do_search).pack(side=tk.LEFT, padx=5)

        # Results
        ttk.Label(right_frame, text="Results:", font=("Arial", 10, "bold")).pack(anchor=tk.W)

        self.results_text = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            height=20,
            font=("Consolas", 9)
        )
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Bottom: Status bar
        self.status_label = ttk.Label(
            self.root,
            text="Ready",
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def _add_files(self):
        """Open file dialog to add files."""
        files = filedialog.askopenfilenames(
            title="Select files to ingest",
            filetypes=[
                ("All supported", "*.md *.docx *.pptx *.pdf *.txt *.mm *.xmind *.py *.java *.cpp *.c *.js *.ts *.xlsx *.xls *.csv"),
                ("Documents", "*.md *.docx *.pdf *.txt"),
                ("Spreadsheets", "*.xlsx *.xls *.csv"),
                ("Code", "*.py *.java *.cpp *.c *.js *.ts"),
                ("All files", "*.*")
            ]
        )
        for f in files:
            if f not in self.selected_files:
                self.selected_files.append(f)
                self.file_listbox.insert(tk.END, Path(f).name)

    def _add_folder(self):
        """Open folder dialog to add all supported files."""
        folder = filedialog.askdirectory(title="Select folder to ingest")
        if folder:
            folder_path = Path(folder)
            for ext in INGESTORS:
                for file_path in folder_path.rglob(f"*{ext}"):
                    if str(file_path) not in self.selected_files:
                        self.selected_files.append(str(file_path))
                        self.file_listbox.insert(tk.END, file_path.name)

    def _clear_files(self):
        """Clear the file list."""
        self.selected_files.clear()
        self.file_listbox.delete(0, tk.END)

    def _ingest_files(self):
        """Ingest files in a background thread."""
        if not self.selected_files:
            messagebox.showwarning("No files", "Please add files to ingest first.")
            return

        self.status_label.config(text="Ingesting files...")
        self.progress["maximum"] = len(self.selected_files)
        self.progress["value"] = 0

        def worker():
            count = 0
            for i, file_path in enumerate(self.selected_files):
                try:
                    path = Path(file_path)
                    suffix = path.suffix.lower()
                    if suffix in INGESTORS:
                        ingestor_cls = INGESTORS[suffix]
                        ingestor = ingestor_cls()
                        docs = ingestor.ingest(file_path)
                        if docs:
                            self.store.add(docs)
                            count += len(docs)

                    # Update progress
                    self.progress["value"] = i + 1
                    self.root.after(0, lambda p=i+1: self.progress.config(value=p))
                except Exception as e:
                    print(f"Error ingesting {file_path}: {e}")

            self.root.after(0, lambda: self._ingest_complete(count))

        threading.Thread(target=worker, daemon=True).start()

    def _ingest_complete(self, count):
        """Called after ingestion is complete."""
        self.status_label.config(text=f"Ingested {count} documents from {len(self.selected_files)} files")
        self.progress["value"] = 0
        self._update_stats()
        messagebox.showinfo("Complete", f"Successfully ingested {count} documents!")

    def _update_stats(self):
        """Update document statistics."""
        try:
            count = self.store.count()
            self.stats_label.config(text=f"Documents indexed: {count}")
        except Exception as e:
            self.stats_label.config(text=f"Error: {e}")

    def _do_search(self):
        """Perform search."""
        query = self.search_entry.get().strip()
        if not query:
            return

        self.status_label.config(text=f"Searching: {query}")
        self.results_text.delete(1.0, tk.END)

        try:
            results = self.store.search(query, top_k=10)

            if not results:
                self.results_text.insert(tk.END, "No results found.\n")
                return

            self.results_text.insert(tk.END, f"Found {len(results)} results:\n\n")

            for i, (doc, score) in enumerate(results, 1):
                self.results_text.insert(tk.END, f"{'='*60}\n")
                self.results_text.insert(tk.END, f"[{i}] Score: {score:.4f}\n")
                self.results_text.insert(tk.END, f"Source: {doc.source_path}\n")
                self.results_text.insert(tk.END, f"Type: {doc.source_type.value}\n")
                self.results_text.insert(tk.END, f"\n{doc.content[:500]}")
                if len(doc.content) > 500:
                    self.results_text.insert(tk.END, "...")
                self.results_text.insert(tk.END, f"\n\n")

            self.status_label.config(text=f"Found {len(results)} results")

        except Exception as e:
            self.results_text.insert(tk.END, f"Error: {e}\n")
            self.status_label.config(text="Search error")


def main():
    """Launch the GUI."""
    root = tk.Tk()
    app = AriadneGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
