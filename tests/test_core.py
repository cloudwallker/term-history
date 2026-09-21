import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/term-history/scripts'
sys.path.insert(0, str(SCRIPTS))

try:
    import core
except ImportError:
    core = None


def evidence(**changes):
    item = dict(url='https://example.org/original', title='原始记录', excerpt='这里使用了测试词。',
                date='2001-02-03', date_kind='published', date_basis='原始帖时间及同期引用交叉核验',
                accessed_at='2026-09-21T10:00:00+08:00', meaning='测试含义', meaning_match=True,
                status='verified', kind='original', date_verified=True,
                verification_note='已打开原文，并核对同期引用。')
    item.update(changes)
    return item


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(core, '证据核心模块尚未实现')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = core.create_run(Path(self.temp.name), '测试词', '测试含义')

    def test_persist_and_append_are_lossless(self):
        core.add_evidence(self.run, evidence())
        core.save_run(self.run)
        loaded = core.load_run(self.run['_path'])
        self.assertEqual(loaded['evidence'][0]['id'], 'E001')
        self.assertEqual(loaded['term'], '测试词')
        core.add_evidence(loaded, evidence(url='https://example.org/other'))
        core.save_run(loaded)
        self.assertEqual(len(core.load_run(loaded['_path'])['evidence']), 2)

    def test_date_precision_and_invalid_calendar_dates(self):
        self.assertEqual(core.date_interval('2000'), ('2000-01-01', '2000-12-31'))
        self.assertEqual(core.date_interval('2000-02'), ('2000-02-01', '2000-02-29'))
        with self.assertRaises(ValueError):
            core.date_interval('2001-02-29')

    def test_modified_secondary_or_unverified_cannot_be_earliest(self):
        for changes in [dict(date_kind='modified'), dict(kind='search_snippet'),
                        dict(kind='repost'), dict(date_verified=False), dict(meaning_match=False)]:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    core.add_evidence(self.run, evidence(**changes))
        core.add_evidence(self.run, evidence(status='secondary', kind='repost'))
        self.assertEqual(core.earliest_candidates(self.run), [])

    def test_uncertain_intervals_keep_multiple_candidates(self):
        core.add_evidence(self.run, evidence(date='2000'))
        core.add_evidence(self.run, evidence(date='2000-06-01', url='https://example.org/2'))
        core.add_evidence(self.run, evidence(date='2001', url='https://example.org/3'))
        self.assertEqual(core.earliest_candidates(self.run), ['E001', 'E002'])

    def test_conclusion_versions_and_meaning(self):
        core.add_evidence(self.run, evidence())
        core.add_conclusion(self.run, dict(summary='目前证据', earliest_ids=['E001'], timeline=[], limitations=[], unresolved=[]))
        core.start_session(self.run)
        core.add_conclusion(self.run, dict(summary='再次核对', earliest_ids=['E001'], timeline=[], limitations=[], unresolved=[]))
        self.assertEqual([c['version'] for c in self.run['conclusions']], [1, 2])
        with self.assertRaises(ValueError):
            core.add_conclusion(self.run, dict(summary='错误引用', earliest_ids=['E999']))

    def test_earliest_cannot_omit_existing_earlier_evidence(self):
        core.add_evidence(self.run, evidence(date='1999'))
        core.add_evidence(self.run, evidence(date='2001', url='https://example.org/2'))
        with self.assertRaises(ValueError):
            core.add_conclusion(self.run, dict(summary='错误排序', earliest_ids=['E002']))

    def test_budget_and_resume(self):
        for i in range(18):
            core.add_log(self.run, dict(kind='search', query='测试词 ' + str(i), outcome='没有更早线索'))
        self.assertIn('search_limit', core.budget_status(self.run)['reasons'])
        core.start_session(self.run)
        self.assertEqual(core.budget_status(self.run)['searches'], 0)
        self.assertEqual(len(self.run['search_log']), 18)

    def test_bad_record_does_not_mutate_run(self):
        before = copy.deepcopy(self.run)
        with self.assertRaises(ValueError):
            core.add_evidence(self.run, evidence(url='javascript:alert(1)'))
        self.assertEqual(before, self.run)

    def test_load_rejects_future_schema(self):
        path = Path(self.run['_path'])
        data = json.loads(path.read_text(encoding='utf-8'))
        data['schema_version'] = 999
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            core.load_run(path)


if __name__ == '__main__':
    unittest.main()
