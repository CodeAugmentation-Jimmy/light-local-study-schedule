from copy import deepcopy
from datetime import date, timedelta
import unittest

from lan_sync import Ledger, merge_documents, validate_document
from lan_sync.schedule import is_due, next_date, validate_schedule


class CalendarTests(unittest.TestCase):
    def test_day_parity_month_year_and_leap_boundaries(self):
        odd = {"schedule": {"mode": "odd"}}
        even = {"schedule": {"mode": "even"}}
        for day, expected in (("2026-11-05", True), ("2026-11-06", False), ("2026-10-31", True),
                              ("2026-11-01", True), ("2028-02-29", True), ("2028-03-01", True),
                              ("2026-12-31", True), ("2027-01-01", True)):
            with self.subTest(day=day):
                self.assertEqual(is_due(odd, date.fromisoformat(day)), expected)
                self.assertEqual(is_due(even, date.fromisoformat(day)), not expected)
        self.assertEqual(next_date(even, date(2026, 10, 31)), date(2026, 11, 2))

    def test_weekdays_and_validation(self):
        item = {"schedule": {"mode": "weekdays", "days": [1, 3, 7]}}
        monday = date(2026, 11, 2)
        self.assertEqual([is_due(item, monday + timedelta(days=i)) for i in range(7)], [True, False, True, False, False, False, True])
        for rule in ({"mode": "weekdays", "days": []}, {"mode": "weekdays", "days": [0]},
                     {"mode": "weekdays", "days": [2, 1]}, {"mode": "weekdays", "days": [True]},
                     {"mode": "weekdays", "days": [1, 1]}, {"mode": "odd", "days": [1]}, {"mode": "unknown"}):
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                validate_schedule(rule)

    def test_legacy_upgrade_and_schedule_merge(self):
        legacy = [{"id": "math", "name": "Math", "goal": 30, "records": {"2026-11-05": 100}}]
        pc = Ledger("pc", legacy)
        self.assertEqual(pc.active()[0]["schedule"], {"mode": "daily"})
        phone = Ledger("phone", pc.stored())
        edited = phone.active(); edited[0]["schedule"] = {"mode": "even"}; phone.capture(edited)
        edited = pc.active(); edited[0]["records"]["2026-11-05"] += 20; pc.capture(edited)
        pc.merge(phone.document)
        self.assertEqual(pc.active()[0]["schedule"], {"mode": "even"})
        self.assertEqual(pc.active()[0]["records"]["2026-11-05"], 120)
        self.assertEqual(Ledger("pc", pc.stored()).document, pc.document)
        self.assertEqual(merge_documents(pc.document, phone.document), pc.document)
        edited = phone.active(); edited[0]["schedule"] = {"mode": "weekdays", "days": [1, 5]}; phone.capture(edited)
        edited = pc.active(); edited[0]["schedule"] = {"mode": "odd"}; pc.capture(edited)
        self.assertEqual(merge_documents(pc.document, phone.document), merge_documents(phone.document, pc.document))

    def test_old_protocol_and_invalid_schedule_rejected_without_mutation(self):
        pc = Ledger("pc", [{"id": "one", "name": "Course", "goal": 5, "records": {}}])
        before = deepcopy(pc.document)
        with self.assertRaisesRegex(ValueError, "1.2"):
            pc.merge({"protocol": 1, "items": []})
        self.assertEqual(pc.document, before)
        bad = deepcopy(before); bad["items"][0]["schedule"] = {"mode": "weekdays", "days": [9]}
        with self.assertRaises(ValueError):
            pc.merge(bad)
        self.assertEqual(pc.document, before)
