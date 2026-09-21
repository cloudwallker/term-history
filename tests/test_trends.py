import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / ".agents" / "skills" / "term-history" / "scripts" / "trends.py"


def load_trends():
    spec = importlib.util.spec_from_file_location("trends_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metadata(**overrides):
    data = {
        "term": "test term",
        "source": "Google Trends",
        "source_url": "https://trends.google.com/",
        "metric": "search interest",
        "region": "US",
        "start": "2024-01-01",
        "end": "2024-01-31",
        "granularity": "day",
    }
    data.update(overrides)
    return data


def csv_file(contents):
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", suffix=".csv", delete=False)
    handle.write(contents)
    handle.close()
    return Path(handle.name)


class ParseCsvTests(unittest.TestCase):
    def parse(self, contents, fmt="generic", **metadata_overrides):
        path = csv_file(contents)
        self.addCleanup(path.unlink)
        return load_trends().parse_csv(path, fmt, metadata(**metadata_overrides))

    def test_generic_returns_periods_preserves_missing_and_keeps_below_threshold(self):
        series = self.parse(
            "date,value\n2024-01-01,3\n2024-01-02,\n2024-01-03,<1\n",
            end="2024-01-03",
        )
        self.assertEqual(series["metadata"]["term"], "test term")
        self.assertEqual(
            series["points"],
            [
                {"date": "2024-01-01", "start": "2024-01-01", "end": "2024-01-01", "value": 3.0, "qualifier": "exact", "raw_value": "3"},
                {"date": "2024-01-02", "start": "2024-01-02", "end": "2024-01-02", "value": None, "qualifier": "missing", "raw_value": ""},
                {"date": "2024-01-03", "start": "2024-01-03", "end": "2024-01-03", "value": None, "qualifier": "below_threshold", "raw_value": "<1"},
            ],
        )
        self.assertEqual(series["peak"], {"status": "available", "value": 3.0, "periods": [{"start": "2024-01-01", "end": "2024-01-01"}]})

    def test_range_rejects_partially_covered_week_bins(self):
        with self.assertRaisesRegex(ValueError, "完整分箱"):
            self.parse(
                "date,value\n2024-01-01 - 2024-01-07,5\n2024-01-08 - 2024-01-14,5\n",
                granularity="week", start="2024-01-03", end="2024-01-10",
            )

    def test_month_period_and_single_point_are_supported(self):
        series = self.parse("date,value\n2024-02,8\n", granularity="month", start="2024-02-01", end="2024-02-29")
        self.assertEqual(series["points"][0]["start"], "2024-02-01")
        self.assertEqual(series["points"][0]["end"], "2024-02-29")
        self.assertEqual(series["peak"]["value"], 8.0)

    def test_google_preamble_bom_chinese_week_header_and_explicit_column(self):
        series = self.parse(
            "Google Trends\n搜索字词: tea\n周,tea,coffee\n2024-01-01 - 2024-01-07,100,4\n",
            "google", granularity="week", end="2024-01-07", column="tea",
        )
        self.assertEqual(series["points"][0]["value"], 100.0)
        self.assertEqual(series["points"][0]["date"], "2024-01-01 - 2024-01-07")

    def test_google_accepts_day_month_and_date_headers(self):
        for header, granularity, date in [("Day", "day", "2024-01-01"), ("月", "month", "2024-01"), ("日期", "day", "2024-01-01")]:
            with self.subTest(header=header):
                series = self.parse(f"{header},tea\n{date},7\n", "google", granularity=granularity)
                self.assertEqual(series["points"][0]["value"], 7.0)

    def test_google_rejects_value_outside_0_to_100(self):
        with self.assertRaisesRegex(ValueError, "0.*100"):
            self.parse("Day,tea\n2024-01-01,101\n", "google")

    def test_multiple_value_columns_need_exact_selection_and_one_column_is_automatic(self):
        with self.assertRaisesRegex(ValueError, "column"):
            self.parse("Day,tea,coffee\n2024-01-01,1,2\n", "google")
        with self.assertRaisesRegex(ValueError, "column"):
            self.parse("Day,tea,coffee\n2024-01-01,1,2\n", "google", column="Tea")
        series = self.parse("Day,tea\n2024-01-01,1\n", "google")
        self.assertEqual(series["points"][0]["value"], 1.0)

    def test_duplicate_dates_with_equal_values_deduplicate_but_conflicts_fail(self):
        series = self.parse("date,value\n2024-01-01,2\n2024-01-01,2\n")
        self.assertEqual(len(series["points"]), 1)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.parse("date,value\n2024-01-01,2\n2024-01-01,3\n")

    def test_rejects_incomplete_metadata_bad_ranges_and_non_finite_or_negative_values(self):
        trends = load_trends()
        path = csv_file("date,value\n2024-01-01,1\n")
        self.addCleanup(path.unlink)
        bad = metadata()
        del bad["term"]
        with self.assertRaises(ValueError):
            trends.parse_csv(path, "generic", bad)
        for values in ("NaN", "inf", "-1"):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    self.parse(f"date,value\n2024-01-01,{values}\n")
        with self.assertRaises(ValueError):
            self.parse("date,value\n2024-01-01,1\n", start="2024-02-01", end="2024-01-01")

    def test_all_unknown_values_have_insufficient_peak(self):
        series = self.parse("date,value\n2024-01-01,\n2024-01-02,<1\n")
        self.assertEqual(series["peak"], {"status": "insufficient", "value": None, "periods": []})


class RenderSvgTests(unittest.TestCase):
    def test_renders_single_exact_point_and_escapes_metadata(self):
        series = {
            "metadata": {"term": "<tea & coffee>"},
            "points": [{"date": "2024-01-01", "start": "2024-01-01", "end": "2024-01-01", "value": 4.0, "qualifier": "exact", "raw_value": "4"}],
        }
        svg = load_trends().render_svg(series)
        self.assertIn("&lt;tea &amp; coffee&gt;", svg)
        self.assertIn("<circle", svg)
        self.assertNotIn("<tea & coffee>", svg)

    def test_all_missing_svg_has_no_fabricated_numeric_marks_or_nan(self):
        series = {
            "metadata": {"term": "tea"},
            "points": [
                {"date": "2024-01-01", "start": "2024-01-01", "end": "2024-01-01", "value": None, "qualifier": "missing", "raw_value": ""},
                {"date": "2024-01-02", "start": "2024-01-02", "end": "2024-01-02", "value": None, "qualifier": "below_threshold", "raw_value": "<1"},
            ],
        }
        svg = load_trends().render_svg(series)
        self.assertIn("暂无可绘制的精确数据", svg)
        self.assertNotIn("NaN", svg)
        self.assertNotIn("<circle", svg)
        self.assertNotIn("<polyline", svg)

    def test_missing_point_breaks_line_instead_of_inventing_a_connection(self):
        series = {
            "metadata": {"term": "tea"},
            "points": [
                {"date": "2024-01-01", "start": "2024-01-01", "end": "2024-01-01", "value": 1.0, "qualifier": "exact", "raw_value": "1"},
                {"date": "2024-01-02", "start": "2024-01-02", "end": "2024-01-02", "value": None, "qualifier": "missing", "raw_value": ""},
                {"date": "2024-01-03", "start": "2024-01-03", "end": "2024-01-03", "value": 3.0, "qualifier": "exact", "raw_value": "3"},
            ],
        }
        svg = load_trends().render_svg(series)
        self.assertEqual(svg.count("<circle"), 2)
        self.assertNotIn("<polyline", svg)

class RegressionContractTests(unittest.TestCase):
    def parse(self, contents, fmt="generic", **metadata_overrides):
        path = csv_file(contents)
        self.addCleanup(path.unlink)
        return load_trends().parse_csv(path, fmt, metadata(**metadata_overrides))

    def test_google_only_allows_less_than_one_threshold(self):
        with self.assertRaisesRegex(ValueError, "<1"):
            self.parse("Day,tea\n2024-01-01,<101\n", "google")

    def test_duplicate_below_threshold_dates_require_identical_raw_value(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.parse("date,value\n2024-01-01,<1\n2024-01-01,<2\n")

    def test_source_url_must_be_http_or_https(self):
        with self.assertRaises(ValueError):
            self.parse("date,value\n2024-01-01,1\n", source_url="javascript:alert(1)")

    def test_google_date_header_must_match_metadata_granularity(self):
        with self.assertRaisesRegex(ValueError, "granularity"):
            self.parse("Week,tea\n2024-01-01 - 2024-01-07,8\n", "google", granularity="day")

    def test_svg_has_context_axis_labels_and_time_scaled_coordinates(self):
        series = {
            "metadata": {"term": "tea", "metric": "interest", "region": "CN", "source": "Google Trends", "start": "2024-01-01", "end": "2024-01-11"},
            "points": [
                {"date": "2024-01-01", "start": "2024-01-01", "end": "2024-01-01", "value": 1.0, "qualifier": "exact", "raw_value": "1"},
                {"date": "2024-01-10", "start": "2024-01-10", "end": "2024-01-10", "value": 3.0, "qualifier": "exact", "raw_value": "3"},
            ],
        }
        svg = load_trends().render_svg(series)
        self.assertIn("interest · CN · Google Trends", svg)
        self.assertIn(">2024-01-01<", svg)
        self.assertIn(">2024-01-11<", svg)
        self.assertIn(">1<", svg)
        self.assertIn(">3<", svg)
        self.assertIn('cx="635.20"', svg)
    def test_below_threshold_can_make_exact_peak_insufficient(self):
        series = self.parse("date,value\n2024-01-01,0.2\n2024-01-02,<1\n", end="2024-01-02")
        self.assertEqual(series["peak"]["status"], "insufficient")
        self.assertTrue(any("峰值" in warning and "阈值" in warning for warning in series["warnings"]))

    def test_exact_peak_is_available_when_every_threshold_upper_bound_is_no_higher(self):
        series = self.parse("date,value\n2024-01-01,1\n2024-01-02,<1\n", end="2024-01-02")
        self.assertEqual(series["peak"]["status"], "available")
        self.assertEqual(series["peak"]["value"], 1.0)

    def test_equivalent_unclipped_periods_use_one_duplicate_key(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.parse("date,value\n2024-01-01,2\n2024-01-01 - 2024-01-01,3\n")

    def test_range_rejects_partially_covered_month_bin(self):
        with self.assertRaisesRegex(ValueError, "完整分箱"):
            self.parse("date,value\n2024-02,8\n", granularity="month", start="2024-02-10", end="2024-02-20")

    def test_fully_outside_bin_is_filtered_without_range_error(self):
        series = self.parse("date,value\n2024-01,8\n", granularity="month", start="2024-02-10", end="2024-02-20")
        self.assertEqual(series["points"], [])

if __name__ == "__main__":
    unittest.main()





