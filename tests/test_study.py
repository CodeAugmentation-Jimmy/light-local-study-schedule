"""使用临时记录文件检查计时逻辑，不改动真实学习数据。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch


SOURCE = next(Path(__file__).resolve().parents[1].glob("*.py"))
spec = importlib.util.spec_from_file_location("study", SOURCE)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(study, "DATA_FILE", Path(self.folder.name) / "data.json")
        self.path_patch.start()
        self.clock = 100.0
        self.wall = study.datetime(2026, 10, 27, 12).timestamp()
        self.monotonic_patch = patch.object(study.time, "monotonic", side_effect=lambda: self.clock)
        self.wall_patch = patch.object(study.time, "time", side_effect=lambda: self.wall)
        self.monotonic_patch.start()
        self.wall_patch.start()
        class FixedDate(study.date):
            @classmethod
            def today(cls):
                return cls(2026, 10, 27)
        self.date_patch = patch.object(study, "date", FixedDate)
        self.date_patch.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = study.StudyApp(self.root)
        self.app.items = [{"id": "math", "name": "Math", "goal": 1, "schedule": {"mode": "daily"}, "records": {}}]
        self.app.refresh()
        self.app.table.selection_set("math")

    def tearDown(self):
        self.app.close()
        self.monotonic_patch.stop()
        self.wall_patch.stop()
        self.date_patch.stop()
        self.path_patch.stop()
        self.folder.cleanup()

    def advance(self, seconds):
        self.clock += seconds
        self.wall += seconds

    def test_pause_resume_and_automatic_save(self):
        self.app.start()
        self.advance(12)
        self.app.toggle_pause()
        self.advance(90)
        self.app.record_elapsed()
        self.assertAlmostEqual(self.app.session_seconds, 12)
        self.app.toggle_pause()
        self.advance(35)
        self.root.after_cancel(self.app.after_id)
        self.app.tick()
        self.assertAlmostEqual(self.app.session_seconds, 47)
        saved = json.loads(study.DATA_FILE.read_text(encoding="utf-8"))
        self.assertAlmostEqual(sum(saved[0]["records"].values()), 47)
        self.app.stop()
        self.assertEqual(self.app.session_seconds, 0)
        self.assertAlmostEqual(sum(self.app.items[0]["records"].values()), 47)

    def test_midnight_split(self):
        self.wall = study.datetime(2026, 10, 27, 23, 59, 50).timestamp()
        self.app.start()
        self.advance(25)
        self.app.stop()
        self.assertEqual(self.app.items[0]["records"], {"2026-10-27": 10, "2026-10-28": 15})

    def test_wall_clock_change_does_not_add_learning_time(self):
        self.app.start()
        self.advance(10)
        self.wall += 3600
        self.app.stop()
        self.assertAlmostEqual(sum(self.app.items[0]["records"].values()), 10)

    def test_refresh_preserves_selection_and_caps_progress(self):
        today = study.date.today().isoformat()
        self.app.items[0]["records"][today] = 120
        self.app.items.append({"id": "english", "name": "English", "goal": 1, "records": {today: 30}})
        self.app.refresh()
        self.assertEqual(self.app.table.selection(), ("math",))
        self.assertEqual(float(self.app.progress["value"]), 75)

    def test_legacy_data_loads(self):
        self.app.save_data()
        expected = self.app.items.copy()
        self.app.items = []
        self.app.load_data()
        self.assertEqual(self.app.items, expected)

    def test_completion_reminder_only_once(self):
        with patch.object(self.root, "bell") as bell:
            self.app.start()
            self.advance(61)
            self.app.record_elapsed()
            self.advance(5)
            self.app.record_elapsed()
            self.app.refresh()
            self.assertEqual(bell.call_count, 1)
            self.assertEqual(float(self.app.progress["value"]), 100)
            self.assertTrue(self.app.running_id)

    def test_sync_merges_phone_time_and_remote_delete_stops_timer(self):
        from lan_sync import Ledger
        self.app.start()
        self.advance(20)
        self.app.record_elapsed()
        self.app.save_data()
        phone = Ledger('phone')
        phone.merge(self.app.ledger.document)
        items = phone.active()
        items[0]['records']['2026-10-27'] += 40
        phone.capture(items)
        self.app.exchange(phone.document)
        self.assertAlmostEqual(self.app.items[0]['records']['2026-10-27'], 60)
        self.assertEqual(self.app.running_id, 'math')
        phone.capture([])
        self.app.exchange(phone.document)
        self.assertFalse(self.app.items)
        self.assertIsNone(self.app.running_id)

    def test_focus_limit_and_resume_preserve_manual_pause(self):
        self.app.apply_preferences(self.app.preferences | {"focus_minutes": 1})
        self.app.start()
        self.advance(20)
        self.app.toggle_pause()
        self.advance(90)
        self.app.toggle_pause()
        self.advance(60)
        self.app.record_elapsed()
        self.assertTrue(self.app.paused)
        self.assertEqual(self.app.session_seconds, 60)
        self.assertEqual(sum(self.app.items[0]["records"].values()), 60)
        self.advance(300)
        self.app.toggle_pause()
        self.advance(10)
        self.app.record_elapsed()
        self.assertEqual(self.app.session_seconds, 70)
        self.assertEqual(self.app.focus_end - self.app.session_seconds, 50)

    def test_focus_boundary_pause_does_not_resume(self):
        self.app.apply_preferences(self.app.preferences | {"focus_minutes": 1})
        self.app.start()
        self.advance(65)
        self.app.toggle_pause()
        self.assertTrue(self.app.paused)
        self.assertEqual(self.app.session_seconds, 60)

    def test_focus_midnight_and_free_mode(self):
        self.wall = study.datetime(2026, 10, 27, 23, 59, 30).timestamp()
        self.app.apply_preferences(self.app.preferences | {"focus_minutes": 1})
        self.app.start()
        self.advance(90)
        self.app.record_elapsed()
        self.assertEqual(self.app.items[0]["records"], {"2026-10-27": 30, "2026-10-28": 30})
        self.app.apply_preferences(self.app.preferences | {"focus_minutes": 0})
        self.app.toggle_pause()
        self.advance(120)
        self.app.record_elapsed()
        self.assertFalse(self.app.paused)
        self.assertEqual(self.app.session_seconds, 180)

    def test_minimized_policy_and_preference_persistence(self):
        self.app.start()
        with patch.object(self.root, "state", return_value="iconic"):
            self.advance(10)
            self.app.pause_if_minimized()
            self.assertFalse(self.app.paused)
            self.app.apply_preferences(self.app.preferences | {"background": False})
            self.assertTrue(self.app.paused)
            self.advance(100)
            self.app.record_elapsed()
            self.assertEqual(self.app.session_seconds, 10)
        saved = study.load_preferences(study.DATA_FILE.with_name("桌面设置.json"))
        self.assertFalse(saved["background"])
        self.app.pause_if_minimized()
        self.assertTrue(self.app.paused)
        self.app.toggle_pause()
        self.advance(5)
        self.app.record_elapsed()
        self.assertEqual(self.app.session_seconds, 15)

    def test_new_windows_and_layout(self):
        self.root.deiconify()
        self.root.geometry("900x680")
        self.root.update()
        for widget in (self.app.start_button, self.app.stop_button, self.app.options_text, self.app.save_status, self.app.table):
            self.assertGreater(widget.winfo_height(), 0)
            self.assertLessEqual(widget.winfo_rooty() - self.root.winfo_rooty() + widget.winfo_height(), self.root.winfo_height())
            self.assertLessEqual(widget.winfo_rootx() - self.root.winfo_rootx() + widget.winfo_width(), self.root.winfo_width())
        mini = self.app.show_mini()
        self.app.start()
        self.advance(10)
        self.app.record_elapsed()
        self.app.refresh()
        self.assertEqual(self.app.mini_timer.cget("text"), "00:00:10")
        self.app.mini_pause.invoke()
        self.assertTrue(self.app.paused)
        mini.destroy()
        self.app.refresh()
        stats = self.app.show_statistics()
        stats.update_idletasks()
        stats.destroy()
        settings = self.app.show_settings()
        settings.destroy()
        self.root.withdraw()

    def test_sidebar_switches_pages_inside_main_window(self):
        self.root.deiconify()
        self.root.update()
        windows_before = {str(child) for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)}
        self.app.start()
        for key in ("calendar", "statistics", "sync", "settings", "calendar"):
            self.app.navigation_buttons[key].invoke()
            self.root.update_idletasks()
            self.assertEqual(self.app.current_page, key)
            self.assertIs(self.app.page_frame.winfo_toplevel(), self.root)
            self.assertTrue(self.app.page_frame.winfo_viewable())
            self.assertFalse(self.app.dashboard.winfo_viewable())
            self.assertEqual(self.app.navigation_buttons[key].cget("style"), "ActiveNav.TButton")
            windows_after = {str(child) for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)}
            self.assertEqual(windows_after, windows_before)
            self.advance(5)
            self.app.record_elapsed()
        self.app.navigation_buttons["home"].invoke()
        self.root.update_idletasks()
        self.assertEqual(self.app.current_page, "home")
        self.assertTrue(self.app.dashboard.winfo_viewable())
        self.assertIsNone(self.app.page_frame)
        self.assertEqual(self.app.table.selection(), ("math",))
        self.assertEqual(self.app.session_seconds, 25)
        self.assertFalse(self.app.paused)
        self.assertEqual(self.app.timer_text.cget("text"), "00:00:25")
        self.root.withdraw()

    def test_embedded_settings_save_stays_on_page(self):
        page = self.app.show_settings()
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        save = next(widget for widget in descendants(page)
                    if isinstance(widget, study.ttk.Button) and widget.cget("text") == "保存设置")
        save.invoke()
        self.assertTrue(page.winfo_exists())
        self.assertEqual(self.app.current_page, "settings")
        self.assertTrue(study.DATA_FILE.with_name("桌面设置.json").exists())

    def test_calendar_filter_progress_and_switch(self):
        self.app.items[0]["schedule"] = {"mode": "odd"}
        self.app.items[0]["records"] = {"2026-10-27": 60}
        self.app.items.append({"id": "english", "name": "English", "goal": 1, "schedule": {"mode": "even"}, "records": {}})
        self.app.refresh()
        self.assertEqual(self.app.table.get_children(), ("math",))
        self.assertEqual(float(self.app.progress["value"]), 100)
        self.app.show_all_courses.set(True); self.app.refresh()
        self.assertEqual(len(self.app.table.get_children()), 2)
        self.app.table.selection_set("english"); self.app.update_controls()
        self.assertTrue(self.app.start_button.instate(["disabled"]))
        with patch.object(study.messagebox, "showinfo"):
            self.app.start()
        self.assertIsNone(self.app.running_id)
        class NextDay(study.date):
            @classmethod
            def today(cls): return cls(2026, 10, 28)
        self.app.show_all_courses.set(False)
        with patch.object(study, "date", NextDay):
            self.app.refresh()
            self.assertEqual(self.app.table.get_children(), ("english",))
            self.assertEqual(float(self.app.progress["value"]), 0)
        self.app.show_calendar().destroy()

    def test_calendar_midnight_pauses_without_extra_time(self):
        self.app.items[0]["schedule"] = {"mode": "odd"}
        self.wall = study.datetime(2026, 10, 27, 23, 59, 50).timestamp()
        self.app.start()
        self.advance(25)
        class NextDay(study.date):
            @classmethod
            def today(cls): return cls(2026, 10, 28)
        with patch.object(study, "date", NextDay):
            self.app.record_elapsed(); self.app.refresh()
            self.assertEqual(self.app.session_seconds, 10)
            self.assertEqual(self.app.items[0]["records"], {"2026-10-27": 10})
            self.assertTrue(self.app.paused)
            self.assertEqual(self.app.table.get_children(), ())
            with patch.object(study.messagebox, "showinfo"):
                self.app.toggle_pause()
            self.assertTrue(self.app.paused)

    def test_schedule_edit_and_remote_rule_pause(self):
        self.app.start(); self.advance(15)
        self.app.apply_schedule("math", {"mode": "even"})
        self.assertTrue(self.app.paused)
        self.assertEqual(self.app.items[0]["records"], {"2026-10-27": 15})
        self.app.apply_schedule("math", {"mode": "odd"})
        self.app.toggle_pause(); self.advance(5)
        from lan_sync import Ledger
        phone = Ledger("phone", self.app.ledger.stored())
        items = phone.active(); items[0]["schedule"] = {"mode": "even"}; phone.capture(items)
        self.app.exchange(phone.document)
        self.assertTrue(self.app.paused)
        self.assertEqual(self.app.items[0]["records"]["2026-10-27"], 20)

    def test_schedule_migration_backup(self):
        legacy = [{"id": "math", "name": "Math", "goal": 1, "records": {"2026-10-27": 12}}]
        original = json.dumps(legacy).encode("utf-8")
        study.DATA_FILE.write_bytes(original)
        self.app.load_data(); self.app.save_data()
        self.assertEqual(study.DATA_FILE.with_name("学习记录.1.2升级备份.json").read_bytes(), original)
        self.assertEqual(self.app.items[0]["schedule"], {"mode": "daily"})
        self.assertEqual(self.app.items[0]["records"], legacy[0]["records"])


if __name__ == "__main__":
    unittest.main()
