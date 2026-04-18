"""
Ariadne GUI — Tkinter-based graphical user interface.

Complete GUI implementation that mirrors all CLI functionality:
- Memory system management (create, rename, delete, merge)
- File ingestion with progress
- Semantic search
- Advanced features (summary, graph, export)
- LLM configuration
- Multi-language support (7 UN languages)

Run with: python -m ariadne.gui
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import webbrowser
from pathlib import Path
from typing import List, Optional
import tempfile

from ariadne import __version__
from ariadne.memory import MemoryManager, get_manager
from ariadne.ingest import (
    MarkdownIngestor, WordIngestor, PPTIngestor, PDFIngestor,
    TxtIngestor, ConversationIngestor, MindMapIngestor,
    CodeIngestor, ExcelIngestor, CsvIngestor,
)
from ariadne.config import (
    AriadneConfig,
    get_config,
    reload_config,
)
from ariadne.i18n import (
    init_locale,
    get_locale,
    available_locales,
    get_locale_display,
    set_locale,
)
from ariadne.advanced import Summarizer, GraphVisualizer, Exporter
from ariadne.graph.storage import GraphStorage

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

# Multi-language labels
LABELS = {
    "en": {
        "file": "File", "add_files": "Add Files...", "add_folder": "Add Folder...",
        "exit": "Exit", "memory": "Memory Systems", "new": "New", "rename": "Rename",
        "delete": "Delete", "merge": "Merge", "clear": "Clear", "view_all": "View All",
        "settings": "Settings", "language": "Language", "llm_config": "LLM Config",
        "ingest": "Ingest", "search": "Search", "info": "Info", "advanced": "Advanced",
        "refresh": "Refresh", "ingest_all": "Ingest All", "remove": "Remove Selected",
        "clear_all": "Clear All", "search_query": "Search Query:", "results": "Search Results:",
        "system_info": "System Information", "docs": "Documents:", "created": "Created:",
        "updated": "Updated:", "top_k": "Results (k):", "show_metadata": "Show metadata",
        "verbose": "Verbose", "recursive": "Recursive", "summary": "Summary", "graph": "Knowledge Graph",
        "export": "Export", "test_llm": "Test LLM", "current_system": "Current System:",
        "provider": "Provider:", "model": "Model:", "api_key": "API Key:", "test": "Test",
        "save": "Save", "cancel": "Cancel", "output_lang": "Output Language:",
        "format": "Format:", "export_btn": "Export", "graph_view": "View Graph",
        "summarize_btn": "Summarize", "status_ready": "Ready", "no_llm": "No LLM configured",
        "test_success": "LLM connection successful!", "test_fail": "LLM connection failed",
    },
    "zh_CN": {
        "file": "文件", "add_files": "添加文件...", "add_folder": "添加文件夹...",
        "exit": "退出", "memory": "记忆系统", "new": "新建", "rename": "重命名",
        "delete": "删除", "merge": "合并", "clear": "清空", "view_all": "查看全部",
        "settings": "设置", "language": "语言", "llm_config": "LLM 配置",
        "ingest": "摄入", "search": "搜索", "info": "信息", "advanced": "高级",
        "refresh": "刷新", "ingest_all": "摄入全部", "remove": "移除选中",
        "clear_all": "清空列表", "search_query": "搜索查询:", "results": "搜索结果:",
        "system_info": "系统信息", "docs": "文档:", "created": "创建时间:",
        "updated": "更新时间:", "top_k": "结果数:", "show_metadata": "显示元数据",
        "verbose": "详细输出", "recursive": "递归", "summary": "摘要", "graph": "知识图谱",
        "export": "导出", "test_llm": "测试 LLM", "current_system": "当前系统:",
        "provider": "提供商:", "model": "模型:", "api_key": "API 密钥:", "test": "测试",
        "save": "保存", "cancel": "取消", "output_lang": "输出语言:",
        "format": "格式:", "export_btn": "导出", "graph_view": "查看图谱",
        "summarize_btn": "生成摘要", "status_ready": "就绪", "no_llm": "未配置 LLM",
        "test_success": "LLM 连接成功!", "test_fail": "LLM 连接失败",
    },
    "zh_TW": {
        "file": "檔案", "add_files": "添加檔案...", "add_folder": "添加資料夾...",
        "exit": "退出", "memory": "記憶系統", "new": "新建", "rename": "重新命名",
        "delete": "刪除", "merge": "合併", "clear": "清除", "view_all": "查看全部",
        "settings": "設定", "language": "語言", "llm_config": "LLM 設定",
        "ingest": "攝入", "search": "搜尋", "info": "資訊", "advanced": "進階",
        "refresh": "刷新", "ingest_all": "攝入全部", "remove": "移除選中",
        "clear_all": "清除列表", "search_query": "搜尋查詢:", "results": "搜尋結果:",
        "system_info": "系統資訊", "docs": "文件:", "created": "創建時間:",
        "updated": "更新時間:", "top_k": "結果數:", "show_metadata": "顯示元資料",
        "verbose": "詳細輸出", "recursive": "遞迴", "summary": "摘要", "graph": "知識圖譜",
        "export": "匯出", "test_llm": "測試 LLM", "current_system": "當前系統:",
        "provider": "提供商:", "model": "模型:", "api_key": "API 密鑰:", "test": "測試",
        "save": "儲存", "cancel": "取消", "output_lang": "輸出語言:",
        "format": "格式:", "export_btn": "匯出", "graph_view": "查看圖譜",
        "summarize_btn": "生成摘要", "status_ready": "就緒", "no_llm": "未設定 LLM",
        "test_success": "LLM 連線成功!", "test_fail": "LLM 連線失敗",
    },
    "fr": {
        "file": "Fichier", "add_files": "Ajouter des fichiers...", "add_folder": "Ajouter un dossier...",
        "exit": "Quitter", "memory": "Systemes de memoire", "new": "Nouveau", "rename": "Renommer",
        "delete": "Supprimer", "merge": "Fusionner", "clear": "Effacer", "view_all": "Voir tout",
        "settings": "Parametres", "language": "Langue", "llm_config": "Config LLM",
        "ingest": "Ingestion", "search": "Recherche", "info": "Info", "advanced": "Avance",
        "refresh": "Actualiser", "ingest_all": "Ingerer tout", "remove": "Supprimer selection",
        "clear_all": "Effacer tout", "search_query": "Requete:", "results": "Resultats:",
        "system_info": "Informations systeme", "docs": "Documents:", "created": "Cree le:",
        "updated": "Mis a jour:", "top_k": "Resultats (k):", "show_metadata": "Afficher metadonnees",
        "verbose": "Detaille", "recursive": "Recursif", "summary": "Resume", "graph": "Graphe de connaissances",
        "export": "Exporter", "test_llm": "Tester LLM", "current_system": "Systeme actuel:",
        "provider": "Fournisseur:", "model": "Modele:", "api_key": "Cle API:", "test": "Tester",
        "save": "Enregistrer", "cancel": "Annuler", "output_lang": "Langue de sortie:",
        "format": "Format:", "export_btn": "Exporter", "graph_view": "Voir le graphe",
        "summarize_btn": "Resumer", "status_ready": "Pret", "no_llm": "LLM non configure",
        "test_success": "Connexion LLM reussie!", "test_fail": "Connexion LLM echouee",
    },
}


def get_label(key: str) -> str:
    """Get localized label."""
    locale = get_locale()
    labels = LABELS.get(locale, LABELS["en"])
    return labels.get(key, key)


class LanguageDialog(tk.Toplevel):
    """Dialog for selecting UI language."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Select Language / 选择语言")
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self._create_widgets()
        self._center_window()
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Select Interface Language:").pack(pady=10)
        
        self.lang_var = tk.StringVar(value=get_locale())
        locales = available_locales()
        
        for code, name in locales:
            ttk.Radiobutton(
                frame, text=name, variable=self.lang_var, value=code
            ).pack(anchor=tk.W, padx=20)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT)
    
    def _center_window(self):
        self.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - self.winfo_width()) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _on_ok(self):
        self.result = self.lang_var.get()
        self.destroy()


class LLMConfigDialog(tk.Toplevel):
    """Dialog for configuring LLM provider."""
    
    def __init__(self, parent, config: AriadneConfig):
        super().__init__(parent)
        self.title("LLM Configuration")
        self.transient(parent)
        self.grab_set()
        
        self.config = config
        self.result = None
        self._create_widgets()
        self._load_config()
        self._center_window()
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Provider
        ttk.Label(frame, text="Provider:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.provider_var = tk.StringVar()
        providers = AriadneConfig.SUPPORTED_PROVIDERS
        self.provider_combo = ttk.Combobox(
            frame, textvariable=self.provider_var, 
            values=[p[0] for p in providers], state="readonly", width=20
        )
        self.provider_combo.grid(row=0, column=1, pady=5)
        
        # Model
        ttk.Label(frame, text="Model:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.model_entry = ttk.Entry(frame, width=30)
        self.model_entry.grid(row=1, column=1, pady=5)
        
        # API Key
        ttk.Label(frame, text="API Key:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.apikey_entry = ttk.Entry(frame, width=30, show="*")
        self.apikey_entry.grid(row=2, column=1, pady=5)
        
        # Temperature
        ttk.Label(frame, text="Temperature:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.temp_var = tk.DoubleVar(value=0.7)
        ttk.Spinbox(frame, from_=0.0, to=2.0, increment=0.1, 
                   textvariable=self.temp_var, width=18).grid(row=3, column=1, pady=5)
        
        # Output Language
        ttk.Label(frame, text="Output Language:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.output_lang_var = tk.StringVar()
        locales = available_locales()
        ttk.Combobox(
            frame, textvariable=self.output_lang_var,
            values=[code for code, _ in locales], state="readonly", width=18
        ).grid(row=4, column=1, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Test", command=self._on_test).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT)
        
        # Status
        self.status_label = ttk.Label(frame, text="", foreground="blue")
        self.status_label.grid(row=6, column=0, columnspan=2)
    
    def _load_config(self):
        llm_info = self.config.get_llm_info()
        self.provider_var.set(llm_info.get("provider", "deepseek"))
        self.model_entry.insert(0, llm_info.get("model", ""))
        self.temp_var.set(llm_info.get("temperature", 0.7))
        self.output_lang_var.set(self.config.get_output_language())
    
    def _center_window(self):
        self.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - self.winfo_width()) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _on_test(self):
        provider = self.provider_var.get()
        model = self.model_entry.get()
        api_key = self.apikey_entry.get()
        
        if not api_key:
            self.status_label.config(text="Please enter API key", foreground="red")
            return
        
        # Temporarily set for testing
        self.config.set("llm.provider", provider)
        self.config.set("llm.model", model)
        self.config.set("llm.api_key", api_key)
        
        success, msg = self.config.test_llm()
        if success:
            self.status_label.config(text=f"OK: {msg}", foreground="green")
        else:
            self.status_label.config(text=f"Failed: {msg}", foreground="red")
    
    def _on_save(self):
        self.config.set("llm.provider", self.provider_var.get())
        self.config.set("llm.model", self.model_entry.get())
        self.config.set("llm.api_key", self.apikey_entry.get())
        self.config.set("llm.temperature", self.temp_var.get())
        self.config.set("locale.output_language", self.output_lang_var.get())
        self.config.save_user()
        
        self.result = True
        self.destroy()


class MemorySystemDialog(tk.Toplevel):
    """Dialog for memory system operations."""
    
    def __init__(self, parent, title: str, manager: MemoryManager,
                 operation: str = "create", current_name: str = ""):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        
        self.manager = manager
        self.operation = operation
        self.current_name = current_name
        self.result = None
        
        self._create_widgets()
        self._center_window()
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5)
        
        if self.operation == "rename":
            self.name_entry.insert(0, self.current_name)
        
        if self.operation == "create":
            ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky=tk.W, pady=5)
            self.desc_entry = ttk.Entry(frame, width=30)
            self.desc_entry.grid(row=1, column=1, pady=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT)
    
    def _center_window(self):
        self.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - self.winfo_width()) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _on_ok(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Error", "Name cannot be empty")
            return
        
        try:
            if self.operation == "create":
                desc = self.desc_entry.get().strip() if hasattr(self, 'desc_entry') else ""
                self.manager.create(name, desc)
            elif self.operation == "rename":
                self.manager.rename(self.current_name, name)
            
            self.result = name
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))


class MergeDialog(tk.Toplevel):
    """Dialog for merging memory systems."""
    
    def __init__(self, parent, manager: MemoryManager):
        super().__init__(parent)
        self.title("Merge Memory Systems")
        self.transient(parent)
        self.grab_set()
        
        self.manager = manager
        self.result = None
        
        self._create_widgets()
        self._center_window()
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="New System Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5)
        
        ttk.Label(frame, text="Select systems to merge:").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        self.listbox = tk.Listbox(frame, selectmode=tk.EXTENDED, height=10, width=40)
        self.listbox.grid(row=2, column=0, columnspan=2, pady=5)
        
        for name in self.manager._manifest.keys():
            if name != "default":
                self.listbox.insert(tk.END, name)
        
        self.delete_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Delete source systems after merge",
                       variable=self.delete_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Merge", command=self._on_merge).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT)
    
    def _center_window(self):
        self.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - self.winfo_width()) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _on_merge(self):
        new_name = self.name_entry.get().strip()
        if not new_name:
            messagebox.showwarning("Error", "Name cannot be empty")
            return
        
        selected = [self.listbox.get(i) for i in self.listbox.curselection()]
        if not selected:
            messagebox.showwarning("Error", "Please select at least one system")
            return
        
        try:
            self.manager.merge(selected, new_name, delete_sources=self.delete_var.get())
            self.result = new_name
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))


class AriadneGUI:
    """Main GUI application with full CLI functionality and multi-language support."""
    
    def __init__(self, root):
        self.root = root
        self.root.title(f"Ariadne — Cross-Source AI Memory v{__version__}")
        self.root.geometry("1100x800")
        
        # Initialize managers
        init_locale()
        self.manager = get_manager()
        self.config = get_config()
        self.current_system = self.manager.DEFAULT_COLLECTION
        
        self.selected_files = []
        
        self._create_widgets()
        self._update_memory_list()
        self._update_stats()
        self._update_info()
    
    def _create_widgets(self):
        # Menu bar
        self._create_menu()
        
        # Header
        header = ttk.Frame(self.root, padding=10)
        header.pack(fill=tk.X)
        
        ttk.Label(header, text="Ariadne", font=("Arial", 18, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text=f"v{__version__}", foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # Language indicator
        self.lang_label = ttk.Label(header, text=f"Lang: {get_locale()}", foreground="blue")
        self.lang_label.pack(side=tk.RIGHT, padx=10)
        
        # Toolbar
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(fill=tk.X)
        
        ttk.Label(toolbar, text=get_label("current_system")).pack(side=tk.LEFT, padx=5)
        self.memory_var = tk.StringVar()
        self.memory_combo = ttk.Combobox(toolbar, textvariable=self.memory_var, state="readonly", width=20)
        self.memory_combo.pack(side=tk.LEFT, padx=5)
        self.memory_combo.bind("<<ComboboxSelected>>", self._on_memory_changed)
        
        ttk.Button(toolbar, text=get_label("refresh"), command=self._refresh).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=get_label("new"), command=self._create_memory).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=get_label("rename"), command=self._rename_memory).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=get_label("delete"), command=self._delete_memory).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=get_label("merge"), command=self._merge_memory).pack(side=tk.LEFT, padx=2)
        
        # Notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Ingest
        self._create_ingest_tab(notebook)
        notebook.add(self.ingest_frame, text=f"{get_label('ingest')} / 摄入")
        
        # Tab 2: Search
        self._create_search_tab(notebook)
        notebook.add(self.search_frame, text=f"{get_label('search')} / 搜索")
        
        # Tab 3: Info
        self._create_info_tab(notebook)
        notebook.add(self.info_frame, text=f"{get_label('info')} / 信息")
        
        # Tab 4: Advanced
        self._create_advanced_tab(notebook)
        notebook.add(self.advanced_frame, text=f"{get_label('advanced')} / 高级")
        
        # Status bar
        self.status_label = ttk.Label(
            self.root, text=get_label("status_ready"), relief=tk.SUNKEN, anchor=tk.W
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=get_label("file"), menu=file_menu)
        file_menu.add_command(label=get_label("add_files"), command=self._add_files)
        file_menu.add_command(label=get_label("add_folder"), command=self._add_folder)
        file_menu.add_separator()
        file_menu.add_command(label=get_label("exit"), command=self.root.quit)
        
        # Memory menu
        memory_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=get_label("memory"), menu=memory_menu)
        memory_menu.add_command(label=get_label("new"), command=self._create_memory)
        memory_menu.add_command(label=get_label("rename"), command=self._rename_memory)
        memory_menu.add_command(label=get_label("delete"), command=self._delete_memory)
        memory_menu.add_command(label=get_label("merge"), command=self._merge_memory)
        memory_menu.add_separator()
        memory_menu.add_command(label=get_label("clear"), command=self._clear_current)
        memory_menu.add_command(label=get_label("view_all"), command=self._view_all_systems)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=get_label("settings"), menu=settings_menu)
        settings_menu.add_command(label=get_label("language"), command=self._change_language)
        settings_menu.add_command(label=get_label("llm_config"), command=self._open_llm_config)
    
    def _create_ingest_tab(self, notebook):
        self.ingest_frame = ttk.Frame(notebook, padding=10)
        
        ttk.Label(self.ingest_frame, text="Files to Ingest:", 
                 font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        list_frame = ttk.Frame(self.ingest_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.file_listbox = tk.Listbox(list_frame, height=12, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=scrollbar.set)
        
        btn_frame = ttk.Frame(self.ingest_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text=get_label("add_files"), command=self._add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=get_label("add_folder"), command=self._add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=get_label("remove"), command=self._remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=get_label("clear_all"), command=self._clear_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=get_label("ingest_all"), command=self._ingest_files,
                  style="Accent.TButton").pack(side=tk.RIGHT, padx=2)
        
        options_frame = ttk.LabelFrame(self.ingest_frame, text="Options", padding=5)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text=get_label("recursive"),
                       variable=self.recursive_var).pack(side=tk.LEFT, padx=10)
        
        self.verbose_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text=get_label("verbose"),
                       variable=self.verbose_var).pack(side=tk.LEFT, padx=10)
        
        self.progress = ttk.Progressbar(self.ingest_frame, mode="determinate")
        self.progress.pack(fill=tk.X, pady=5)
        
        self.ingest_stats_label = ttk.Label(self.ingest_frame, text="", foreground="gray")
        self.ingest_stats_label.pack(anchor=tk.W)
    
    def _create_search_tab(self, notebook):
        self.search_frame = ttk.Frame(notebook, padding=10)
        
        search_frame = ttk.Frame(self.search_frame)
        search_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_frame, text=get_label("search_query")).pack(side=tk.LEFT, padx=5)
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<Return>", lambda e: self._do_search())
        
        ttk.Button(search_frame, text=get_label("search"), command=self._do_search).pack(side=tk.LEFT, padx=5)
        
        options_frame = ttk.Frame(self.search_frame)
        options_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(options_frame, text=get_label("top_k")).pack(side=tk.LEFT, padx=5)
        self.top_k_var = tk.IntVar(value=5)
        ttk.Spinbox(options_frame, from_=1, to=50, textvariable=self.top_k_var, width=5).pack(side=tk.LEFT)
        
        self.verbose_search_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text=get_label("show_metadata"),
                       variable=self.verbose_search_var).pack(side=tk.LEFT, padx=10)
        
        ttk.Label(self.search_frame, text=get_label("results"), 
                 font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        self.results_text = tk.Text(self.search_frame, wrap=tk.WORD, font=("Consolas", 9))
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(self.results_text, orient=tk.VERTICAL, command=self.results_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_text.config(yscrollcommand=scrollbar.set)
    
    def _create_info_tab(self, notebook):
        self.info_frame = ttk.Frame(notebook, padding=10)
        
        info_group = ttk.LabelFrame(self.info_frame, text=get_label("system_info"), padding=10)
        info_group.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.info_text = tk.Text(info_group, wrap=tk.WORD, height=15, font=("Consolas", 9))
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.info_text, orient=tk.VERTICAL, command=self.info_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_text.config(yscrollcommand=scrollbar.set)
        
        btn_frame = ttk.Frame(self.info_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text=get_label("refresh"), command=self._update_info).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=get_label("view_all"), command=self._view_all_systems).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=get_label("clear"), command=self._clear_current).pack(side=tk.LEFT, padx=2)
    
    def _create_advanced_tab(self, notebook):
        """Create advanced features tab."""
        self.advanced_frame = ttk.Frame(notebook, padding=10)
        
        # LLM Config section
        config_group = ttk.LabelFrame(self.advanced_frame, text=get_label("llm_config"), padding=10)
        config_group.pack(fill=tk.X, pady=10)
        
        ttk.Button(config_group, text=get_label("llm_config"), 
                  command=self._open_llm_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(config_group, text=get_label("test_llm"), 
                  command=self._test_llm).pack(side=tk.LEFT, padx=5)
        
        self.llm_status_label = ttk.Label(config_group, text="")
        self.llm_status_label.pack(side=tk.LEFT, padx=10)
        
        # Summary section
        summary_group = ttk.LabelFrame(self.advanced_frame, text=get_label("summary"), padding=10)
        summary_group.pack(fill=tk.BOTH, expand=True, pady=10)
        
        ttk.Label(summary_group, text=get_label("search_query")).pack(anchor=tk.W)
        self.summary_search_entry = ttk.Entry(summary_group)
        self.summary_search_entry.pack(fill=tk.X, pady=5)
        
        ttk.Label(summary_group, text=get_label("output_lang")).pack(anchor=tk.W)
        self.output_lang_combo = ttk.Combobox(summary_group, values=[code for code, _ in available_locales()],
                                             state="readonly", width=15)
        self.output_lang_combo.set(self.config.get_output_language())
        self.output_lang_combo.pack(anchor=tk.W, pady=5)
        
        ttk.Button(summary_group, text=get_label("summarize_btn"), 
                  command=self._do_summary).pack(pady=5)
        
        self.summary_text = tk.Text(summary_group, wrap=tk.WORD, height=10, font=("Consolas", 9))
        self.summary_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Export section
        export_group = ttk.LabelFrame(self.advanced_frame, text=get_label("export"), padding=10)
        export_group.pack(fill=tk.X, pady=10)
        
        ttk.Label(export_group, text=get_label("format")).pack(side=tk.LEFT, padx=5)
        self.export_format_var = tk.StringVar(value="html")
        ttk.Combobox(export_group, textvariable=self.export_format_var,
                    values=["markdown", "html", "docx"], state="readonly", width=10).pack(side=tk.LEFT)
        
        ttk.Button(export_group, text=get_label("export_btn"), 
                  command=self._do_export).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(export_group, text=get_label("graph_view"), 
                  command=self._view_graph).pack(side=tk.LEFT, padx=5)
    
    # === Memory System Operations ===
    
    def _update_memory_list(self):
        systems = self.manager.list_systems()
        names = [s.name for s in systems]
        self.memory_combo["values"] = names
        
        if self.current_system in names:
            self.memory_var.set(self.current_system)
        elif names:
            self.memory_var.set(names[0])
            self.current_system = names[0]
    
    def _on_memory_changed(self, event):
        new_system = self.memory_var.get()
        if new_system and new_system != self.current_system:
            self.current_system = new_system
            self._update_stats()
            self._status(f"Switched to: {new_system}")
    
    def _refresh(self):
        self.config = reload_config()
        self._update_memory_list()
        self._update_stats()
        self._update_info()
        self._status(get_label("status_ready"))
    
    def _create_memory(self):
        dialog = MemorySystemDialog(self.root, "New Memory System", self.manager, "create")
        self.root.wait_window(dialog)
        self._update_memory_list()
    
    def _rename_memory(self):
        if self.current_system == self.manager.DEFAULT_COLLECTION:
            messagebox.showwarning("Cannot Rename", "Cannot rename the default memory system")
            return
        
        dialog = MemorySystemDialog(self.root, "Rename Memory System", self.manager,
                                   "rename", self.current_system)
        self.root.wait_window(dialog)
        
        if dialog.result:
            self.current_system = dialog.result
            self._update_memory_list()
    
    def _delete_memory(self):
        if self.current_system == self.manager.DEFAULT_COLLECTION:
            messagebox.showwarning("Cannot Delete", "Cannot delete the default memory system")
            return
        
        if messagebox.askyesno("Confirm Delete",
                             f"Delete memory system '{self.current_system}'?\nThis cannot be undone."):
            try:
                self.manager.delete(self.current_system, confirm=False)
                self.current_system = self.manager.DEFAULT_COLLECTION
                self._update_memory_list()
                self._update_stats()
                messagebox.showinfo("Success", "Memory system deleted")
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    def _merge_memory(self):
        dialog = MergeDialog(self.root, self.manager)
        self.root.wait_window(dialog)
        self._update_memory_list()
    
    def _view_all_systems(self):
        systems = self.manager.list_systems()
        
        text = "="*60 + "\n"
        text += "All Memory Systems\n"
        text += "="*60 + "\n\n"
        
        for s in systems:
            info = self.manager.get_info(s.name)
            count = info.get("document_count", "?") if info else "?"
            text += f"[{s.name}]\n"
            text += f"  Path: {s.path}\n"
            text += f"  Documents: {count}\n"
            text += f"  Created: {s.created_at[:10]}\n"
            if s.description:
                text += f"  Description: {s.description}\n"
            text += "\n"
        
        top = tk.Toplevel(self.root)
        top.title("All Memory Systems")
        top.geometry("600x400")
        
        text_widget = tk.Text(top, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(1.0, text)
        text_widget.config(state=tk.DISABLED)
    
    def _clear_current(self):
        if messagebox.askyesno("Confirm Clear",
                             f"Clear all documents from '{self.current_system}'?\nThis cannot be undone."):
            try:
                self.manager.clear(self.current_system)
                self._update_stats()
                messagebox.showinfo("Success", "Memory system cleared")
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    # === File Operations ===
    
    def _add_files(self):
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
        self._status(f"Added {len(files)} files")
    
    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select folder to ingest")
        if folder:
            folder_path = Path(folder)
            count = 0
            for ext in INGESTORS:
                if self.recursive_var.get():
                    files = folder_path.rglob(f"*{ext}")
                else:
                    files = folder_path.glob(f"*{ext}")
                for file_path in files:
                    if str(file_path) not in self.selected_files:
                        self.selected_files.append(str(file_path))
                        self.file_listbox.insert(tk.END, file_path.name)
                        count += 1
            self._status(f"Added {count} files from folder")
    
    def _remove_selected(self):
        selected = list(self.file_listbox.curselection())
        for i in reversed(selected):
            self.file_listbox.delete(i)
            del self.selected_files[i]
    
    def _clear_files(self):
        self.selected_files.clear()
        self.file_listbox.delete(0, tk.END)
    
    def _ingest_files(self):
        if not self.selected_files:
            messagebox.showwarning("No Files", "Please add files to ingest first.")
            return
        
        self.status_label.config(text="Ingesting files...")
        self.progress["maximum"] = len(self.selected_files)
        self.progress["value"] = 0
        
        def worker():
            docs_added = 0
            errors = []
            
            for i, file_path in enumerate(self.selected_files):
                try:
                    path = Path(file_path)
                    suffix = path.suffix.lower()
                    
                    if suffix in INGESTORS:
                        ingestor_cls = INGESTORS[suffix]
                        ingestor = ingestor_cls()
                        docs = ingestor.ingest(file_path)
                        
                        if docs:
                            store = self.manager.get_store(self.current_system)
                            store.add(docs)
                            docs_added += len(docs)
                    else:
                        if self.verbose_var.get():
                            print(f"SKIP {path.name} (unsupported format)")
                
                except Exception as e:
                    errors.append((file_path, str(e)))
                
                self.root.after(0, lambda p=i+1: self.progress.config(value=p))
            
            self.root.after(0, lambda: self._ingest_complete(docs_added, len(self.selected_files), errors))
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _ingest_complete(self, docs_count, files_count, errors):
        self.status_label.config(text=f"Ingested {docs_count} documents from {files_count} files")
        self.progress["value"] = 0
        self._update_stats()
        
        if errors:
            self.ingest_stats_label.config(text=f"{len(errors)} error(s)", foreground="red")
        else:
            self.ingest_stats_label.config(text="", foreground="gray")
        
        messagebox.showinfo("Complete", f"Successfully ingested {docs_count} documents!")
    
    # === Search Operations ===
    
    def _do_search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        
        self.status_label.config(text=f"Searching: {query}")
        self.results_text.delete(1.0, tk.END)
        
        try:
            store = self.manager.get_store(self.current_system)
            results = store.search(query, top_k=self.top_k_var.get())
            
            if not results:
                self.results_text.insert(tk.END, "No results found.\n")
                self.status_label.config(text="No results")
                return
            
            self.results_text.insert(tk.END, f"Found {len(results)} results:\n\n")
            
            for i, (doc, score) in enumerate(results, 1):
                self.results_text.insert(tk.END, "="*60 + "\n")
                self.results_text.insert(tk.END, f"[{i}] Score: {score:.4f}\n")
                
                if self.verbose_search_var.get():
                    self.results_text.insert(tk.END, f"Source: {doc.source_path}\n")
                    self.results_text.insert(tk.END, f"Type: {doc.source_type.value}\n")
                
                self.results_text.insert(tk.END, f"\n{doc.content[:500]}")
                if len(doc.content) > 500:
                    self.results_text.insert(tk.END, "...")
                self.results_text.insert(tk.END, "\n\n")
            
            self.status_label.config(text=f"Found {len(results)} results")
        
        except Exception as e:
            self.results_text.insert(tk.END, f"Error: {e}\n")
            self.status_label.config(text="Search error")
    
    # === Info Operations ===
    
    def _update_stats(self):
        try:
            store = self.manager.get_store(self.current_system)
            count = store.count()
            self.ingest_stats_label.config(
                text=f"Current: {self.current_system} | {get_label('docs')}: {count}"
            )
        except Exception as e:
            self.ingest_stats_label.config(text=f"Error: {e}")
    
    def _update_info(self):
        self.info_text.delete(1.0, tk.END)
        
        text = f"Ariadne Memory System v{__version__}\n"
        text += "="*50 + "\n\n"
        
        text += f"{get_label('current_system')} {self.current_system}\n"
        text += f"Storage: ChromaDB\n\n"
        
        info = self.manager.get_info(self.current_system)
        if info:
            text += f"{get_label('docs')}: {info.get('document_count', 0)}\n"
            text += f"{get_label('created')}: {info.get('created_at', 'N/A')[:10]}\n"
            text += f"{get_label('updated')}: {info.get('updated_at', 'N/A')[:10]}\n"
        
        text += "\n" + "="*50 + "\n"
        text += "All Memory Systems:\n"
        text += "="*50 + "\n"
        
        systems = self.manager.list_systems()
        for s in systems:
            count = self.manager.get_info(s.name).get("document_count", "?") if self.manager.get_info(s.name) else "?"
            marker = " * " if s.name == self.current_system else "   "
            text += f"{marker}{s.name}: {count} docs\n"
        
        self.info_text.insert(1.0, text)
        self.info_text.config(state=tk.DISABLED)
    
    # === Advanced Operations ===
    
    def _open_llm_config(self):
        dialog = LLMConfigDialog(self.root, self.config)
        self.root.wait_window(dialog)
        if dialog.result:
            self.config = reload_config()
            messagebox.showinfo("Success", "LLM configuration saved")
    
    def _test_llm(self):
        success, msg = self.config.test_llm()
        if success:
            self.llm_status_label.config(text=f"OK: {msg[:50]}", foreground="green")
        else:
            self.llm_status_label.config(text=f"Failed: {msg[:50]}", foreground="red")
    
    def _do_summary(self):
        query = self.summary_search_entry.get().strip()
        output_lang = self.output_lang_combo.get()
        
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, "Generating summary...\n\n")
        
        def worker():
            try:
                store = self.manager.get_store(self.current_system)
                
                if query:
                    results = store.search(query, top_k=10)
                    docs = [doc for doc, _ in results]
                else:
                    self.root.after(0, lambda: self.summary_text.delete(1.0, tk.END))
                    self.root.after(0, lambda: self.summary_text.insert(tk.END, 
                        "Please enter a search query for targeted summary."))
                    return
                
                if not docs:
                    self.root.after(0, lambda: self.summary_text.delete(1.0, tk.END))
                    self.root.after(0, lambda: self.summary_text.insert(tk.END, "No documents found."))
                    return
                
                summarizer = Summarizer(config=self.config)
                result = summarizer.summarize(docs, query=query, language=output_lang)
                
                self.root.after(0, lambda: self.summary_text.delete(1.0, tk.END))
                output = f"=== Summary ({output_lang}) ===\n\n"
                output += f"Summary:\n{result.summary}\n\n"
                output += f"Topics:\n" + "\n".join(f"  - {t}" for t in result.topics) + "\n\n"
                output += f"Keywords:\n" + ", ".join(result.keywords) + "\n"
                self.root.after(0, lambda t=output: self.summary_text.insert(tk.END, t))
                
            except Exception as e:
                self.root.after(0, lambda: self.summary_text.delete(1.0, tk.END))
                self.root.after(0, lambda: self.summary_text.insert(tk.END, f"Error: {e}"))
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _do_export(self):
        export_format = self.export_format_var.get()
        output_path = filedialog.asksaveasfilename(
            defaultextension=f".{export_format}",
            filetypes=[(export_format.upper(), f"*.{export_format}")]
        )
        
        if not output_path:
            return
        
        try:
            # Create a temporary graph storage for demo
            graph = GraphStorage(db_path=str(Path(tempfile.gettempdir()) / "ariadne_temp.db"))
            exporter = Exporter(graph=graph, config=self.config)
            
            path = exporter.export(
                output_path,
                format=export_format,
                title=f"Ariadne Export - {self.current_system}",
                include_graph=True,
            )
            
            messagebox.showinfo("Success", f"Exported to:\n{path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{e}")
    
    def _view_graph(self):
        try:
            # Create HTML visualization
            graph = GraphStorage(db_path=str(Path(tempfile.gettempdir()) / "ariadne_temp.db"))
            visualizer = GraphVisualizer(graph, self.config)
            
            html = visualizer.to_html(title=f"Knowledge Graph - {self.current_system}")
            
            # Save and open in browser
            temp_path = Path(tempfile.gettempdir()) / "ariadne_graph.html"
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(html)
            
            webbrowser.open(f"file://{temp_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Graph visualization failed:\n{e}")
    
    # === Settings Operations ===
    
    def _change_language(self):
        dialog = LanguageDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result:
            set_locale(dialog.result)
            self.lang_label.config(text=f"Lang: {dialog.result}")
            
            # Refresh UI
            messagebox.showinfo("Language Changed", 
                              f"Language changed to: {get_locale_display()}\n"
                              "Some changes will take effect after restart.")
    
    def _status(self, msg: str):
        self.status_label.config(text=msg)


def main():
    """Launch the GUI."""
    try:
        root = tk.Tk()
        app = AriadneGUI(root)
        root.mainloop()
    except Exception as e:
        import traceback
        print(f"GUI Error: {e}")
        print("\nDetailed error:")
        traceback.print_exc()
        
        # Try to show error in a message box
        try:
            root = tk.Tk()
            root.withdraw()
            from tkinter import messagebox
            messagebox.showerror("Ariadne GUI Error", f"Failed to start GUI:\n\n{e}\n\nPlease check your configuration and try again.")
        except:
            pass
        
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
