import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asset_patch as assets
from vendor.mpq.reader import Archive
from vendor.mpq.writer import write_archive


class AssetTests(unittest.TestCase):
    def test_reported_screenshot_tooltips_are_translated(self):
        database = json.loads((assets.ROOT / "assets-zh-TW.json").read_text(encoding="utf-8"))
        ui = database["files"][r"Interface\FrameXML\GlobalStrings.lua"]["translations"]
        self.assertEqual(ui.get("CONTESTED_TERRITORY", {}).get("target"), "爭奪中的領土")
        self.assertEqual(ui.get("NEWBIE_TOOLTIP_CHARACTER", {}).get("target"), "你的角色資訊，包括裝備、屬性、技能與聲望。")
        for suffix, unit in [("SEC", "秒"), ("MIN", "分"), ("HOURS", "小時"), ("DAYS", "天")]:
            for plural in ["", "_P1"]:
                item = ui.get("SPELL_TIME_REMAINING_" + suffix + plural, {})
                self.assertEqual(item.get("target"), "剩餘 %d " + unit)
                self.assertTrue(assets.compatible(item["source"], item["target"]))

    def test_map_markers_and_area_names_are_consistent(self):
        database = json.loads((assets.ROOT / "assets-zh-TW.json").read_text(encoding="utf-8"))
        area = database["files"][r"DBFilesClient\AreaTable.dbc"]["translations"]["11"]
        poi = database["files"].get(r"DBFilesClient\AreaPOI.dbc", {}).get("translations", {}).get("10", {})
        self.assertEqual(poi.get("Raven Hill"), "烏鴉嶺")
        self.assertEqual(poi["Raven Hill"], area["Raven Hill"])

    def test_wow_references_end_before_punctuation(self):
        self.assertTrue(assets.compatible("Increases damage by $s1% for $d.", "傷害提高$s1%，持續$d。"))
        self.assertFalse(assets.compatible("Deals $s1 damage.", "造成$s2點傷害。"))

    def test_positional_parameters_keep_argument_identity(self):
        self.assertTrue(assets.compatible("%s gains %d health.", "%1$s恢復%2$d點生命值。"))
        self.assertFalse(assets.compatible("%s gains %d health.", "%2$s恢復%1$d點生命值。"))
        self.assertFalse(assets.compatible("%s hits %s.", "%s命中。"))

    def test_numbers_cannot_change(self):
        self.assertTrue(assets.compatible("100% damage", "100%傷害"))
        self.assertFalse(assets.compatible("Deals 10 damage over 5 sec.", "在5秒內造成20點傷害。"))

    def test_percent_units_and_time_parameters_cannot_disappear(self):
        self.assertFalse(assets.compatible("Chance increased by $s1%.", "機率提高$s1。"))
        self.assertTrue(assets.compatible("Chance increased by $s1%.", "機率提高$s1%。"))
        self.assertFalse(assets.compatible("%I:%M %p", "%I:%M"))

    def test_lua_changes_only_known_literals_and_escapes_quotes(self):
        source = b'LABEL = "Hello %s"; -- keep\nOTHER = "original";\n'
        output, count = assets.patch_lua(source, {"LABEL": {"source": "Hello %s", "target": '你好「%s」"'}})
        self.assertEqual(count, 1)
        self.assertIn(b'-- keep\nOTHER = "original";', output)
        self.assertIn(b'\\"', output)
        self.assertEqual(assets.lua_decode(assets.ASSIGN.search(output.decode())[2]), '你好「%s」"')

    def test_protected_commands_and_confirm_tokens_are_rejected(self):
        for key in ["SLASH_SAY1", "EMOTE1_CMD1", "DELETE_ITEM_CONFIRM_STRING"]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                assets.patch_lua(f'{key} = "DELETE";'.encode(), {key: {"source": "DELETE", "target": "刪除"}})

    def test_dbc_preserves_numeric_fields_and_original_pool(self):
        pool = b"\0Spell\0Other\0"
        raw = struct.pack("<4s4I", b"WDBC", 2, 3, 12, len(pool)) + struct.pack("<6I", 100, 1, 999, 200, 7, 777) + pool
        output, count = assets.patch_dbc(raw, 3, {"1": {"Spell": "法術"}})
        self.assertEqual(count, 1)
        self.assertEqual(struct.unpack_from("<I", output, 20)[0], 100)
        self.assertEqual(output[28:44], raw[28:44])
        self.assertEqual(output[44:len(raw)], pool)
        new_offset = struct.unpack_from("<I", output, 24)[0]
        self.assertEqual(output[44 + new_offset:], "法術\0".encode())
        with self.assertRaises(ValueError):
            assets.patch_dbc(raw, 4, {"1": {"Spell": "法術"}})

    def test_xml_escapes_translated_text(self):
        raw = b'<Ui><FontString text="Name &amp; Title"/></Ui>'
        output, count = assets.patch_xml(raw, {"Name & Title": "名稱與頭銜"})
        self.assertEqual(count, 1)
        self.assertIn("名稱與頭銜".encode(), output)

    def test_mpq_roundtrip_and_hash_case(self):
        files = {r"Interface\FrameXML\GlobalStrings.lua": b'LABEL = "test";', r"DBFilesClient\Test.dbc": bytes(range(256)) * 40}
        archive = Archive(write_archive(files))
        for name, data in files.items():
            self.assertEqual(archive.read(name.lower()), data)

    def test_overlay_install_repeat_restore_and_foreign_file_refusal(self):
        import patch
        parent = Path(__file__).resolve().parent / "fixtures"
        parent.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="assets-", dir=parent))
        game, backup = root / "game", root / "backup"
        original = b"supported game"
        patch.write_exclusive(game / "AzerothSurvivors.exe", original)
        patch.write_exclusive(root / "baseline.json", json.dumps({"original_sha256": patch.digest(original)}).encode())
        patch.write_exclusive(root / "assets-zh-TW.json", b'{}')
        overlay = write_archive({"test.txt": "中文".encode()})
        with mock.patch.object(assets, "ROOT", root), mock.patch.object(assets, "build_overlay", return_value=(overlay, {"test.txt": 1})):
            assets.install_overlay(game, backup, root / "unused-font")
            target = game / "Data" / assets.OVERLAY_NAME
            self.assertEqual(target.read_bytes(), overlay)
            assets.install_overlay(game, backup, root / "unused-font")
            assets.restore_overlay(game, backup)
            self.assertFalse(target.exists())
            self.assertEqual((game / "AzerothSurvivors.exe").read_bytes(), original)
            target.write_bytes(b"someone else's overlay")
            with self.assertRaisesRegex(ValueError, "拒絕覆蓋"):
                assets.install_overlay(game, backup, root / "unused-font")
            with self.assertRaisesRegex(ValueError, "拒絕刪除"):
                assets.restore_overlay(game, backup)
            self.assertEqual(target.read_bytes(), b"someone else's overlay")


if __name__ == "__main__":
    unittest.main()
