import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.agents/skills/term-history/scripts'))
import core
from test_core import evidence


class RecordReloadTests(unittest.TestCase):
    def test_rebuild_derived_dates_after_manually_correcting_primary_date(self):
        with tempfile.TemporaryDirectory() as temp:
            record = core.create_run(temp, '测试词', '测试含义')
            core.add_evidence(record, evidence(date='2001'))
            core.add_evidence(record, evidence(date='2002'))
            core.save_run(record)
            path = Path(record['_path'])
            saved = json.loads(path.read_text(encoding='utf-8'))
            saved['evidence'][0]['date'] = '2003'
            path.write_text(json.dumps(saved), encoding='utf-8')
            loaded = core.load_run(path)
            self.assertEqual(core.earliest_candidates(loaded), ['E002'])
            self.assertEqual(loaded['evidence'][0]['date_start'], '2003-01-01')


if __name__ == '__main__':
    unittest.main()
