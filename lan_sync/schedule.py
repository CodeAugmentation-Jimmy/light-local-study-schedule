"""Calendar rules shared by persistence, today's course list and timers."""
from datetime import date, timedelta

MODES = {"daily": "每天", "odd": "单数日", "even": "双数日", "weekdays": "指定星期"}
WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def validate_schedule(rule):
    if not isinstance(rule, dict) or rule.get("mode") not in MODES:
        raise ValueError("课程安排类型有误")
    if rule["mode"] == "weekdays":
        days = rule.get("days")
        if not isinstance(days, list) or not days or any(type(day) is not int or not 1 <= day <= 7 for day in days) or days != sorted(set(days)):
            raise ValueError("指定星期须选择至少一天，按周一至周日排列且不重复")
        if set(rule) != {"mode", "days"}:
            raise ValueError("课程安排字段有误")
    elif set(rule) != {"mode"}:
        raise ValueError("课程安排字段有误")
    return rule


def is_due(item, day):
    rule = item.get("schedule", {"mode": "daily"})
    mode = rule["mode"]
    return (mode == "daily" or mode == "odd" and day.day % 2 == 1 or
            mode == "even" and day.day % 2 == 0 or mode == "weekdays" and day.isoweekday() in rule["days"])


def schedule_label(item):
    rule = item.get("schedule", {"mode": "daily"})
    return "、".join(WEEKDAYS[day - 1] for day in rule["days"]) if rule["mode"] == "weekdays" else MODES[rule["mode"]]


def next_date(item, start):
    for offset in range(8):
        candidate = start + timedelta(days=offset)
        if is_due(item, candidate):
            return candidate
    return None
