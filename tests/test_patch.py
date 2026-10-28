import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import patch
from tools.prepare import extract

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.source = {"example": "Deals {n} damage to %s"}
        self.target = {"example": "對%s造成{n}點傷害"}
        original = json.dumps(self.source).encode().ljust(180, b" ")
        self.data = b"PREFIX" + "简体中文".encode() + original + b"FONT" + b"END"
        self.baseline = {
            "entries": 1,
            "original_sha256": patch.digest(self.data),
            "original_size": len(self.data),
            "label_offset": 6,
            "json_offset": 18,
            "json_size": 180,
            "json_sha256": patch.digest(original),
            "font_offset": 198,
            "font_size": 4,
            "font_sha256": patch.digest(b"FONT"),
        }

    def apply(self, **overrides):
        arguments = dict(data=self.data, baseline=self.baseline, source=self.source, target=self.target, font=b"TT")
        arguments.update(overrides)
        return patch.make_patch(**arguments)

    def test_only_declared_ranges_change_and_json_padding_is_valid(self):
        result = self.apply()
        self.assertEqual(len(result), len(self.data))
        self.assertEqual(result[:6], b"PREFIX")
        self.assertEqual(result[6:18], "繁體中文".encode())
        self.assertEqual(json.loads(result[18:198]), self.target)
        self.assertEqual(result[198:202], b"TT\0\0")
        self.assertEqual(result[202:], b"END")

    def test_unknown_build_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "雜湊"):
            self.apply(data=self.data[:-1] + b"X")

    def test_payload_and_font_overflow_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "容量"):
            self.apply(target={"example": "繁" * 100 + "{n}%s"})
        with self.assertRaisesRegex(ValueError, "容量"):
            self.apply(font=b"TOOLONG")

    def test_missing_extra_empty_or_invalid_translation_is_rejected(self):
        for target in [{}, {**self.target, "extra": "多餘"}, {"example": ""}, {"example": "\0{n}%s"}]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.apply(target=target)

    def test_repeated_parameters_cannot_be_lost(self):
        with self.assertRaisesRegex(ValueError, "參數"):
            patch.validate_translation({"a": "{n} / {n}"}, {"a": "{n}"})

    def test_format_parameters_and_tags_are_preserved(self):
        for target in [{"example": "傷害{n}"}, {"example": "<b>{n}%s</b>"}]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.apply(target=target)

    def test_overlapping_ranges_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "範圍"):
            self.apply(baseline={**self.baseline, "font_offset": 190})

    def test_font_can_precede_language(self):
        data = b"PREFIXFONT" + self.data[6:198] + b"END"
        baseline = {**self.baseline, "original_sha256": patch.digest(data),
                    "label_offset": 10, "json_offset": 22, "font_offset": 6}
        result = self.apply(data=data, baseline=baseline)
        self.assertEqual(result[:6], b"PREFIX")
        self.assertEqual(result[6:10], b"TT\0\0")
        self.assertEqual(result[10:22], "繁體中文".encode())
        self.assertEqual(json.loads(result[22:202]), self.target)
        self.assertEqual(result[202:], b"END")

    def test_extract_lf_and_crlf(self):
        table = {"game.title": "測試", "line": "{n} 行"}
        for newline in ["\n", "\r\n"]:
            raw = json.dumps(table, ensure_ascii=False, indent=2).replace("\n", newline).encode()
            offset, actual, values = extract(b"English" + raw + b"\xff", "English")
            self.assertEqual(offset, 7)
            self.assertEqual(actual, raw)
            self.assertEqual(values, table)

    def test_extract_rejects_duplicate_marker_and_key(self):
        raw = b'English{\n  "game.title": "test"}'
        with self.assertRaisesRegex(ValueError, "unique"):
            extract(raw + raw, "English")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            extract(b'English{\n  "game.title": "a", "game.title": "b"}', "English")

    def test_installed_dictionary(self):
        source = patch.load_json(patch.ROOT / "en.json")
        target = patch.load_json(patch.ROOT / "zh-TW.json")
        patch.validate_translation(source, target)
        self.assertEqual(len(target), 3198)
        self.assertEqual(target["class.rogue.name"], "盜賊")
        self.assertEqual(target["race.troll.name"], "食人妖")
        self.assertEqual(target["race.gnome.name"], "地精")
        self.assertEqual(target["race.scourge.name"], "不死族")
        self.assertNotIn("擴音", "".join(target.values()))

    def test_apply_repeat_restore_and_refuse_unknown_files(self):
        FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="patch-", dir=FIXTURE_ROOT))
        for name, content in [("baseline.json", self.baseline), ("en.json", self.source), ("zh-TW.json", self.target)]:
            patch.write_exclusive(folder / name, json.dumps(content).encode())
        exe, backup = folder / "game" / "AzerothSurvivors.exe", folder / "backup"
        patch.write_exclusive(exe, self.data)
        result = self.apply()

        def run(action):
            with mock.patch.object(sys, "argv", ["patch.py", action, str(exe), str(backup)]):
                patch.main()

        with mock.patch.object(patch, "ROOT", folder), mock.patch.object(patch, "build", return_value=result):
            run("apply")
            self.assertEqual(exe.read_bytes(), result)
            self.assertEqual((backup / "AzerothSurvivors.exe.original").read_bytes(), self.data)
            run("apply")
            run("restore")
            self.assertEqual(exe.read_bytes(), self.data)
            run("restore")
            run("apply")
            exe.write_bytes(b"new game update")
            with self.assertRaisesRegex(ValueError, "收據"):
                run("restore")
            self.assertEqual(exe.read_bytes(), b"new game update")
            with self.assertRaisesRegex(ValueError, "雜湊"):
                run("apply")
            exe.write_bytes(self.data)
            (backup / "AzerothSurvivors.exe.original").write_bytes(b"damaged backup")
            with self.assertRaisesRegex(ValueError, "拒絕覆蓋"):
                run("apply")
            self.assertEqual(exe.read_bytes(), self.data)

    def test_replace_refuses_changed_destination(self):
        FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="replace-", dir=FIXTURE_ROOT))
        destination = folder / "game.exe"
        patch.write_exclusive(destination, b"game update")
        with self.assertRaisesRegex(ValueError, "已改變"):
            patch.replace_checked(destination, patch.digest(b"old game"), b"translation")
        self.assertEqual(destination.read_bytes(), b"game update")


if __name__ == "__main__":
    unittest.main()
