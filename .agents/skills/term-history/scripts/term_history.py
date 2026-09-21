#!/usr/bin/env python3
"""Local helpers for the term-history skill. No network, model API or dependencies."""
import argparse
import copy
import json
import shutil
import sys
from pathlib import Path

import core


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def parser():
    result = argparse.ArgumentParser(description='深度溯源：证据、趋势和中文报告的本地工具')
    commands = result.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='初始化调查')
    init.add_argument('term')
    init.add_argument('--meaning', required=True)
    init.add_argument('--alias', action='append', default=[])
    init.add_argument('--root', default=str(Path.cwd() / 'runs'))
    for name, help_text in [('resume', '开始新一轮调查并保留历史'), ('status', '查看预算、证据和待办'),
                            ('finish', '结束本轮'), ('render', '生成报告和曲线'), ('record', '批量追加证据、日志或结论'),
                            ('import-trends', '导入真实趋势 CSV')]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument('run', help='调查目录或 investigation.json 路径')
        if name == 'finish':
            command.add_argument('--reason', required=True)
        if name == 'record':
            command.add_argument('--kind', choices=['evidence', 'log', 'conclusion'], required=True)
            command.add_argument('--input', required=True, help='UTF-8 JSON 对象或数组文件')
        if name == 'import-trends':
            command.add_argument('csv')
            command.add_argument('--format', choices=['generic', 'google'], required=True)
            command.add_argument('--metadata', required=True, help='来源、指标、地域、覆盖范围等 JSON 文件')
    return result


def execute(args):
    if args.command == 'init':
        record = core.create_run(args.root, args.term, args.meaning, args.alias)
        return dict(run_id=record['run_id'], path=record['_path'], budget=core.budget_status(record))
    record = core.load_run(args.run)
    if args.command == 'status':
        return dict(run_id=record['run_id'], term=record['term'], meaning=record['meaning'],
                    budget=core.budget_status(record), evidence_count=len(record['evidence']),
                    earliest_candidates=core.earliest_candidates(record), trends=len(record['trends']),
                    conclusion=record['conclusions'][-1] if record['conclusions'] else None)
    if args.command == 'render':
        from report import render
        return dict(report=str(render(record)))
    if args.command == 'resume':
        core.start_session(record)
    elif args.command == 'finish':
        core.finish_session(record, args.reason)
    elif args.command == 'record':
        payload = read_json(args.input)
        items = payload if isinstance(payload, list) else [payload]
        if not items or not all(isinstance(item, dict) for item in items):
            raise ValueError('输入必须为 JSON 对象或非空对象数组')
        changed = copy.deepcopy(record)
        operation = {'evidence': core.add_evidence, 'log': core.add_log, 'conclusion': core.add_conclusion}[args.kind]
        for item in items:
            operation(changed, item)
        record = changed
    elif args.command == 'import-trends':
        from trends import parse_csv
        metadata = read_json(args.metadata)
        if not isinstance(metadata, dict) or metadata.get('term') != record['term']:
            raise ValueError('趋势 term 必须与当前调查词条一致；别称数据应单独建立调查')
        series = parse_csv(Path(args.csv), args.format, metadata)
        series['id'] = 'T%03d' % (len(record['trends']) + 1)
        # Append new files only. Failed concurrent saves cannot overwrite earlier raw data.
        relative = 'trends/' + series['id'] + '-raw.csv'
        target = Path(record['_path']).parent / relative
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            raise ValueError('原始数据目标已存在；请检查此前未完成的导入，禁止覆盖')
        with Path(args.csv).open('rb') as source, target.open('xb') as out:
            shutil.copyfileobj(source, out)
        series.update(raw_file=relative, imported_at=core.now())
        record['trends'].append(series)
        try:
            core.save_run(record)
        except Exception:
            target.unlink()
            raise
        return dict(path=record['_path'], series_id=series['id'], peak=series['peak'])
    core.save_run(record)
    return dict(path=record['_path'], revision=record['revision'], budget=core.budget_status(record))


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = parser().parse_args()
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('错误：' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
