#!/usr/bin/env python3
"""
Compiles .po files to .mo binary format.

.mo entry format:
  Each original string entry in the data section is: msgid1 \x00 msgid2
  where msgid2 is empty for non-plural messages.
  Each translation string is: msgstr \x00

Usage:
    python tools/msgfmt.py --all        # compile all locales
    python tools/msgfmt.py <input.po>   # compile single file
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path


def _unescape(s: str) -> str:
    """Unescape a PO string literal."""
    i = 0
    result = []
    while i < len(s):
        if i < len(s) - 1 and s[i] == "\\":
            c = s[i + 1]
            if c == "n":    result.append("\n")
            elif c == "t":  result.append("\t")
            elif c == "r":  result.append("\r")
            elif c == "\\": result.append("\\")
            elif c == '"':  result.append('"')
            elif c == "\n": result.append("")
            else:           result.append(c)
            i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def _read_po_string(lines: list[str], start: int) -> tuple[str, int]:
    """Parse a PO string value from lines[start:] (caller strips keyword)."""
    first = lines[start].strip().strip('"')
    value = _unescape(first)
    i = start + 1
    while i < len(lines) and lines[i].strip().startswith('"'):
        cont = lines[i].strip().strip('"')
        value += _unescape(cont)
        i += 1
    return value, i


def _compile_po(po_path: Path) -> list[tuple[bytes, bytes]]:
    """
    Parse a .po file.
    Returns list of (orig_bytes, trans_bytes) pairs.
    orig_bytes = msgid singular + b'\\x00' + msgid plural  (plural is empty for non-plural)
    trans_bytes = msgstr + b'\\x00'
    """
    entries: list[tuple[bytes, bytes]] = []

    with open(po_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    n = len(lines)
    msgctxt = ""
    msgid = ""
    msgstr = ""

    while i < n:
        stripped = lines[i].strip()

        if stripped.startswith("#") or stripped == "":
            i += 1
            continue

        if stripped.startswith("msgctxt "):
            raw = stripped[8:]
            msgctxt = _unescape(raw.strip().strip('"'))
            i += 1
            while i < n and lines[i].strip().startswith('"'):
                msgctxt += _unescape(lines[i].strip().strip('"'))
                i += 1
            continue

        if stripped.startswith('msgid "'):
            if msgid and msgstr:
                # Build msgid bytes: context\x04 + singular + \x00 + plural
                if msgctxt:
                    id_bytes = (msgctxt + "\x04" + msgid).encode("utf-8")
                else:
                    id_bytes = msgid.encode("utf-8")
                # Append singular + \x00 + plural (plural empty) for .mo format
                id_bytes += b'\x00'
                entries.append((id_bytes, msgstr.encode("utf-8") + b'\x00'))
            # Read msgid value
            raw = stripped[6:]
            msgid = _unescape(raw.strip().strip('"'))
            i += 1
            while i < n and lines[i].strip().startswith('"'):
                msgid += _unescape(lines[i].strip().strip('"'))
                i += 1
            msgstr = ""
            msgctxt = ""
            continue

        if stripped.startswith('msgstr "'):
            raw = stripped[8:]
            msgstr = _unescape(raw.strip().strip('"'))
            i += 1
            while i < n and lines[i].strip().startswith('"'):
                msgstr += _unescape(lines[i].strip().strip('"'))
                i += 1
            continue

        i += 1

    # Final entry
    if msgid and msgstr:
        if msgctxt:
            id_bytes = (msgctxt + "\x04" + msgid).encode("utf-8")
        else:
            id_bytes = msgid.encode("utf-8")
        id_bytes += b'\x00'
        entries.append((id_bytes, msgstr.encode("utf-8") + b'\x00'))

    return entries


def compile_po(po_path: str | Path, mo_path: str | Path) -> None:
    """Write a .mo file from parsed PO entries."""
    po_path = Path(po_path)
    mo_path = Path(mo_path)
    entries = _compile_po(po_path)

    MAGIC = 0x950412DE  # little-endian
    nstrings = len(entries)

    # Layout: header(28) | orig_table(n×8) | trans_table(n×8) | orig_data | trans_data
    header_size = 7 * 4
    table_size = nstrings * 8 * 2
    data_start = header_size + table_size

    orig_data = [e[0] for e in entries]
    trans_data = [e[1] for e in entries]

    # Translation data starts after ALL original strings
    trans_data_start = data_start + sum(len(d) for d in orig_data)

    with open(mo_path, "wb") as f:
        f.write(struct.pack("<I", MAGIC))
        f.write(struct.pack("<I", 0))                                     # version
        f.write(struct.pack("<I", nstrings))                             # nstrings
        f.write(struct.pack("<I", header_size))                          # offset_orig
        f.write(struct.pack("<I", header_size + nstrings * 8))          # offset_trans
        f.write(struct.pack("<I", 0))                                     # hash_size
        f.write(struct.pack("<I", 0))                                     # hash_offset

        # Original string offset table
        cur = data_start
        for d in orig_data:
            f.write(struct.pack("<II", cur, len(d)))
            cur += len(d)

        # Translation string offset table
        cur = trans_data_start
        for d in trans_data:
            f.write(struct.pack("<II", cur, len(d)))
            cur += len(d)

        # Original string data
        for d in orig_data:
            f.write(d)

        # Translation string data
        for d in trans_data:
            f.write(d)

    print(f"Compiled: {mo_path} ({nstrings} strings)")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--all":
        base = Path(__file__).parent.parent / "locale"
        langs = ["zh_CN", "zh_TW", "en", "fr", "es", "ru", "ar"]
        for lang in langs:
            po = base / lang / "LC_MESSAGES" / "ariadne.po"
            compile_po(po, po.with_suffix(".mo"))
    elif len(sys.argv) >= 2:
        po_file = Path(sys.argv[1])
        compile_po(po_file, po_file.with_suffix(".mo"))
    else:
        print("Usage: python msgfmt.py [--all | <input.po>]")
        sys.exit(1)
