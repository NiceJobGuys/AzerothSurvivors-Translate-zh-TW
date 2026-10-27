"""Extract the installed language tables and rebuild the editable zh-TW draft."""
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_SHA256 = "7e3e3f9558de1d87e615592c7b5d83f00de393ac8efa4e67d8f9b634ed07d6bf"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def extract(data, label):
    markers = list(re.finditer(re.escape(label.encode()) + rb'\{\r?\n  "game.title"', data))
    if len(markers) != 1:
        raise ValueError(f"Language marker is not unique: {label}")
    offset = markers[0].start() + len(label.encode())
    text = data[offset:offset + 500_000].decode("utf-8", errors="replace")
    table, end = json.JSONDecoder(object_pairs_hook=unique_object).raw_decode(text)
    raw = text[:end].encode()
    if data[offset:offset + len(raw)] != raw:
        raise ValueError("Invalid UTF-8 in language table")
    return offset, raw, table


def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    from opencc import OpenCC

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("--terms-db", type=Path, help="Import relevant approved CoA terms once")
    args = parser.parse_args()
    data = args.exe.read_bytes()
    if hashlib.sha256(data).hexdigest() != SUPPORTED_SHA256:
        raise ValueError("Unsupported executable: re-check the language and font locations before porting")
    _, _, english = extract(data, "English")
    offset, raw, chinese = extract(data, "zh简体中文")
    if english.keys() != chinese.keys():
        raise ValueError("English and Chinese keys differ")
    write_json("en.json", english)
    write_json("zh-CN.json", chinese)
    write_json("baseline.json", {
        "original_sha256": hashlib.sha256(data).hexdigest(),
        "original_size": len(data),
        "json_offset": offset,
        "json_size": len(raw),
        "json_sha256": hashlib.sha256(raw).hexdigest(),
        "label_offset": offset - len("简体中文".encode()),
        "entries": len(chinese),
        "font_offset": 118999084,
        "font_size": 1225410,
        "font_sha256": hashlib.sha256(data[118999084:120224494]).hexdigest(),
    })
    name_keys = [key for key in english if re.match(r"(?:class|race|zone|ability|enemy|boss|weapon|starter|set)\.", key)
                 and not key.endswith((".blurb", ".line1", ".line2", ".line3", ".subtitle"))]
    if args.terms_db:
        with sqlite3.connect(args.terms_db.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            approved = {}
            for key in name_keys:
                row = connection.execute("SELECT zh, status FROM terms WHERE en = ?", (english[key],)).fetchone()
                if row and row[1] in {"official", "decided", "vocab", "rule", "manual"}:
                    approved[english[key]] = row[0]
        write_json("wow-terms.json", approved)
    converter = OpenCC("s2t")
    glossary = json.loads((ROOT / "glossary.json").read_text(encoding="utf-8"))
    terms = json.loads((ROOT / "wow-terms.json").read_text(encoding="utf-8"))
    overrides = json.loads((ROOT / "overrides.json").read_text(encoding="utf-8"))
    unknown = overrides.keys() - chinese.keys()
    if unknown:
        raise ValueError(f"Unknown override keys: {sorted(unknown)}")
    target = {}
    pattern = re.compile("|".join(re.escape(term) for term in sorted(glossary, key=len, reverse=True)))
    for key, value in chinese.items():
        text = converter.convert(value)
        text = pattern.sub(lambda match: glossary[match.group()], text)
        if key in name_keys:
            text = terms.get(english[key], text)
        target[key] = overrides.get(key, text)
    write_json("zh-TW.json", target)
    print(f"Extracted {len(english)} keys; JSON offset {offset}, capacity {len(raw)} bytes")
    print(f"Original SHA-256: {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
