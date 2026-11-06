from copy import deepcopy
import http.client
import json
import threading
import unittest
from lan_sync import Ledger, SyncServer, merge_documents, validate_document


LEGACY = [{"id": "math", "name": "Math", "goal": 30, "records": {"2026-10-27": 100}}]


class SyncTests(unittest.TestCase):
    def test_offline_devices_add_and_repeated_sync_does_not_duplicate(self):
        pc = Ledger("pc", deepcopy(LEGACY))
        phone = Ledger("phone")
        phone.merge(pc.document)
        local = pc.active(); local[0]["records"]["2026-10-27"] += 20; pc.capture(local)
        local = phone.active(); local[0]["records"]["2026-10-27"] += 40; phone.capture(local)
        pc.merge(phone.document); phone.merge(pc.document)
        expected = deepcopy(pc.document)
        for _ in range(5):
            pc.merge(phone.document); phone.merge(pc.document)
        self.assertEqual(pc.document, expected)
        self.assertEqual(pc.active()[0]["records"]["2026-10-27"], 160)
        self.assertEqual(pc.document, phone.document)
        self.assertEqual(Ledger("pc", pc.stored()).document, pc.document)

    def test_delete_wins_over_offline_edit(self):
        pc = Ledger("pc", deepcopy(LEGACY))
        phone = Ledger("phone", pc.stored())
        pc.capture([])
        edited = phone.active(); edited[0]["name"] = "Offline edit"; phone.capture(edited)
        merged = merge_documents(pc.document, phone.document)
        self.assertTrue(merged["items"][0]["deleted"])
        self.assertEqual(merged, merge_documents(phone.document, pc.document))

    def test_concurrent_metadata_edits_converge_and_counters_survive(self):
        pc = Ledger("pc", deepcopy(LEGACY)); phone = Ledger("phone", pc.stored())
        edited = pc.active(); edited[0]["goal"] = 60; pc.capture(edited)
        edited = phone.active(); edited[0]["name"] = "Algebra"; phone.capture(edited)
        self.assertEqual(merge_documents(pc.document, phone.document), merge_documents(phone.document, pc.document))
        pc.merge(phone.document)
        self.assertEqual(pc.active()[0]["records"]["2026-10-27"], 100)

    def test_invalid_data_is_rejected_before_merge(self):
        pc = Ledger("pc", deepcopy(LEGACY))
        original = deepcopy(pc.document)
        corrupt = deepcopy(original); corrupt["items"][0]["counters"]["2026-10-27"]["legacy"] = float("nan")
        with self.assertRaises(ValueError): pc.merge(corrupt)
        self.assertEqual(pc.document, original)

    def test_http_pairing_and_end_to_end_merge(self):
        pc = Ledger("pc", deepcopy(LEGACY))
        def exchange(document):
            pc.merge(document)
            return deepcopy(pc.document)
        server = SyncServer("ABCDEF123456", exchange, host="127.0.0.1", port=0)
        server.start()
        def request(token, document):
            connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=3)
            try:
                connection.request("POST", "/sync", json.dumps(document), {"X-Study-Token": token, "Content-Type": "application/json"})
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()
        try:
            empty = {"protocol": 2, "items": []}
            self.assertEqual(request("WRONG", empty)[0], 401)
            status, payload = request("ABCDEF123456", empty)
            self.assertEqual(status, 200)
            phone = Ledger("phone"); phone.merge(payload)
            local = phone.active(); local[0]["records"]["2026-10-27"] += 50; phone.capture(local)
            self.assertEqual(request("ABCDEF123456", phone.document)[0], 200)
            self.assertEqual(request("ABCDEF123456", phone.document)[0], 200)
            self.assertEqual(pc.active()[0]["records"]["2026-10-27"], 150)
        finally:
            server.close()


if __name__ == "__main__":
    unittest.main()
