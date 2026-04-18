"""Debug script: test PO parsing and MO generation."""
import re
from pathlib import Path

def _unescape(s: str) -> str:
    i = 0
    result = []
    while i < len(s):
        if i < len(s) - 1 and s[i] == "\\":
            c = s[i + 1]
            if c == "n":   result.append("\n")
            elif c == "t": result.append("\t")
            elif c == "r": result.append("\r")
            elif c == "\\": result.append("\\")
            elif c == '"':  result.append('"')
            elif c == "\n": result.append("")
            else:           result.append(c)
            i += 2
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def _compile_po(po_path: Path):
    entries = []
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
            # Save previous entry
            if msgid and msgstr:
                if msgctxt:
                    id_bytes = (msgctxt + "\x04" + msgid).encode("utf-8")
                else:
                    id_bytes = msgid.encode("utf-8")
                entries.append((id_bytes + b'\x00', msgstr.encode("utf-8") + b'\x00'))
            # Read msgid
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

    if msgid and msgstr:
        if msgctxt:
            id_bytes = (msgctxt + "\x04" + msgid).encode("utf-8")
        else:
            id_bytes = msgid.encode("utf-8")
        # .mo format: msgid1 \0 msgid2 — append \0 for singular/plural separator
        id_bytes += b'\x00'
        entries.append((id_bytes, msgstr.encode("utf-8") + b'\x00'))
        if len(msgstr) > 50:
            print(f"  DEBUG: saved entry with msgid={repr(msgid[:30])} msgstr_len={len(msgstr)}")

    return entries


po = Path(r'D:\WorkSpace\Claw\AI项目\Ariadne\locale\en\LC_MESSAGES\ariadne.po')
entries = _compile_po(po)
print(f"Parsed {len(entries)} entries")
for eid, estr in entries[:3]:
    print(f"  msgid={repr(eid[:40])}  msgstr={repr(estr[:40])}")

# Now test the MO file using Python's own gettext
import struct, tempfile, os

MAGIC_LE = 0x950412DE
nstrings = len(entries)

# Layout: header(28) | orig_table(n×8) | trans_table(n×8) | orig_data | trans_data
header_size = 7 * 4
table_size = nstrings * 8 * 2
data_start = header_size + table_size

orig_data = [e[0] for e in entries]
trans_data = [e[1] for e in entries]
trans_data_start = data_start + sum(len(d) for d in orig_data)

with tempfile.NamedTemporaryFile(suffix='.mo', delete=False) as f:
    mo_path = f.name
    f.write(struct.pack("<I", MAGIC_LE))
    f.write(struct.pack("<I", 0))
    f.write(struct.pack("<I", nstrings))
    f.write(struct.pack("<I", header_size))
    f.write(struct.pack("<I", header_size + nstrings * 8))
    f.write(struct.pack("<I", 0))
    f.write(struct.pack("<I", 0))

    cur = data_start
    for d in orig_data:
        f.write(struct.pack("<II", cur, len(d)))
        cur += len(d)

    cur = trans_data_start
    for d in trans_data:
        f.write(struct.pack("<II", cur, len(d)))
        cur += len(d)

    for d in orig_data:
        f.write(d)
    for d in trans_data:
        f.write(d)

print(f"MO file written to {mo_path}")

# Now test with gettext
import gettext
try:
    t = gettext.translation('ariadne', localedir=str(po.parent.parent.parent), languages=['en'])
    print("gettext loaded OK!")
    print(f'_("Search") = {repr(t.gettext("Search"))}')
except Exception as ex:
    print(f"gettext error: {ex}")
finally:
    os.unlink(mo_path)
