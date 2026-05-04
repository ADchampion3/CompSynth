"""Tests for utils/date_parser.py"""

from datetime import datetime, timedelta, timezone

from comp_synth.utils.date_parser import parse_published_at


class TestIso8601:
    def test_iso_date_only(self):
        result = parse_published_at("2026-04-10")
        assert result == datetime(2026, 4, 10)

    def test_iso_datetime(self):
        result = parse_published_at("2026-04-10T15:30:00")
        assert result == datetime(2026, 4, 10, 15, 30, 0)

    def test_iso_datetime_with_timezone(self):
        result = parse_published_at("2026-04-10T15:30:00+08:00")
        assert result == datetime(2026, 4, 10, 7, 30, 0)

    def test_iso_datetime_z_suffix(self):
        result = parse_published_at("2026-04-10T15:30:00Z")
        assert result == datetime(2026, 4, 10, 15, 30, 0)

    def test_iso_datetime_with_millis(self):
        result = parse_published_at("2026-04-10T15:30:00.123Z")
        assert result is not None
        assert result.year == 2026


class TestStrptimeFormats:
    def test_slash_date(self):
        assert parse_published_at("2026/04/10") == datetime(2026, 4, 10)

    def test_dot_date(self):
        assert parse_published_at("2026.04.10") == datetime(2026, 4, 10)

    def test_chinese_date(self):
        assert parse_published_at("2026年04月10日") == datetime(2026, 4, 10)

    def test_chinese_date_no_zero_pad(self):
        assert parse_published_at("2026年4月10日") == datetime(2026, 4, 10)

    def test_datetime_with_space(self):
        assert parse_published_at("2026-04-10 15:30:00") == datetime(2026, 4, 10, 15, 30, 0)

    def test_datetime_with_space_short(self):
        assert parse_published_at("2026-04-10 15:30") == datetime(2026, 4, 10, 15, 30)

    def test_slash_datetime(self):
        assert parse_published_at("2026/04/10 15:30") == datetime(2026, 4, 10, 15, 30)

    def test_english_full_month(self):
        assert parse_published_at("April 10, 2026") == datetime(2026, 4, 10)

    def test_english_abbr_month(self):
        assert parse_published_at("Apr 10, 2026") == datetime(2026, 4, 10)

    def test_english_day_first(self):
        assert parse_published_at("10 April 2026") == datetime(2026, 4, 10)

    def test_english_day_first_abbr(self):
        assert parse_published_at("10 Apr 2026") == datetime(2026, 4, 10)

    def test_chinese_datetime(self):
        assert parse_published_at("2026年04月10日 15:30") == datetime(2026, 4, 10, 15, 30)


class TestRelativeTimes:
    def test_just_now(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("刚刚", now=now)
        assert result == now

    def test_just_now_english(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("just now", now=now)
        assert result == now

    def test_yesterday(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("昨天", now=now)
        assert result == datetime(2026, 5, 3, 12, 0, 0)

    def test_yesterday_english(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("yesterday", now=now)
        assert result == datetime(2026, 5, 3, 12, 0, 0)

    def test_day_before_yesterday(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("前天", now=now)
        assert result == datetime(2026, 5, 2, 12, 0, 0)

    def test_minutes_ago_chinese(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("30分钟前", now=now)
        assert result == datetime(2026, 5, 4, 11, 30, 0)

    def test_hours_ago_chinese(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("3小时前", now=now)
        assert result == datetime(2026, 5, 4, 9, 0, 0)

    def test_days_ago_chinese(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("2天前", now=now)
        assert result == datetime(2026, 5, 2, 12, 0, 0)

    def test_weeks_ago_chinese(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("1周前", now=now)
        assert result == datetime(2026, 4, 27, 12, 0, 0)

    def test_months_ago_chinese(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("3个月前", now=now)
        assert result is not None
        assert result < now - timedelta(days=89)

    def test_hours_ago_english(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("3 hours ago", now=now)
        assert result == datetime(2026, 5, 4, 9, 0, 0)

    def test_days_ago_english(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("2 days ago", now=now)
        assert result == datetime(2026, 5, 2, 12, 0, 0)

    def test_minutes_ago_english(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("45 mins ago", now=now)
        assert result == datetime(2026, 5, 4, 11, 15, 0)

    def test_today_with_time(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("今天 08:30", now=now)
        assert result == datetime(2026, 5, 4, 8, 30, 0)

    def test_yesterday_with_time(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        result = parse_published_at("昨天 18:45", now=now)
        assert result == datetime(2026, 5, 3, 18, 45, 0)

    def test_english_relative_requires_ago(self):
        assert parse_published_at("5 minutes") is None
        assert parse_published_at("3 hours") is None
        assert parse_published_at("2 days") is None

    def test_invalid_hour_returns_none(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        assert parse_published_at("今天 25:00", now=now) is None

    def test_invalid_minute_returns_none(self):
        now = datetime(2026, 5, 4, 12, 0, 0)
        assert parse_published_at("今天 08:70", now=now) is None


class TestEdgeCases:
    def test_empty_string(self):
        assert parse_published_at("") is None

    def test_whitespace_only(self):
        assert parse_published_at("   ") is None

    def test_unrecognized_format(self):
        assert parse_published_at("some random text") is None

    def test_strips_whitespace(self):
        assert parse_published_at("  2026-04-10  ") == datetime(2026, 4, 10)

    def test_default_now_for_relative(self):
        """Relative time works without explicit now (uses current UTC)."""
        result = parse_published_at("刚刚")
        assert result is not None
        assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - result).total_seconds()) < 2
