"""Package only the translation source and tools; never include games or fonts."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = "AzerothSurvivors-zhTW-1.3.0"
FILES = [
    "README.md", "VALIDATION.md", "patch.py", "requirements.txt", "baseline.json",
    "en.json", "zh-CN.json", "zh-TW.json", "wow-terms.json", "glossary.json", "overrides.json",
    "tools/prepare.py", "tools/package.py", "tests/test_patch.py", ".gitignore", ".gitattributes",
    "AGENTS.md", "asset_patch.py", "assets-zh-TW.json", "assets-overrides.json",
    "tools/export_assets.py", "tests/test_assets.py", "vendor/__init__.py", "vendor/mpq/__init__.py",
    "vendor/mpq/reader.py", "vendor/mpq/writer.py", "vendor/mpq/crypto.py", "vendor/mpq/names.py",
    "vendor/mpq/LICENSE.txt", "vendor/mpq/NOTICE.md",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / (NAME + ".zip")
    with ZipFile(path, "x", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, NAME + "/" + name)
    with ZipFile(path) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(FILES):
            raise ValueError("ZIP integrity check failed")
        if any(Path(name).suffix.lower() in {".exe", ".dll", ".mpq", ".ttf", ".ttc", ".otf", ".original"}
               for name in archive.namelist()):
            raise ValueError("Unexpected game/font content in package")
        for name in FILES:
            if archive.read(NAME + "/" + name) != (ROOT / name).read_bytes():
                raise ValueError(f"Packaged content differs: {name}")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".zip.sha256").write_text(f"{checksum}  {path.name}\n", encoding="ascii")
    print(f"{path}\n{path.stat().st_size:,} bytes; {len(FILES)} files; SHA-256: {checksum}")


if __name__ == "__main__":
    main()
