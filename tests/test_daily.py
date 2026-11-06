import plistlib
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from daily import collection_days, summarize_source, build_and_publish
from publish import collect_files


class DailyTests(unittest.TestCase):
    def test_weekday_schedule(self):
        config = plistlib.loads((ROOT / 'scripts/com.aiflow.site.plist').read_bytes())
        self.assertEqual(config['StartCalendarInterval'], [
            {'Weekday': d, 'Hour': 9, 'Minute': 30} for d in range(1, 6)])

    def test_monday_catches_weekend_with_overlap(self):
        now = datetime.fromisoformat('2026-11-09T09:30:00+08:00')
        self.assertEqual(collection_days(now, {'checked_at': '2026-11-06T09:30:00+08:00'}), 5)

    def test_missing_result_is_failure_except_empty_link_inbox(self):
        self.assertEqual(summarize_source('x', None, 1, [])['status'], 'failed')
        self.assertEqual(summarize_source('news', None, 0, [])['status'], 'failed')
        self.assertEqual(summarize_source('links', None, 0, [])['status'], 'empty')

    def test_child_feed_failure_is_not_full_success(self):
        row = summarize_source('news', {'items': [], 'coverage': [
            {'source': 'example', 'error': 'timeout'}]}, 0, [])
        self.assertEqual(row['status'], 'partial')

    def test_failed_checks_block_publish(self):
        with patch('daily.subprocess.run', side_effect=[None, subprocess.CalledProcessError(1, ['unittest'])]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                build_and_publish('example', datetime.fromisoformat('2026-11-06T09:30:00+08:00'))
        self.assertFalse(any('scripts/publish.py' in call.args[0] for call in run.call_args_list))

    def test_private_material_is_excluded_from_publication(self):
        for path in collect_files():
            self.assertFalse({'.private-inbox', 'logs', '__pycache__'} & set(path.relative_to(ROOT).parts))
