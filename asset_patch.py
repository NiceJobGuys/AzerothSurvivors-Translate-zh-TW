"""Translate explicitly listed display strings in the player's own MPQ assets."""
from collections import Counter
import hashlib
import html
import io
import json
import mmap
import os
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

from vendor.mpq.reader import Archive
from vendor.mpq.writer import write_archive

OVERLAY_NAME = "patch-Z.MPQ"
ROOT = Path(__file__).resolve().parent
ASSIGN = re.compile(r'^([A-Za-z_][A-Za-z_0-9]*)\s*=\s*"((?:\\.|[^"\\])*)"\s*;', re.M)
PRINTF = re.compile(r'%(?:\d+\$)?[-+#0 ]*\d*(?:\.\d+)?[A-Za-z]|%%')
DOLLAR = re.compile(r'\$(?:\d+)?[A-Za-z]\d*')
PROTECTED = re.compile(r'^(?:SLASH_|.*_CMD\d*$|.*_CONFIRM_STRING$)')


def signature(text):
    # WoW $s1/$d references end before punctuation; % and plural grammar are separate.
    text = re.sub(r'(?<=\d)% (?=[A-Za-z]{2,}\b)', '％ ', text)
    dollars = Counter(t for t in DOLLAR.findall(PRINTF.sub("", text)) if t not in {"$g", "$l"})
    markup = Counter(re.findall(r'\|c[0-9a-fA-F]{8}|\|H[^\n]*?\|h|\|T[^\n]*?\|t|\|[rh]', text))
    named = Counter(re.findall(r'\{[A-Za-z0-9_]+\}', text))
    arguments = Counter()
    position = 0
    for token in PRINTF.findall(text):
        if token == "%%":
            arguments[(0, token)] += 1
            continue
        explicit = re.match(r"%(\d+)\$", token)
        if explicit:
            index = int(explicit[1])
        else:
            position += 1
            index = position
        arguments[(index, re.sub(r"^%\d+\$", "%", token))] += 1
    literals = PRINTF.sub("", text)
    return dollars, arguments, markup, named, literals.count("%") + literals.count("％")


def numbers(text):
    text = PRINTF.sub("", re.sub(r'(?<=\d)% (?=[A-Za-z]{2,}\b)', '％ ', text))
    return Counter(re.findall(r'\d+(?:\.\d+)?', DOLLAR.sub("", text)))


def compatible(source, target):
    return (isinstance(target, str) and bool(target.strip()) and "\x00" not in target and "\ufffd" not in target
            and signature(source) == signature(target)
            and numbers(source) == numbers(target))


def lua_decode(raw):
    escapes = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f', 'v': '\v', 'a': '\a',
               '\\': '\\', '"': '"', "'": "'"}
    def replace(match):
        value = match[1]
        if value.isdecimal():
            return chr(int(value))
        if value not in escapes:
            raise ValueError(f"Unsupported Lua escape: {value}")
        return escapes[value]
    return re.sub(r'\\(\d{1,3}|.)', replace, raw)


def lua_encode(text):
    escapes = {'\\': '\\\\', '"': '\\"', '\n': '\\n', '\r': '\\r', '\t': '\\t'}
    return ''.join(escapes.get(c, '\\' + str(ord(c)).zfill(3) if ord(c) < 32 else c) for c in text)


def patch_lua(raw, translations):
    source = raw.decode("utf-8-sig")
    seen = set()
    def replace(match):
        key = match[1]
        if key not in translations:
            return match[0]
        if key in seen or PROTECTED.search(key):
            raise ValueError(f"Duplicate or protected Lua key: {key}")
        seen.add(key)
        item = translations[key]
        if lua_decode(match[2]) != item["source"] or not compatible(item["source"], item["target"]):
            raise ValueError(f"Invalid Lua translation: {key}")
        a, b = match.start(2) - match.start(), match.end(2) - match.start()
        return match[0][:a] + lua_encode(item["target"]) + match[0][b:]
    output = ASSIGN.sub(replace, source)
    if seen != translations.keys():
        raise ValueError("Lua translation refers to missing keys")
    return output.encode("utf-8"), len(seen)


def patch_dbc(raw, fields, translations):
    magic, rows, actual_fields, width, length = struct.unpack_from("<4s4I", raw)
    start = 20 + rows * width
    if magic != b"WDBC" or fields != actual_fields or width != fields * 4 or start + length != len(raw):
        raise ValueError("DBC schema or length changed")
    output = bytearray(raw)
    pool = raw[start:]
    added, positions = {}, []
    for column, mapping in translations.items():
        column = int(column)
        if not 0 < column < fields:
            raise ValueError("Invalid DBC text column")
        for index in range(rows):
            position = 20 + index * width + column * 4
            offset = struct.unpack_from("<I", raw, position)[0]
            end = pool.find(b"\0", offset)
            if offset >= len(pool) or end < offset:
                raise ValueError("Invalid DBC string offset")
            text = pool[offset:end].decode("utf-8")
            if text not in mapping:
                continue
            target = mapping[text]
            if not compatible(text, target):
                raise ValueError(f"Invalid DBC translation: {text}")
            if target not in added:
                added[target] = len(output) - start
                output.extend(target.encode() + b"\0")
            struct.pack_into("<I", output, position, added[target])
            positions.append(position)
    struct.pack_into("<I", output, 16, len(output) - start)
    proof = bytearray(output[:len(raw)])
    proof[16:20] = raw[16:20]
    for position in positions:
        proof[position:position + 4] = raw[position:position + 4]
    if proof != raw:
        raise ValueError("Non-text DBC data changed")
    return bytes(output), len(positions)


def patch_xml(raw, translations):
    source = raw.decode("utf-8")
    counts = Counter()
    def replace(match):
        text = html.unescape(match[1])
        if text not in translations:
            return match[0]
        target = translations[text]
        if not compatible(text, target):
            raise ValueError(f"Invalid XML label: {text}")
        counts[text] += 1
        return 'text="' + html.escape(target, quote=True) + '"'
    output = re.sub(r'\btext="([^"]*)"', replace, source).encode()
    if counts.keys() != translations.keys():
        raise ValueError("XML translation refers to missing labels")
    ET.fromstring(output)
    return output, sum(counts.values())


def build_overlay(game_dir, database, font_path):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    members, counts = {}, {}
    with (game_dir / "Data/patch.MPQ").open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        archive = Archive(mm)
        for name, item in database["files"].items():
            raw = archive.read(name)
            if raw is None or hashlib.sha256(raw).hexdigest() != item["source_sha256"]:
                raise ValueError(f"Asset source changed: {name}")
            if name.endswith(".dbc"):
                members[name], counts[name] = patch_dbc(raw, item["fields"], item["translations"])
            elif name.endswith(".lua"):
                members[name], counts[name] = patch_lua(raw, item["translations"])
            elif name.endswith(".xml"):
                members[name], counts[name] = patch_xml(raw, item["translations"])
            else:
                raise ValueError(f"Unexpected asset type: {name}")
    chars = {ord(c) for c in json.dumps(database, ensure_ascii=False) if ord(c) >= 32}
    main = json.loads((Path(__file__).parent / "zh-TW.json").read_text(encoding="utf-8"))
    chars.update(ord(c) for text in main.values() for c in text if ord(c) >= 32)
    font = TTFont(font_path, fontNumber=0, recalcTimestamp=False)
    cmap = font.getBestCmap()
    missing = {c for c in chars - cmap.keys() if 0x2E80 <= c <= 0x9FFF}
    if missing:
        raise ValueError("Asset font missing Chinese glyphs: " + ''.join(map(chr, sorted(missing))))
    options = subset.Options()
    options.hinting = False
    options.recalc_timestamp = False
    options.drop_tables += ["MERG", "meta"]
    selected = subset.Subsetter(options=options)
    selected.populate(unicodes=chars & cmap.keys())
    selected.subset(font)
    stream = io.BytesIO()
    font.save(stream)
    for name in ["FRIZQT__", "ARIALN", "MORPHEUS", "SKURRI", "AZS_SC"]:
        members[f"Fonts\\{name}.TTF"] = stream.getvalue()
    output = write_archive(members)
    check = Archive(output)
    if any(check.read(name) != data for name, data in members.items()):
        raise ValueError("MPQ round-trip verification failed")
    return output, counts


def install_overlay(game_dir, backup_dir, font_path):
    from patch import digest, load_json, replace_checked, write_exclusive

    baseline = load_json(ROOT / "baseline.json")
    exe = game_dir / "AzerothSurvivors.exe"
    exe_hash = digest(exe.read_bytes())
    if exe_hash != baseline["original_sha256"]:
        receipt = load_json(backup_dir / "installed.json")
        if (receipt.get("original_sha256") != baseline["original_sha256"] or
                exe_hash != receipt.get("patched_sha256") or
                digest((backup_dir / "AzerothSurvivors.exe.original").read_bytes()) != baseline["original_sha256"]):
            raise ValueError("遊戲 EXE 與支援版本及原版備份不符")
    dictionary = ROOT / "assets-zh-TW.json"
    data, counts = build_overlay(game_dir, load_json(dictionary), font_path)
    desired = digest(data)
    target = game_dir / "Data" / OVERLAY_NAME
    receipt_path = backup_dir / "assets-installed.json"
    previous = load_json(receipt_path) if receipt_path.exists() else {}
    if previous and previous.get("original_sha256") != baseline["original_sha256"]:
        raise ValueError("資源收據屬於其他遊戲版本")
    if target.exists():
        current = digest(target.read_bytes())
        if current != desired and current != previous.get("overlay_sha256"):
            raise ValueError("已有非本工具建立或已被修改的 patch-Z.MPQ，拒絕覆蓋")
        if current != desired:
            replace_checked(target, current, data)
    else:
        staging = target.with_name(target.name + ".zhtw-new")
        write_exclusive(staging, data)
        if digest(exe.read_bytes()) != exe_hash:
            raise ValueError("遊戲在套用期間改變，保留暫存檔並停止")
        os.rename(staging, target)
    receipt = {"original_sha256": baseline["original_sha256"], "overlay_sha256": desired,
               "dictionary_sha256": digest(dictionary.read_bytes()), "fields": sum(counts.values()), "files": counts}
    content = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode()
    if receipt_path.exists():
        replace_checked(receipt_path, digest(receipt_path.read_bytes()), content)
    else:
        write_exclusive(receipt_path, content)
    if digest(target.read_bytes()) != desired:
        raise ValueError("中文覆蓋包安裝後雜湊不符")
    print(f"已套用 {len(counts)} 個資源檔、{sum(counts.values()):,} 個文字欄位：{target}")
    return receipt


def restore_overlay(game_dir, backup_dir):
    from patch import digest, load_json

    target = game_dir / "Data" / OVERLAY_NAME
    if not target.exists():
        print("目前沒有中文資源覆蓋包")
        return
    receipt = load_json(backup_dir / "assets-installed.json")
    if digest(target.read_bytes()) != receipt.get("overlay_sha256"):
        raise ValueError("中文覆蓋包與收據不符，拒絕刪除")
    target.unlink()
    print("已移除本工具的中文資源覆蓋包；原版 MPQ 未變更")


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["apply", "restore"])
    parser.add_argument("game_dir", type=Path)
    parser.add_argument("backup_dir", type=Path)
    parser.add_argument("--font", type=Path, default=Path(r"C:\Windows\Fonts\msjh.ttc"))
    args = parser.parse_args()
    try:
        if args.action == "apply":
            install_overlay(args.game_dir.resolve(), args.backup_dir.resolve(), args.font)
        else:
            restore_overlay(args.game_dir.resolve(), args.backup_dir.resolve())
    except (OSError, ValueError, ImportError) as error:
        print(f"停止：{error}", file=sys.stderr)
        sys.exit(1)
