"""Package only the translation source and tools; never include games or fonts."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "README.md", "VALIDATION.md", "patch.py", "requirements.txt", "baseline.json",
    "en.json", "zh-CN.json", "zh-TW.json", "wow-terms.json", "glossary.json", "overrides.json",
    "tools/prepare.py", "tools/package.py", "tests/test_patch.py", ".gitignore", ".gitattributes",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "AzerothSurvivors-zhTW-1.0.0.zip"
    with ZipFile(path, "x", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, "AzerothSurvivors-zhTW-1.0.0/" + name)
    with ZipFile(path) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(FILES):
            raise ValueError("ZIP integrity check failed")
        if any(Path(name).suffix.lower() in {".exe", ".dll", ".mpq", ".ttf", ".ttc", ".otf", ".original"}
               for name in archive.namelist()):
            raise ValueError("Unexpected game/font content in package")
        for name in FILES:
            if archive.read("AzerothSurvivors-zhTW-1.0.0/" + name) != (ROOT / name).read_bytes():
                raise ValueError(f"Packaged content differs: {name}")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".zip.sha256").write_text(f"{checksum}  {path.name}\n", encoding="ascii")
    print(f"{path}\n{path.stat().st_size:,} bytes; {len(FILES)} files; SHA-256: {checksum}")


if __name__ == "__main__":
    main()
