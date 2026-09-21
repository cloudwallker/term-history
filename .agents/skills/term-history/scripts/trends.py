"""离线解析趋势 CSV 并渲染安全的 SVG 图表。"""

import calendar
import csv
import datetime as _datetime
import html
import math
import re
from urllib.parse import urlparse


_REQUIRED_METADATA = (
    "term", "source", "source_url", "metric", "region", "start", "end", "granularity",
)
_GOOGLE_DATE_HEADERS = {"day", "week", "month", "date", "日期", "天", "周", "月"}
_RANGE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*(?:-|–|—|to)\s*(\d{4}-\d{2}-\d{2})$", re.IGNORECASE)
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


def _parse_iso_date(value, field):
    if not isinstance(value, str) or not _DAY_RE.match(value):
        raise ValueError("%s 必须为 YYYY-MM-DD" % field)
    try:
        return _datetime.date.fromisoformat(value)
    except ValueError:
        raise ValueError("%s 不是有效日期: %s" % (field, value))


def _validate_metadata(metadata):
    if not isinstance(metadata, dict):
        raise ValueError("metadata 必须是对象")
    missing = [key for key in _REQUIRED_METADATA if not isinstance(metadata.get(key), str) or not metadata[key].strip()]
    if missing:
        raise ValueError("metadata 缺少必填字段: " + ", ".join(missing))
    result = dict(metadata)
    result["start"] = result["start"].strip()
    result["end"] = result["end"].strip()
    start = _parse_iso_date(result["start"], "metadata.start")
    end = _parse_iso_date(result["end"], "metadata.end")
    if start > end:
        raise ValueError("metadata.start 不能晚于 metadata.end")
    if result["granularity"] not in ("day", "week", "month"):
        raise ValueError("metadata.granularity 必须为 day、week 或 month")
    result["source_url"] = result["source_url"].strip()
    source_url = urlparse(result["source_url"])
    if source_url.scheme not in ("http", "https") or not source_url.netloc:
        raise ValueError("metadata.source_url 必须是可追溯的 http(s) 地址")
    return result, start, end


def _date_string(value):
    return value.isoformat()


def _parse_period(raw_date, granularity):
    raw_date = raw_date.strip()
    match = _RANGE_RE.match(raw_date)
    if match:
        start = _parse_iso_date(match.group(1), "CSV 日期")
        end = _parse_iso_date(match.group(2), "CSV 日期")
        if end < start:
            raise ValueError("CSV 日期区间结束早于开始: " + raw_date)
        return raw_date, start, end
    if granularity == "month":
        month = _MONTH_RE.match(raw_date)
        if not month:
            raise ValueError("月度 CSV 日期必须为 YYYY-MM: " + raw_date)
        year, number = int(month.group(1)), int(month.group(2))
        if not 1 <= number <= 12:
            raise ValueError("无效月份: " + raw_date)
        start = _datetime.date(year, number, 1)
        end = _datetime.date(year, number, calendar.monthrange(year, number)[1])
        return raw_date, start, end
    start = _parse_iso_date(raw_date, "CSV 日期")
    if granularity == "week":
        return raw_date, start, start + _datetime.timedelta(days=6)
    return raw_date, start, start


def _parse_value(raw_value, format_name):
    value_text = raw_value.strip()
    if not value_text:
        return None, "missing", ""
    if value_text.startswith("<"):
        threshold = value_text[1:].strip()
        try:
            numeric_threshold = float(threshold)
        except ValueError:
            raise ValueError("无效的阈值值: " + value_text)
        if not math.isfinite(numeric_threshold) or numeric_threshold < 0:
            raise ValueError("阈值必须是有限非负数: " + value_text)
        if format_name == "google" and value_text != "<1":
            raise ValueError("Google Trends 阈值只能为 <1")
        return None, "below_threshold", value_text
    try:
        value = float(value_text)
    except ValueError:
        raise ValueError("数值必须是有限非负数: " + value_text)
    if not math.isfinite(value) or value < 0:
        raise ValueError("数值必须是有限非负数: " + value_text)
    if format_name == "google" and value > 100:
        raise ValueError("Google Trends 数值必须在 0 到 100 之间")
    return value, "exact", value_text


def _read_rows(path):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as csv_file:
            return list(csv.reader(csv_file))
    except OSError as error:
        raise ValueError("无法读取 CSV: %s" % error)


def _find_header(rows, format_name):
    for index, row in enumerate(rows):
        if not row:
            continue
        first = row[0].strip().lower()
        if format_name == "generic":
            if first == "date":
                return index, row
        elif first in _GOOGLE_DATE_HEADERS:
            return index, row
    expected = "date" if format_name == "generic" else "Day/Week/Month/天/周/月/日期"
    raise ValueError("未找到日期表头: " + expected)


def _choose_value_column(header, metadata):
    if len(header) < 2:
        raise ValueError("CSV 必须包含一个数值列")
    candidates = [cell.strip() for cell in header[1:]]
    selected = metadata.get("column")
    if selected is not None:
        if not isinstance(selected, str) or selected not in candidates:
            raise ValueError("metadata.column 必须精确匹配一个数值列")
        return candidates.index(selected) + 1
    if len(candidates) != 1:
        raise ValueError("CSV 有多个数值列，必须提供 metadata.column")
    return 1


def parse_csv(path, format, metadata):
    """按 ``generic`` 或 Google Trends CSV 格式返回标准化趋势序列。"""
    if format not in ("generic", "google"):
        raise ValueError("format 必须为 generic 或 google")
    normalized_metadata, requested_start, requested_end = _validate_metadata(metadata)
    rows = _read_rows(path)
    header_index, header = _find_header(rows, format)
    if format == "google":
        google_granularity = {
            "day": "day", "date": "day", "日期": "day", "天": "day",
            "week": "week", "周": "week",
            "month": "month", "月": "month",
        }[header[0].strip().lower()]
        if google_granularity != normalized_metadata["granularity"]:
            raise ValueError("Google CSV 日期表头与 metadata.granularity 不一致")
    value_index = _choose_value_column(header, normalized_metadata)

    points_by_period = {}
    for row in rows[header_index + 1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) <= value_index:
            raise ValueError("CSV 数据行缺少选定数值列")
        date_text = row[0].strip()
        if not date_text:
            raise ValueError("CSV 数据行缺少日期")
        date_label, bin_start, bin_end = _parse_period(date_text, normalized_metadata["granularity"])
        value, qualifier, raw_value = _parse_value(row[value_index], format)
        if bin_end < requested_start or bin_start > requested_end:
            continue
        if bin_start < requested_start or bin_end > requested_end:
            raise ValueError("metadata 日期范围必须覆盖完整分箱，不能裁切分箱数值")
        point = {
            "date": date_label,
            "start": _date_string(bin_start),
            "end": _date_string(bin_end),
            "value": value,
            "qualifier": qualifier,
            "raw_value": raw_value,
        }
        period_key = (point["start"], point["end"])
        existing = points_by_period.get(period_key)
        if existing is not None:
            same_value = (existing["qualifier"] == qualifier and existing["value"] == value and (qualifier != "below_threshold" or existing["raw_value"] == raw_value))
            if same_value:
                continue
            raise ValueError("duplicate 日期区间存在冲突值: " + date_label)
        points_by_period[period_key] = point

    points = sorted(points_by_period.values(), key=lambda point: (point["start"], point["end"], point["date"]))
    exact_points = [point for point in points if point["qualifier"] == "exact" and point["value"] > 0]
    threshold_points = [point for point in points if point["qualifier"] == "below_threshold"]
    peak_warning = None
    if exact_points:
        peak_value = max(point["value"] for point in exact_points)
        unresolved_threshold = any(float(point["raw_value"][1:].strip()) > peak_value for point in threshold_points)
        if unresolved_threshold:
            peak = {"status": "insufficient", "value": None, "periods": []}
            peak_warning = "低于阈值的数据上界可能高于精确最大值，无法确认峰值。"
        else:
            peak = {
                "status": "available",
                "value": peak_value,
                "periods": [{"start": point["start"], "end": point["end"]} for point in exact_points if point["value"] == peak_value],
            }
    else:
        peak = {"status": "insufficient", "value": None, "periods": []}

    warnings = []
    missing_count = sum(point["qualifier"] == "missing" for point in points)
    below_count = sum(point["qualifier"] == "below_threshold" for point in points)
    if missing_count:
        warnings.append("存在 %d 个缺失值，未补零。" % missing_count)
    if below_count:
        warnings.append("存在 %d 个低于阈值的值，未按精确数值处理。" % below_count)
    if peak_warning:
        warnings.append(peak_warning)
    return {"metadata": normalized_metadata, "points": points, "peak": peak, "warnings": warnings}


def render_svg(series):
    """将精确点绘为 SVG；日期按真实时间比例定位，未知数据不虚构坐标。"""
    if not isinstance(series, dict):
        raise ValueError("series 必须是对象")
    metadata = series.get("metadata") or {}
    term = html.escape(str(metadata.get("term", "趋势")), quote=True)
    metric = html.escape(str(metadata.get("metric", "数值")), quote=True)
    region = html.escape(str(metadata.get("region", "未注明地域")), quote=True)
    source = html.escape(str(metadata.get("source", "未注明来源")), quote=True)
    points = series.get("points") or []
    exact = []
    for index, point in enumerate(points):
        if not isinstance(point, dict) or point.get("qualifier") != "exact":
            continue
        value = point.get("value")
        if isinstance(value, bool):
            continue
        try:
            value = float(value)
            point_date = _parse_iso_date(str(point.get("start", "")), "point.start")
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value >= 0:
            exact.append((index, value, point, point_date))

    try:
        axis_start = _parse_iso_date(str(metadata.get("start", "")), "metadata.start")
        axis_end = _parse_iso_date(str(metadata.get("end", "")), "metadata.end")
        if axis_end < axis_start:
            raise ValueError
    except ValueError:
        dates = [item[3] for item in exact]
        axis_start = min(dates) if dates else _datetime.date.today()
        axis_end = max(dates) if dates else axis_start

    width, height, left, right, top, bottom = 720, 360, 52, 20, 64, 70
    chart_width, chart_height = width - left - right, height - top - bottom
    context = "%s · %s · %s" % (metric, region, source)
    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="360" viewBox="0 0 720 360" role="img">',
        '<title>%s</title>' % term,
        '<rect width="720" height="360" fill="white"/>',
        '<path d="M52 64V290H700" fill="none" stroke="#94a3b8"/>',
        '<text x="52" y="25" font-family="sans-serif" font-size="16">%s</text>' % term,
        '<text x="52" y="47" font-family="sans-serif" font-size="12" fill="#475569">%s</text>' % context,
        '<text x="52" y="315" font-family="sans-serif" font-size="11" text-anchor="start">%s</text>' % axis_start.isoformat(),
        '<text x="700" y="315" font-family="sans-serif" font-size="11" text-anchor="end">%s</text>' % axis_end.isoformat(),
        '<text x="52" y="337" font-family="sans-serif" font-size="11">%s</text>' % metric,
    ]
    if not exact:
        pieces.append('<text x="52" y="177" font-family="sans-serif" font-size="14" fill="#64748b">暂无可绘制的精确数据</text>')
        pieces.append("</svg>")
        return "".join(pieces)

    minimum = min(value for _, value, _, _ in exact)
    maximum = max(value for _, value, _, _ in exact)
    total_days = max((axis_end - axis_start).days, 1)

    def coordinates(point_date, value):
        offset = (point_date - axis_start).days / total_days
        x = left + chart_width * min(1, max(0, offset))
        if maximum == minimum:
            y = top + chart_height / 2
        else:
            y = top + chart_height * (maximum - value) / (maximum - minimum)
        return x, y

    def display_value(value):
        return str(int(value)) if value.is_integer() else "%g" % value

    pieces.extend([
        '<text x="46" y="%.2f" font-family="sans-serif" font-size="11" text-anchor="end">%s</text>' % (top + 4, display_value(maximum)),
        '<text x="46" y="%.2f" font-family="sans-serif" font-size="11" text-anchor="end">%s</text>' % (top + chart_height, display_value(minimum)),
    ])
    runs, current = [], []
    exact_by_index = {index: (value, point, point_date) for index, value, point, point_date in exact}
    for index in range(len(points)):
        item = exact_by_index.get(index)
        if item is None:
            if current:
                runs.append(current)
                current = []
            continue
        value, point, point_date = item
        x, y = coordinates(point_date, value)
        current.append((x, y, point))
    if current:
        runs.append(current)
    for run in runs:
        if len(run) > 1:
            coordinates_text = " ".join("%.2f,%.2f" % (x, y) for x, y, _ in run)
            pieces.append('<polyline points="%s" fill="none" stroke="#2563eb" stroke-width="2"/>' % coordinates_text)
    for _, value, point, point_date in exact:
        x, y = coordinates(point_date, value)
        label = html.escape(str(point.get("date", "")), quote=True)
        pieces.append('<circle cx="%.2f" cy="%.2f" r="3.5" fill="#2563eb"><title>%s: %s</title></circle>' % (x, y, label, value))
    pieces.append("</svg>")
    return "".join(pieces)


