"""Render reports from saved records, never from inferred search counts."""
import html
import re
from pathlib import Path
from urllib.parse import quote

from core import budget_status, earliest_candidates


STATUS = {'verified': '已核验', 'candidate': '待核实线索', 'secondary': '二手转述', 'unavailable': '原文不可访问'}
DATE_KIND = {'published': '发布', 'modified': '修改', 'archived': '存档（至迟已存在）', 'reported': '转述的事件日期', 'unknown': '未知'}


def md(value):
    value = html.escape(str(value), quote=False).replace('\\', '\\\\')
    for char in ('[', ']', '*', '_', '`', '|'):
        value = value.replace(char, '\\' + char)
    return value.replace('\r', '').replace('\n', ' ')


def link(title, url):
    return '[%s](%s)' % (md(title), quote(url, safe=':/?#=&%+@;,-._~'))


def refs(ids):
    return '、'.join('[%s](#%s)' % (eid, eid.lower()) for eid in ids)


def render(record):
    from trends import render_svg
    folder = Path(record['_path']).parent
    current = record['conclusions'][-1] if record['conclusions'] else None
    by_id = {e['id']: e for e in record['evidence']}
    lines = ['# 词条调查：' + md(record['term']), '',
             '- 调查含义：' + md(record['meaning']),
             '- 记录编号：`' + record['run_id'] + '`',
             '- 最近记录更新：' + md(record['updated_at']),
             '- 目标范围：公开网页文字，中文优先；实际读取的材料以下方日志为准。', '',
             '本报告呈现截至本次检索所发现的证据，不证明已经覆盖全网。', '',
             '## 最早已知记录', '']
    if current:
        lines += [md(current['summary']), '']
    selected = current['earliest_ids'] if current else []
    if selected:
        for eid in selected:
            e = by_id[eid]
            label = '至迟 ' if e['date_kind'] == 'archived' else ''
            lines.append('- %s%s：%s。%s' % (label, md(e['date']), link(e['title'], e['url']), refs([eid])))
        if len(selected) > 1:
            lines += ['', '以上日期区间存在重叠或并列，当前精度不足以确定唯一先后。']
        if set(selected) != set(earliest_candidates(record)):
            lines += ['', '**旧版结论后新增了更早或精度不同的证据，请继续核对并生成新结论。**']
    else:
        lines.append('尚未确定最早可验证记录；候选和二手说法见证据表。')
    if current:
        lines += ['', '结论版本：%s；此前版本保留于调查 JSON。' % current['version']]
    lines += ['', '## 传播时间线', '']
    if current and current['timeline']:
        lines += ['| 时间 | 有证据支持的节点 | 证据 |', '| --- | --- | --- |']
        for item in sorted(current['timeline'], key=lambda t: t['date']):
            labels = '、'.join(sorted({STATUS[by_id[eid]['status']] for eid in item['evidence_ids']}))
            lines.append('| %s | %s（%s） | %s |' % (md(item['date']), md(item['text']), labels, refs(item['evidence_ids'])))
    else:
        lines.append('尚无经整理的传播节点。检索结果的数量不作为传播规模。')
    lines += ['', '## 热度结果', '']
    if not record['trends']:
        lines.append('数据不足：没有可计算的历史时间序列。可补充 Google Trends 官方 CSV 或通用 date,value CSV。')
    for series in record['trends']:
        meta = series['metadata']
        sid = series['id']
        if not re.fullmatch(r'T\d{3,}', sid):
            raise ValueError('无效的趋势编号')
        lines += ['### %s：%s' % (sid, md(meta['source'])), '',
                  '- 词条：%s；指标：%s；地域：%s。' % (md(meta['term']), md(meta['metric']), md(meta['region'])),
                  '- 覆盖范围：%s 至 %s；粒度：%s。' % (meta['start'], meta['end'], md(meta['granularity'])),
                  '- 来源：' + link(meta['source'], meta['source_url']),
                  '- 原始数据：' + link('CSV', series['raw_file'])]
        peak = series['peak']
        if peak['status'] == 'available':
            periods = ['%s 至 %s' % (p['start'], p['end']) if p['start'] != p['end'] else p['start'] for p in peak['periods']]
            lines += ['- **该序列覆盖范围内的观测峰值：%s**；时间：%s。' % (md(peak['value']), '；'.join(periods))]
        else:
            lines += ['- 数据不足：当前序列不能确认可信峰值（可能全零、缺失或受低于阈值的数据影响）。']
        lines += ['- ' + md(w) for w in series['warnings']]
        chart_dir = folder / 'trends'
        chart_dir.mkdir(exist_ok=True)
        (chart_dir / (sid + '.svg')).write_text(render_svg(series), encoding='utf-8')
        lines += ['', '![%s](trends/%s.svg)' % (md(meta['metric']), sid), '',
                  '该结果仅属于上述数据源及查询范围，不代表全网历史最高热度。', '']
    lines += ['', '## 证据表', '']
    if not record['evidence']:
        lines.extend(['尚未记录可引用证据。', ''])
    for e in record['evidence']:
        lines += ['<a id="%s"></a>' % e['id'].lower(), '',
                  '### %s · %s' % (e['id'], md(e['title'])), '',
                  '- 状态：%s；词义匹配：%s。' % (STATUS[e['status']], '是' if e['meaning_match'] else '否'),
                  '- 来源：' + link(e['title'], e['url']),
                  '- 日期：%s；类型：%s。' % (md(e['date'] or '未知'), DATE_KIND[e['date_kind']]),
                  '- 日期依据：' + md(e['date_basis']),
                  '- 相关摘录：' + md(e['excerpt']),
                  '- 核验说明：' + md(e['verification_note']),
                  '- 访问时间：' + md(e['accessed_at']), '']
    lines += ['## 覆盖范围与调查日志', '',
              '- 累计会话：%s；搜索查询：%s；页面访问：%s。' % (len(record['sessions']),
                 sum(x['kind'] == 'search' for x in record['search_log']), sum(x['kind'] == 'page' for x in record['search_log'])),
              '- 本轮预算状态：' + md(', '.join(budget_status(record)['reasons']) or '未达到上限'), '']
    for session in record['sessions']:
        lines.append('- %s：%s → %s；%s。' % (session['id'], session['started_at'], session['ended_at'] or '进行中', md(session['stop_reason'] or '调查中')))
    lines.append('')
    for entry in record['search_log']:
        target = md(entry['query']) if entry['kind'] == 'search' else link('原文／档案', entry['url'])
        lines.append('- %s [%s] %s → %s' % (entry['id'], entry['session_id'], target, md(entry['outcome'])))
    lines += ['', '## 局限与待办线索', '']
    limitations = current['limitations'] if current else ['尚未生成结论；请继续核验已有候选。']
    lines += ['- ' + md(x) for x in limitations]
    lines += ['- ' + md(x) for x in (current['unresolved'] if current else [])]
    lines += ['- 未被搜索引擎收录、已删除或当前不可访问的内容可能改变结论。',
              '- 年／月级日期保持原精度；发布日期、修改日期和存档日期不互相替代。', '']
    destination = folder / 'report.md'
    destination.write_text('\n'.join(lines), encoding='utf-8')
    return destination
