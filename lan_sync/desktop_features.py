"""Local desktop preferences and reports; the LAN protocol stays unchanged."""
import csv
import json
import os
from datetime import timedelta


DEFAULTS = {"focus_minutes": 0, "background": True, "sound": True, "topmost": False}


def load_preferences(path):
    if not path.exists():
        return DEFAULTS.copy()
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("桌面设置格式错误")
    result = DEFAULTS | {key: value[key] for key in DEFAULTS if key in value}
    minutes = result["focus_minutes"]
    if type(minutes) is not int or not 0 <= minutes <= 180:
        raise ValueError("专注时长须为 0 至 180 的整数")
    if any(type(result[key]) is not bool for key in ("background", "sound", "topmost")):
        raise ValueError("桌面开关设置格式错误")
    return result


def save_preferences(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def statistics(items, today, days=7):
    first = today - timedelta(days=days - 1)
    totals = {}
    for item in items:
        for day, seconds in item["records"].items():
            totals[day] = totals.get(day, 0) + seconds
    daily = [((first + timedelta(days=i)).isoformat(), totals.get((first + timedelta(days=i)).isoformat(), 0)) for i in range(days)]
    cursor = today if totals.get(today.isoformat(), 0) > 0 else today - timedelta(days=1)
    streak = 0
    while totals.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)
    categories = [(item["name"], sum(seconds for day, seconds in item["records"].items() if first.isoformat() <= day <= today.isoformat())) for item in items]
    categories.sort(key=lambda row: row[1], reverse=True)
    return {"daily": daily, "categories": categories, "total": sum(row[1] for row in daily),
            "studied_days": sum(seconds > 0 for _, seconds in daily), "streak": streak}


def export_csv(path, items, start=None, end=None):
    rows = sorted((day, item["name"], seconds) for item in items for day, seconds in item["records"].items()
                  if seconds > 0 and (start is None or day >= start) and (end is None or day <= end))
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["日期", "学习类目", "学习秒数", "学习分钟数"])
        for day, name, seconds in rows:
            # Prevent category names from becoming formulas when opened in Excel.
            safe_name = "'" + name if name.lstrip().startswith(("=", "+", "-", "@")) or name.startswith(("\t", "\r", "\n")) else name
            writer.writerow([day, safe_name, round(seconds, 3), round(seconds / 60, 3)])
    return len(rows)
