import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from test_core import evidence

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / '.agents/skills/term-history/scripts/term_history.py'


class CliReportTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CLI.exists(), 'CLI 尚未实现')
        self.temp = tempfile.TemporaryDirectory(prefix='溯源-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        result = self.call('init', '测试词', '--meaning', '测试含义', '--root', str(self.root))
        self.run = Path(json.loads(result.stdout)['path'])

    def call(self, *args, ok=True):
        result = subprocess.run([sys.executable, '-X', 'utf8', str(CLI), *args],
                                capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
        self.assertEqual(result.returncode, 0 if ok else 2, result.stderr + result.stdout)
        return result

    def payload(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return str(path)

    def record(self, kind, data, ok=True):
        return self.call('record', str(self.run), '--kind', kind, '--input', self.payload('input.json', data), ok=ok)

    def test_end_to_end_evidence_report_resume(self):
        self.record('evidence', evidence())
        self.record('conclusion', dict(summary='有限证据的调查结果', earliest_ids=['E001'],
                    timeline=[dict(date='2001-02-03', text='原文中的使用', evidence_ids=['E001'])]))
        self.call('finish', str(self.run), '--reason', '本轮完成')
        self.call('render', str(self.run))
        report = (self.run.parent / 'report.md').read_text(encoding='utf-8')
        self.assertIn('2001-02-03', report)
        self.assertIn('https://example.org/original', report)
        self.assertIn('数据不足', report)
        self.call('resume', str(self.run))
        self.record('conclusion', dict(summary='继续核对后保持结论', earliest_ids=['E001']))
        data = json.loads(self.run.read_text(encoding='utf-8'))
        self.assertEqual(len(data['conclusions']), 2)
        self.assertEqual(len(data['evidence']), 1)

    def test_batch_record_failure_does_not_partially_save(self):
        self.record('evidence', [evidence(), evidence(url='invalid')], ok=False)
        self.assertEqual(json.loads(self.run.read_text(encoding='utf-8'))['evidence'], [])

    def test_unknown_references_are_rejected(self):
        self.record('conclusion', dict(summary='错误', timeline=[dict(date='2000', text='节点', evidence_ids=['E404'])]), ok=False)

    def test_import_keeps_raw_bytes_and_evidence(self):
        self.record('evidence', evidence())
        csv = self.root / '中文趋势.csv'
        raw = b'\xef\xbb\xbfdate,value\r\n2020-01-01,20\r\n2020-01-02,90\r\n2020-01-03,90\r\n'
        csv.write_bytes(raw)
        metadata = dict(term='测试词', source='演示数据', source_url='https://example.org/data',
                        metric='每日提及次数', region='测试区域', start='2020-01-01', end='2020-01-03', granularity='day')
        self.call('import-trends', str(self.run), str(csv), '--format', 'generic',
                  '--metadata', self.payload('metadata.json', metadata))
        self.call('render', str(self.run))
        data = json.loads(self.run.read_text(encoding='utf-8'))
        self.assertEqual(len(data['evidence']), 1)
        trend = data['trends'][0]
        self.assertEqual((self.run.parent / trend['raw_file']).read_bytes(), raw)
        self.assertEqual(trend['peak']['value'], 90)
        self.assertEqual(len(trend['peak']['periods']), 2)
        svg = self.run.parent / 'trends' / 'T001.svg'
        self.assertEqual(ET.parse(svg).getroot().tag, '{http://www.w3.org/2000/svg}svg')
        self.assertIn('2020-01-02', (self.run.parent / 'report.md').read_text(encoding='utf-8'))

    def test_no_data_report_has_no_chart(self):
        self.call('render', str(self.run))
        self.assertFalse((self.run.parent / 'trends').exists())
        self.assertIn('尚未确定', (self.run.parent / 'report.md').read_text(encoding='utf-8'))

    def test_invalid_json_has_friendly_error(self):
        path = self.root / 'bad.json'
        path.write_text('{', encoding='utf-8')
        result = self.call('record', str(self.run), '--kind', 'evidence', '--input', str(path), ok=False)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
