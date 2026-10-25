"""Azeroth Survivors 繁體中文補丁；只支援 baseline.json 記錄的原版。"""
import argparse
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
TOKENS = re.compile(r"\{[A-Za-z0-9_]+\}|%(?:[0-9]+\$)?[-+0-9.]*[sdfiu]")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"JSON 鍵重複：{key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def validate_translation(source, target):
    if source.keys() != target.keys():
        raise ValueError("譯文鍵與原文不一致")
    for key, text in target.items():
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"譯文空白或格式錯誤：{key}")
        if Counter(TOKENS.findall(source[key])) != Counter(TOKENS.findall(text)):
            raise ValueError(f"譯文參數不一致：{key}")
        if Counter(re.findall(r"</?[A-Za-z][^>]*>", source[key])) != Counter(re.findall(r"</?[A-Za-z][^>]*>", text)):
            raise ValueError(f"譯文標記不一致：{key}")
        if "\ufffd" in text or "\x00" in text:
            raise ValueError(f"譯文含無效字元：{key}")


def make_font(original_font, target, font_path):
    from fontTools import subset
    from fontTools.ttLib import TTFont

    original = TTFont(io.BytesIO(original_font))
    font = TTFont(font_path, fontNumber=0, recalcTimestamp=False)
    characters = {ord(c) for text in [*target.values(), "繁體中文"] for c in text if ord(c) >= 32}
    existing = set(original.getBestCmap())
    available = set(font.getBestCmap())
    # shortcut: retain the game's existing emoji fallback; only new missing glyphs are an error.
    missing = (characters | existing) - available - {ord(c) for c in "♾⚔️🏆💀"}
    if missing:
        raise ValueError("本機字型缺字：" + "".join(chr(c) for c in sorted(missing)))
    options = subset.Options()
    options.hinting = False
    options.recalc_timestamp = False
    options.drop_tables += ["MERG", "meta"]
    selected = subset.Subsetter(options=options)
    selected.populate(unicodes=existing | (characters & available))
    selected.subset(font)
    output = io.BytesIO()
    font.save(output)
    result = output.getvalue()
    cmap = TTFont(io.BytesIO(result)).getBestCmap()
    if (existing | (characters & available)) - cmap.keys():
        raise ValueError("字型子集遺失字元")
    print(f"字型：{len(cmap)} 個字元，{len(result):,} bytes；繁中漢字缺字 0")
    return result


def make_patch(data, baseline, source, target, font):
    if len(data) != baseline["original_size"] or digest(data) != baseline["original_sha256"]:
        raise ValueError("原版雜湊不符；遊戲可能已更新或套用過其他補丁")
    validate_translation(source, target)
    payload = json.dumps(target, ensure_ascii=False, separators=(",", ":")).encode()
    start, size = baseline["json_offset"], baseline["json_size"]
    font_start, font_size = baseline["font_offset"], baseline["font_size"]
    label_start = baseline["label_offset"]
    if not (0 <= label_start < label_start + 12 <= start < start + size <= font_start < font_start + font_size <= len(data)):
        raise ValueError("補丁範圍無效或重疊")
    if digest(data[start:start + size]) != baseline["json_sha256"]:
        raise ValueError("原版語系區塊不符")
    if digest(data[font_start:font_start + font_size]) != baseline["font_sha256"]:
        raise ValueError("原版字型區塊不符")
    if data[label_start:label_start + 12] != "简体中文".encode():
        raise ValueError("找不到原版語言名稱")
    if len(payload) > size or len(font) > font_size:
        raise ValueError(f"超出原區塊容量：文字 {len(payload)}/{size}；字型 {len(font)}/{font_size}")
    result = bytearray(data)
    result[label_start:label_start + 12] = "繁體中文".encode()
    result[start:start + size] = payload.ljust(size, b" ")
    result[font_start:font_start + font_size] = font.ljust(font_size, b"\0")
    if len(result) != len(data) or json.loads(result[start:start + size]) != target:
        raise ValueError("補丁回讀驗證失敗")
    print(f"文字：{len(target):,} 筆，{len(payload):,}/{size:,} bytes；所有參數一致")
    return bytes(result)


def build(data, baseline, font_path):
    if len(data) != baseline["original_size"] or digest(data) != baseline["original_sha256"]:
        raise ValueError("原版雜湊不符；不支援這個遊戲版本")
    source = load_json(ROOT / "en.json")
    target = load_json(ROOT / "zh-TW.json")
    validate_translation(source, target)
    start, size = baseline["font_offset"], baseline["font_size"]
    font = make_font(data[start:start + size], target, font_path)
    return make_patch(data, baseline, source, target, font)


def write_exclusive(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if digest(path.read_bytes()) != digest(data):
        raise ValueError(f"檔案回讀雜湊不符：{path}")


def replace_checked(path, expected, replacement):
    # Keep the original file in place until the replacement has been fully written and verified.
    staging = path.with_name(path.name + ".zhtw-new")
    write_exclusive(staging, replacement)
    if digest(path.read_bytes()) != expected:
        raise ValueError(f"寫入前遊戲檔案已改變；保留暫存檔：{staging}")
    os.replace(staging, path)
    if digest(path.read_bytes()) != digest(replacement):
        raise ValueError("替換後雜湊不符，請保留備份並停止操作")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "apply", "restore"])
    parser.add_argument("exe", type=Path, help="原版或已套用的 AzerothSurvivors.exe")
    parser.add_argument("destination", type=Path, help="build：輸出 EXE；apply/restore：備份目錄")
    parser.add_argument("--font", type=Path, default=Path(r"C:\Windows\Fonts\msjh.ttc"))
    args = parser.parse_args()
    baseline = load_json(ROOT / "baseline.json")
    exe = args.exe.resolve(strict=True)
    data = exe.read_bytes()
    original_hash = baseline["original_sha256"]
    current_hash = digest(data)
    if args.action == "build":
        if args.destination.resolve() == exe:
            raise ValueError("build 輸出不能覆蓋來源")
        if args.destination.exists():
            raise ValueError("輸出檔已存在，請使用新的檔名")
        result = build(data, baseline, args.font)
        write_exclusive(args.destination, result)
        print(f"已建立：{args.destination.resolve()}\nSHA-256：{digest(result)}")
        return

    backup_dir = args.destination.resolve()
    backup = backup_dir / "AzerothSurvivors.exe.original"
    receipt_path = backup_dir / "installed.json"
    if exe in {backup.resolve(), receipt_path.resolve()}:
        raise ValueError("遊戲與備份路徑不可重疊")
    if args.action == "restore":
        if current_hash == original_hash:
            print("目前已是支援的原版，無須還原")
            return
        receipt = load_json(receipt_path)
        original = backup.read_bytes()
        if digest(original) != original_hash or receipt.get("original_sha256") != original_hash:
            raise ValueError("原版備份雜湊不符")
        if current_hash != receipt.get("patched_sha256"):
            raise ValueError("目前遊戲與安裝收據不符；不覆蓋更新過或另行修改的檔案")
        replace_checked(exe, current_hash, original)
        print("已還原原版；保留原檔備份與安裝收據")
        return

    if current_hash != original_hash:
        if receipt_path.exists() and backup.exists():
            receipt = load_json(receipt_path)
            if (receipt.get("original_sha256") == original_hash and
                    current_hash == receipt.get("patched_sha256") and digest(backup.read_bytes()) == original_hash):
                if receipt.get("translation_sha256") == digest((ROOT / "zh-TW.json").read_bytes()):
                    print("目前已套用這份翻譯，無須重複套用")
                    return
                raise ValueError("譯文已變更；請先還原，再套用新版翻譯")
        raise ValueError("遊戲雜湊不符，未寫入任何遊戲檔案")
    result = build(data, baseline, args.font)
    if backup.exists():
        if digest(backup.read_bytes()) != original_hash:
            raise ValueError("備份目錄已有不同版本，拒絕覆蓋")
    else:
        write_exclusive(backup, data)
    receipt = {
        "original_sha256": original_hash,
        "patched_sha256": digest(result),
        "translation_sha256": digest((ROOT / "zh-TW.json").read_bytes()),
        "entries": baseline["entries"],
    }
    backup_dir.mkdir(parents=True, exist_ok=True)
    if receipt_path.exists():
        previous = load_json(receipt_path)
        if previous.get("original_sha256") != original_hash:
            raise ValueError("備份目錄安裝收據屬於其他版本")
        replace_checked(receipt_path, digest(receipt_path.read_bytes()), (json.dumps(receipt, indent=2) + "\n").encode())
    else:
        write_exclusive(receipt_path, (json.dumps(receipt, indent=2) + "\n").encode())
    replace_checked(exe, current_hash, result)
    print("已套用繁體中文；啟動遊戲後，在語言選單選擇「繁體中文」")
    print(f"原版備份：{backup}\n補丁 SHA-256：{digest(result)}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, ImportError) as error:
        print(f"停止：{error}", file=sys.stderr)
        sys.exit(1)
