"""Export reviewed asset translations from the local coverage audit."""
import argparse
from collections import Counter
import hashlib
import html
import json
import mmap
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from asset_patch import compatible
from vendor.mpq.reader import Archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path)
    parser.add_argument("game_dir", type=Path)
    args = parser.parse_args()
    db = sqlite3.connect(args.audit.resolve().as_uri() + "?mode=ro", uri=True)
    result = {"game_version": "0.120.4", "game_build": "93ecb257", "files": {}}
    origins = Counter()
    with (args.game_dir / "Data/patch.MPQ").open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        archive = Archive(mm)
        for file, key, english, target, origin in db.execute("SELECT file,key,english,chinese,origin FROM strings WHERE chinese<>'' ORDER BY file,key"):
            if not compatible(english, target):
                raise ValueError(f"Invalid translation: {file} {key}")
            if file not in result["files"]:
                raw = archive.read(file)
                result["files"][file] = {"source_sha256": hashlib.sha256(raw).hexdigest(), "translations": {}}
                if file.endswith(".dbc"):
                    result["files"][file]["fields"] = db.execute("SELECT fields FROM files WHERE path=?", (file,)).fetchone()[0]
            item = result["files"][file]
            if file.endswith(".dbc"):
                column = key.split(":")[1]
                mapping = item["translations"].setdefault(column, {})
                if english in mapping and mapping[english] != target:
                    raise ValueError(f"Ambiguous DBC translation: {file} {english}")
                mapping[english] = target
            elif file.endswith(".lua"):
                item["translations"][key] = {"source": english, "target": target}
            elif file.endswith(".xml"):
                item["translations"][html.unescape(english)] = target
            origins[origin] += 1
    path = ROOT / "assets-zh-TW.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("FILES", len(result["files"]), "TRANSLATED_FIELDS", sum(origins.values()), "SOURCES", dict(origins))
    print("OUTPUT", path, path.stat().st_size)


if __name__ == "__main__":
    main()
