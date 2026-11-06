import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from lan_sync.storage import data_directory, import_legacy


class StorageTests(unittest.TestCase):
    def test_frozen_data_uses_user_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {'LOCALAPPDATA': folder}):
                self.assertEqual(data_directory(), Path(folder) / 'StudySchedule')

    def test_migration_preserves_records_and_pairing_without_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'old'; source.mkdir()
            destination = Path(folder) / 'new'
            original = [{'id': 'math', 'name': 'Math', 'goal': 30, 'records': {'2026-10-27': 123}}]
            original_bytes = json.dumps(original).encode('utf-8')
            (source / '学习记录.json').write_bytes(original_bytes)
            settings = {'device': 'a' * 32, 'token': 'ABCDEF123456'}
            (source / '同步设置.json').write_text(json.dumps(settings), encoding='utf-8')
            import_legacy(source, destination)
            data = json.loads((destination / '学习记录.json').read_text(encoding='utf-8'))
            self.assertEqual(data[0]['records'], original[0]['records'])
            self.assertEqual(json.loads((destination / '同步设置.json').read_text(encoding='utf-8')), settings)
            self.assertEqual((source / '学习记录.json').read_bytes(), original_bytes)
            saved = (destination / '学习记录.json').read_bytes()
            with self.assertRaises(FileExistsError): import_legacy(source, destination)
            self.assertEqual((destination / '学习记录.json').read_bytes(), saved)

    def test_invalid_migration_keeps_destination_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'old'; source.mkdir()
            (source / '学习记录.json').write_text('not json', encoding='utf-8')
            destination = Path(folder) / 'new'
            with self.assertRaises(ValueError): import_legacy(source, destination)
            self.assertFalse((destination / '学习记录.json').exists())
