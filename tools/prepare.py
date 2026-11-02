"""Extract the installed language tables and rebuild the editable zh-TW draft."""
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_SHA256 = "aa6b254f905e2f7a4cbc7c2c8f11af822ec362e3d2b8e84cabd8c38893a10dc8"
GAME_VERSION = "0.137.0"
GAME_BUILD = "d171b8f9f"
FONT_OFFSET = 120875580
FONT_SIZE = 1225410
FONT_SHA256 = "d145063c4f54417778c7e92cf85a9cb12fbf2ce08c54aa3384d0bbee760232e5"


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


def translation_sources(english, chinese, overrides):
    if chinese.keys() - english.keys():
        raise ValueError("Chinese table has unknown English keys")
    missing = english.keys() - chinese.keys()
    if missing - overrides.keys():
        raise ValueError(f"Missing Chinese keys require explicit translations: {sorted(missing - overrides.keys())}")
    return {key: chinese.get(key, value) for key, value in english.items()}


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
    overrides = json.loads((ROOT / "overrides.json").read_text(encoding="utf-8"))
    sources = translation_sources(english, chinese, overrides)
    font = data[FONT_OFFSET:FONT_OFFSET + FONT_SIZE]
    if hashlib.sha256(font).hexdigest() != FONT_SHA256 or (GAME_BUILD + GAME_VERSION).encode() not in data:
        raise ValueError("Embedded version or font source differs")
    write_json("en.json", english)
    write_json("zh-CN.json", chinese)
    write_json("baseline.json", {
        "original_sha256": hashlib.sha256(data).hexdigest(),
        "original_size": len(data),
        "json_offset": offset,
        "json_size": len(raw),
        "json_sha256": hashlib.sha256(raw).hexdigest(),
        "label_offset": offset - len("简体中文".encode()),
        "entries": len(english),
        "chinese_entries": len(chinese),
        "missing_chinese_keys": sorted(english.keys() - chinese.keys()),
        "game_version": GAME_VERSION,
        "game_build": GAME_BUILD,
        "font_offset": FONT_OFFSET,
        "font_size": FONT_SIZE,
        "font_sha256": hashlib.sha256(font).hexdigest(),
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
    unknown = overrides.keys() - english.keys()
    if unknown:
        raise ValueError(f"Unknown override keys: {sorted(unknown)}")
    target = {}
    pattern = re.compile("|".join(re.escape(term) for term in sorted(glossary, key=len, reverse=True)))
    for key, value in sources.items():
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
