import csv
from datetime import date
from pathlib import Path
import tempfile
import unittest

from lan_sync.desktop_features import DEFAULTS, export_csv, load_preferences, save_preferences, statistics


class DesktopFeatureTests(unittest.TestCase):
    def test_statistics_boundaries_streak_and_empty(self):
        items = [{"name": "Math", "records": {"2026-10-20": 99, "2026-10-21": 90,
                  "2026-10-22": 40, "2026-10-25": 10, "2026-10-26": 20, "2026-10-27": 30, "2026-10-29": 900}},
                 {"name": "English", "records": {"2026-10-27": 50}}]
        result = statistics(items, date(2026, 10, 28))
        self.assertEqual(result["total"], 150)
        self.assertEqual(result["streak"], 3)
        self.assertEqual(result["studied_days"], 4)
        self.assertEqual(result["daily"][0][0], "2026-10-22")
        items[0]["records"]["2026-10-28"] = 5
        self.assertEqual(statistics(items, date(2026, 10, 28), 30)["streak"], 4)
        self.assertEqual(statistics(items, date(2026, 10, 28), 30)["total"], 344)
        self.assertEqual(statistics([], date(2026, 10, 28))["streak"], 0)

    def test_csv_range_unicode_and_formula_names(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.csv"
            items = [{"name": "英语,阅读", "records": {"2026-10-27": 90, "2026-10-28": 30}},
                     {"name": "=2+3", "records": {"2026-10-27": 60}}]
            self.assertEqual(export_csv(path, items, "2026-10-27", "2026-10-27"), 2)
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            with path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.reader(file))
            self.assertEqual(rows[1], ["2026-10-27", "'=2+3", "60", "1.0"])
            self.assertEqual(rows[2], ["2026-10-27", "英语,阅读", "90", "1.5"])

    def test_preferences_roundtrip_and_invalid_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            self.assertEqual(load_preferences(path), DEFAULTS)
            preferences = DEFAULTS | {"focus_minutes": 25, "background": False}
            save_preferences(path, preferences)
            self.assertEqual(load_preferences(path), preferences)
            bad = '{"focus_minutes": -1}'
            path.write_text(bad, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_preferences(path)
            self.assertEqual(path.read_text(encoding="utf-8"), bad)
