"""Rebuild PO files - zh_CN with translations, others with English placeholders."""
from pathlib import Path
from datetime import datetime, timezone

locale_dir = Path(__file__).parent.parent / "locale"

# English strings -> Chinese translations (zh_CN)
ZH_CN_TRANSLATIONS = {
    "Ingest files into memory": "将文件摄入记忆",
    "Search memory": "搜索记忆",
    "Show system info": "显示系统信息",
    "Ingesting: {path}": "正在摄入: {path}",
    "Search query:": "搜索查询:",
    "No results found.": "未找到结果。",
    "Found {count} result(s):": "找到 {count} 个结果:",
    "Source: {source}": "来源: {source}",
    "Chunks: {chunks}": "分块数: {chunks}",
    "Settings": "设置",
    "Language": "语言",
    "Select language:": "选择语言:",
    "Memory Info": "记忆信息",
    "Total documents: {count}": "文档总数: {count}",
    "Total chunks: {count}": "分块总数: {count}",
    "Vector store: {status}": "向量存储: {status}",
    "Error: {message}": "错误: {message}",
    "Ingestion complete.": "摄入完成。",
    "Export memory": "导出记忆",
    "Import memory": "导入记忆",
    "Clear memory": "清空记忆",
}

# 21 strings
STRINGS = [
    "Ingest files into memory",
    "Search memory",
    "Show system info",
    "Ingesting: {path}",
    "Search query:",
    "No results found.",
    "Found {count} result(s):",
    "Source: {source}",
    "Chunks: {chunks}",
    "Settings",
    "Language",
    "Select language:",
    "Memory Info",
    "Total documents: {count}",
    "Total chunks: {count}",
    "Vector store: {status}",
    "Error: {message}",
    "Ingestion complete.",
    "Export memory",
    "Import memory",
    "Clear memory",
]

LANG_NAMES = {
    "zh_CN": "简体中文 (Simplified Chinese)",
    "zh_TW": "繁體中文 (Traditional Chinese)",
    "en": "English",
    "fr": "Français (French)",
    "es": "Español (Spanish)",
    "ru": "Русский (Russian)",
    "ar": "العربية (Arabic)",
}

PLURAL_FORMS = {
    "zh_CN": 'nplurals=1; plural=0;',
    "zh_TW": 'nplurals=1; plural=0;',
    "en": 'nplurals=2; plural=(n != 1);',
    "fr": 'nplurals=2; plural=(n > 1);',
    "es": 'nplurals=2; plural=(n != 1);',
    "ru": 'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);',
    "ar": 'nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : n%100>=11 ? 4 : 5);',
}

def make_header(locale):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M+0000")
    parts = [
        ("Project-Id-Version", "Ariadne 0.1.0"),
        ("Report-Msgid-Bugs-To", "https://github.com/Chaobs/ariadne-memory/issues"),
        ("POT-Creation-Date", now),
        ("PO-Revision-Date", now),
        ("Last-Translator", "Chaobs"),
        ("Language", locale),
        ("Language-Team", LANG_NAMES.get(locale, locale)),
        ("Plural-Forms", PLURAL_FORMS.get(locale, "nplurals=2; plural=(n != 1);")),
        ("MIME-Version", "1.0"),
        ("Content-Type", "text/plain; charset=UTF-8"),
        ("Content-Transfer-Encoding", "8bit"),
    ]
    return "\n".join('"%s: %s\\n"' % (k, v) for k, v in parts)

def po_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")

def make_po_file(locale, translations):
    po_path = locale_dir / locale / "LC_MESSAGES" / "ariadne.po"
    lines = [
        "# Ariadne - " + LANG_NAMES.get(locale, locale) + " Message Catalog",
        "# Copyright (C) 2026 Chaobs",
        "# This file is distributed under the MIT License.",
        "",
        'msgid ""',
        'msgstr ""',
        make_header(locale),
        "",
    ]
    for s in STRINGS:
        t = translations.get(s, s)  # Use translation or original
        lines.append('msgid "%s"' % po_escape(s))
        lines.append('msgstr "%s"' % po_escape(t))
        lines.append("")
    content = "\n".join(lines) + "\n"
    po_path.write_text(content, encoding="utf-8", newline="\n")
    print("Created:", locale, "->", po_path)

# zh_CN has translations, others have English
make_po_file("zh_CN", ZH_CN_TRANSLATIONS)
for loc in ["zh_TW", "en", "fr", "es", "ru", "ar"]:
    make_po_file(loc, {})  # English placeholders

print("\nCompiling MO files with Babel:")
from babel.messages.pofile import read_po
from babel.messages.mofile import write_mo

for locale in ["zh_CN", "zh_TW", "en", "fr", "es", "ru", "ar"]:
    po_path = locale_dir / locale / "LC_MESSAGES" / "ariadne.po"
    mo_path = po_path.with_suffix(".mo")
    try:
        catalog = read_po(po_path.open(encoding="utf-8", newline="\n"))
        with mo_path.open("wb") as f:
            write_mo(f, catalog)
        print("  OK:", locale)
    except Exception as e:
        print("  FAILED:", locale, "-", e)
