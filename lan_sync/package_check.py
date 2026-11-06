"""Smoke check the frozen program in temporary storage, including LAN requests."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import traceback

from . import Ledger, SyncServer


def run_check(module, report_path):
    report = {"ok": False}
    root = None
    app = None
    try:
        with tempfile.TemporaryDirectory(prefix="StudySchedule-check-") as directory:
            module.DATA_FILE = Path(directory) / "学习记录.json"
            root = module.tk.Tk()
            root.withdraw()
            app = module.StudyApp(root)
            app.name.insert(0, "打包检查")
            app.minutes.insert(0, "1")
            app.add_item()
            identifier = app.items[0]["id"]
            app.table.selection_set(identifier)
            app.start()
            app.last_tick -= 65
            app.stop()
            assert sum(app.items[0]["records"].values()) >= 65
            phone = Ledger("package_phone")
            phone.merge(app.ledger.document)
            active = phone.active()
            today = module.date.today().isoformat()
            active[0]["records"][today] = active[0]["records"].get(today, 0) + 30
            active[0]["schedule"] = {"mode": "weekdays", "days": [1, 2, 3, 4, 5, 6, 7]}
            phone.capture(active)
            server = SyncServer(app.sync_settings["token"], app.queue_exchange, host="127.0.0.1", port=0)
            app.sync_server = server
            server.start()
            response = {}
            def request():
                connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=8)
                try:
                    connection.request("POST", "/sync", json.dumps(phone.document), {"X-Study-Token": app.sync_settings["token"]})
                    result = connection.getresponse()
                    response["status"] = result.status
                    response["body"] = json.loads(result.read())
                except Exception:
                    response["error"] = traceback.format_exc()
                finally:
                    connection.close()
            thread = threading.Thread(target=request)
            thread.start()
            deadline = time.monotonic() + 10
            while thread.is_alive() and time.monotonic() < deadline:
                root.update()
                time.sleep(.02)
            thread.join(timeout=1)
            assert response.get("status") == 200, response
            assert sum(app.items[0]["records"].values()) >= 95
            assert app.items[0]["schedule"]["mode"] == "weekdays"
            assert app.save_data()
            app.items = []
            app.load_data()
            assert app.items[0]["name"] == "打包检查"
            app.apply_preferences(app.preferences | {"focus_minutes": 1})
            app.start()
            app.last_tick -= 80
            app.record_elapsed()
            assert app.paused and app.session_seconds == 60
            app.show_mini().withdraw()
            app.show_statistics().destroy()
            csv_path = Path(directory) / "report.csv"
            assert module.export_csv(csv_path, app.items) > 0
            assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
            app.stop()
            app.apply_schedule(identifier, {"mode": "even" if module.date.today().day % 2 else "odd"})
            assert identifier not in app.table.get_children()
            app.show_all_courses.set(True); app.refresh()
            assert identifier in app.table.get_children()
            app.show_calendar().destroy()
            before = [child for child in root.winfo_children() if isinstance(child, module.tk.Toplevel)]
            for key in ("calendar", "statistics", "sync", "settings", "home"):
                app.navigation_buttons[key].invoke()
                assert app.current_page == key
            after = [child for child in root.winfo_children() if isinstance(child, module.tk.Toplevel)]
            assert after == before
            app.table.selection_set(identifier)
            app.edit_schedule().destroy()
            report = {"ok": True, "checks": ["Tk interface", "add category", "timer completion", "authenticated LAN schedule sync", "save and reload", "focus auto-pause", "mini timer", "statistics page", "CSV export", "calendar filtering", "14-day calendar preview", "embedded sidebar navigation"], "frozen": bool(getattr(module.sys, "frozen", False))}
            app.close()
            app = None
            root = None
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if app is not None:
            app.close()
        elif root is not None:
            root.destroy()
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["ok"]:
        raise SystemExit(1)
