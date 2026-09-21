"""Append-only investigation records. Python 3.9+, standard library only."""
import calendar
import copy
import json
import os
import re
import tempfile
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + ' 必须是非空文本')
    return value.strip()


def timestamp(value):
    parsed = datetime.fromisoformat(text(value, '时间').replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('访问／会话时间必须包含时区')
    return parsed


def web_url(value):
    value = text(value, 'URL')
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.hostname or any(c.isspace() for c in value):
        raise ValueError('URL 必须是完整的 HTTP(S) 地址')
    return value


def date_interval(value):
    value = text(value, '日期')
    if not re.fullmatch(r'\d{4}(?:-\d{2})?(?:-\d{2})?', value):
        raise ValueError('日期应为 YYYY、YYYY-MM 或 YYYY-MM-DD')
    parts = [int(x) for x in value.split('-')]
    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    start = date(year, month, parts[2] if len(parts) > 2 else 1)
    if len(parts) == 1:
        end = date(year, 12, 31)
    elif len(parts) == 2:
        end = date(year, month, calendar.monthrange(year, month)[1])
    else:
        end = start
    return start.isoformat(), end.isoformat()


def _strings(value, name):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(name + ' 必须是非空文本组成的数组（可为空数组）')
    return list(value)


def validate_evidence(item):
    clean = copy.deepcopy(item)
    for field in ('title', 'excerpt', 'date_basis', 'meaning', 'verification_note'):
        clean[field] = text(clean.get(field), field)
    clean['url'] = web_url(clean.get('url'))
    timestamp(clean.get('accessed_at'))
    if clean.get('date'):
        clean['date_start'], clean['date_end'] = date_interval(clean['date'])
    else:
        clean['date'] = None
        clean['date_start'] = clean['date_end'] = None
    if clean.get('date_kind') not in ('published', 'modified', 'archived', 'reported', 'unknown'):
        raise ValueError('date_kind 不受支持')
    if clean.get('status') not in ('verified', 'candidate', 'secondary', 'unavailable'):
        raise ValueError('status 不受支持')
    if clean.get('kind') not in ('original', 'archive', 'repost', 'search_snippet', 'secondary'):
        raise ValueError('kind 不受支持')
    for field in ('meaning_match', 'date_verified'):
        if not isinstance(clean.get(field), bool):
            raise ValueError(field + ' 必须是布尔值')
    if clean['status'] == 'verified':
        if (not clean['date'] or not clean['date_verified'] or not clean['meaning_match']
                or clean['kind'] not in ('original', 'archive')
                or clean['date_kind'] not in ('published', 'archived')):
            raise ValueError('已核验记录需原始／档案证据、对应词义及已核验的发布／存档日期')
    return clean


def create_run(root, term, meaning, aliases=None):
    term, meaning = text(term, '词条'), text(meaning, '含义')
    aliases = _strings(aliases or [], '别称')
    stamp = now()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    folder = Path(root).resolve() / run_id
    folder.mkdir(parents=True, exist_ok=False)
    record = dict(schema_version=1, run_id=run_id, term=term, meaning=meaning, aliases=aliases,
                  created_at=stamp, updated_at=stamp, language='zh', sessions=[], search_log=[],
                  evidence=[], conclusions=[], trends=[], revision=0, _revision=None,
                  _path=str(folder / 'investigation.json'))
    start_session(record)
    save_run(record)
    return record


def start_session(record):
    stamp = now()
    if record['sessions'] and not record['sessions'][-1]['ended_at']:
        record['sessions'][-1].update(ended_at=stamp, status='paused', stop_reason='开始后续调查')
    session = dict(id='S%03d' % (len(record['sessions']) + 1), started_at=stamp,
                   ended_at=None, status='active', stop_reason=None,
                   limits=dict(searches=18, pages=24, seconds=600))
    record['sessions'].append(session)
    return session


def finish_session(record, reason):
    reason = text(reason, '停止原因')
    record['sessions'][-1].update(ended_at=now(), status='completed', stop_reason=reason)


def add_log(record, item):
    clean = copy.deepcopy(item)
    if clean.get('kind') not in ('search', 'page'):
        raise ValueError('日志 kind 必须为 search 或 page')
    if clean['kind'] == 'search':
        clean['query'] = text(clean.get('query'), 'query')
    else:
        clean['url'] = web_url(clean.get('url'))
    clean['outcome'] = text(clean.get('outcome'), 'outcome')
    clean['accessed_at'] = clean.get('accessed_at') or now()
    timestamp(clean['accessed_at'])
    if record['sessions'][-1]['ended_at']:
        raise ValueError('会话已结束；继续调查前先 resume')
    clean.update(id='L%03d' % (len(record['search_log']) + 1), session_id=record['sessions'][-1]['id'])
    record['search_log'].append(clean)
    return clean


def add_evidence(record, item):
    clean = validate_evidence(item)
    if clean['meaning_match'] and clean['meaning'] != record['meaning']:
        raise ValueError('匹配的词义应与调查 meaning 一致；其他含义须标记 meaning_match=false')
    clean.update(id='E%03d' % (len(record['evidence']) + 1), added_at=now())
    record['evidence'].append(clean)
    return clean


def earliest_candidates(record):
    eligible = [e for e in record['evidence'] if e['status'] == 'verified' and e['meaning_match']]
    if not eligible:
        return []
    earliest_end = min(e['date_end'] for e in eligible)
    return [e['id'] for e in sorted(eligible, key=lambda e: (e['date_start'], e['date_end'], e['id']))
            if e['date_start'] <= earliest_end]


def add_conclusion(record, item):
    clean = copy.deepcopy(item)
    clean['summary'] = text(clean.get('summary'), 'summary')
    clean['earliest_ids'] = _strings(clean.get('earliest_ids', earliest_candidates(record)), 'earliest_ids')
    expected = earliest_candidates(record)
    if clean['earliest_ids'] and set(clean['earliest_ids']) != set(expected):
        raise ValueError('最早结论必须引用所有可能最早的已核验证据；不足时可留空')
    ids = {e['id'] for e in record['evidence']}
    timeline = clean.get('timeline', [])
    if not isinstance(timeline, list):
        raise ValueError('timeline 必须为数组')
    for entry in timeline:
        date_interval(entry.get('date'))
        text(entry.get('text'), 'timeline.text')
        refs = _strings(entry.get('evidence_ids'), 'timeline.evidence_ids')
        if not refs or not set(refs).issubset(ids):
            raise ValueError('传播节点必须引用现存证据编号')
        referenced = [e for e in record['evidence'] if e['id'] in refs]
        if not any(e['meaning_match'] for e in referenced):
            raise ValueError('传播节点至少需要一条符合调查词义的证据')
    clean['timeline'] = timeline
    for field in ('limitations', 'unresolved'):
        clean[field] = _strings(clean.get(field, []), field)
    clean.update(version=len(record['conclusions']) + 1, created_at=now())
    record['conclusions'].append(clean)
    return clean


def budget_status(record):
    session = record['sessions'][-1]
    logs = [x for x in record['search_log'] if x['session_id'] == session['id']]
    searches = sum(x['kind'] == 'search' for x in logs)
    pages = sum(x['kind'] == 'page' for x in logs)
    seconds = max(0, (timestamp(session['ended_at'] or now()) - timestamp(session['started_at'])).total_seconds())
    reasons = []
    for key, value in [('searches', searches), ('pages', pages), ('seconds', seconds)]:
        if value >= session['limits'][key]:
            reasons.append({'searches': 'search_limit', 'pages': 'page_limit', 'seconds': 'time_limit'}[key])
    if session['ended_at']:
        reasons.append('session_closed')
    return dict(session_id=session['id'], searches=searches, pages=pages, seconds=seconds,
                stop=bool(reasons), reasons=reasons, limits=session['limits'])


def _validate_record(record):
    if record.get('schema_version') != 1:
        raise ValueError('仅支持 schema_version=1')
    for field in ('run_id', 'term', 'meaning'):
        text(record.get(field), field)
    for field in ('sessions', 'search_log', 'evidence', 'conclusions', 'trends'):
        if not isinstance(record.get(field), list):
            raise ValueError(field + ' 必须是数组')
    if not record['sessions']:
        raise ValueError('缺少调查会话')
    evidence_ids = set()
    for index, item in enumerate(record['evidence']):
        item = validate_evidence(item)
        record['evidence'][index] = item
        eid = text(item.get('id'), 'evidence.id')
        if eid in evidence_ids:
            raise ValueError('证据编号重复')
        evidence_ids.add(eid)
    for conclusion in record['conclusions']:
        refs = list(conclusion['earliest_ids'])
        for entry in conclusion['timeline']:
            refs.extend(entry['evidence_ids'])
        if not set(refs).issubset(evidence_ids):
            raise ValueError('结论存在失效证据引用')
    return record


def load_run(path):
    path = Path(path).resolve()
    if path.is_dir():
        path = path / 'investigation.json'
    record = json.loads(path.read_text(encoding='utf-8-sig'))
    _validate_record(record)
    record.update(_path=str(path), _revision=record.get('revision', 0))
    return record


def save_run(record):
    _validate_record(record)
    path = Path(record['_path'])
    if path.exists():
        disk = json.loads(path.read_text(encoding='utf-8'))
        if disk.get('revision', 0) != record['_revision']:
            raise ValueError('记录已被另一操作更新；请重新读取后追加')
    clean = {k: v for k, v in record.items() if not k.startswith('_')}
    clean['updated_at'] = now()
    clean['revision'] = (record['_revision'] or 0) + 1
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=str(path.parent), delete=False) as out:
            tmp = out.name
            json.dump(clean, out, ensure_ascii=False, indent=2, allow_nan=False)
            out.write('\n')
        os.replace(tmp, str(path))
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    record.update(updated_at=clean['updated_at'], revision=clean['revision'], _revision=clean['revision'])
