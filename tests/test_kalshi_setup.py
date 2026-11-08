import tempfile
import unittest
from pathlib import Path
from dotenv import dotenv_values

from scripts.configure_kalshi import configure


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.env=self.root/'.env'
        self.env.write_text('EXISTING=value\n')
        self.id=self.root/'api-key-id'
        self.id.write_text('12345678-1234-1234-1234-123456789abc\n')
        self.key=self.root/'key.txt'
        self.key.write_text('private-key placeholder, never read by migration')

    def test_adds_only_new_settings_and_protects_backup(self):
        backup=configure(self.env,self.id,self.key)
        self.assertEqual(backup.read_text(),'EXISTING=value\n')
        content=self.env.read_text()
        self.assertIn('EXISTING=value\n',content)
        self.assertEqual(dotenv_values(self.env)['KALSHI_API_KEY_ID'],'12345678-1234-1234-1234-123456789abc')
        self.assertNotIn('private-key placeholder',content)

    def test_conflict_preserves_original_env(self):
        self.env.write_text('KALSHI_API_KEY_ID=different\n')
        with self.assertRaises(ValueError):
            configure(self.env,self.id,self.key)
        self.assertEqual(self.env.read_text(),'KALSHI_API_KEY_ID=different\n')

    def test_rerun_is_noop(self):
        configure(self.env,self.id,self.key)
        content=self.env.read_bytes()
        self.assertIsNone(configure(self.env,self.id,self.key))
        self.assertEqual(self.env.read_bytes(),content)
