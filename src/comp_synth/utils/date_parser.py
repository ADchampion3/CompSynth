"""Centralized date parsing for crawled content.

Supports ISO 8601, common date/datetime formats, Chinese dates,
and relative time expressions. All returned datetimes are naive UTC.
"""

import re
from datetime import datetime, timedelta, timezone


def parse_published_at(text: str, now: datetime | None = None) -> datetime | None:
    """Parse a date/time string into a naive UTC datetime.

    Tries formats in order: ISO 8601 -> strptime list -> relative time regex.
    Returns None if nothing matches.
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    result = _try_iso8601(text)
    if result is not None:
        return result

    result = _try_strptime(text)
    if result is not None:
        return result

    result = _try_relative(text, now)
    return result


def _to_naive_utc(dt: datetime) -> datetime:
    """Convert any datetime to naive UTC."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _try_iso8601(text: str) -> datetime | None:
    """Try parsing ISO 8601 via datetime.fromisoformat."""
    cleaned = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        return _to_naive_utc(dt)
    except (ValueError, TypeError):
        return None


_STRPTIME_FORMATS = [
    # 带时间的格式
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y.%m.%d %H:%M:%S",
    "%Y.%m.%d %H:%M",
    # 纯日期格式
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y年%m月%d日",
    "%Y年%m月%d日 %H:%M",
    "%Y年%m月%d日 %H:%M:%S",
    # 英文日期
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d %Y",
    "%b %d %Y",
]


def _try_strptime(text: str) -> datetime | None:
    """Try a list of strptime formats."""
    for fmt in _STRPTIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _try_relative(text: str, now: datetime | None = None) -> datetime | None:
    """Try parsing relative time expressions (Chinese and English)."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)

    # 刚刚 / just now
    if text in ("刚刚", "just now"):
        return now

    # 昨天 / yesterday
    if text in ("昨天", "yesterday"):
        return now - timedelta(days=1)

    # 前天
    if text == "前天":
        return now - timedelta(days=2)

    # N分钟前 / N mins ago
    m = re.match(r"(\d+)\s*分钟前", text)
    if m:
        return now - timedelta(minutes=int(m.group(1)))

    m = re.match(r"(\d+)\s*(?:minute|minutes|min|mins)\s+ago", text, re.IGNORECASE)
    if m:
        return now - timedelta(minutes=int(m.group(1)))

    # N小时前 / N hours ago
    m = re.match(r"(\d+)\s*小时前", text)
    if m:
        return now - timedelta(hours=int(m.group(1)))

    m = re.match(r"(\d+)\s*(?:hour|hours|hr|hrs)\s+ago", text, re.IGNORECASE)
    if m:
        return now - timedelta(hours=int(m.group(1)))

    # N天前 / N days ago
    m = re.match(r"(\d+)\s*天前", text)
    if m:
        return now - timedelta(days=int(m.group(1)))

    m = re.match(r"(\d+)\s*(?:day|days)\s+ago", text, re.IGNORECASE)
    if m:
        return now - timedelta(days=int(m.group(1)))

    # N周前 / N weeks ago
    m = re.match(r"(\d+)\s*周前", text)
    if m:
        return now - timedelta(weeks=int(m.group(1)))

    m = re.match(r"(\d+)\s*(?:week|weeks)\s+ago", text, re.IGNORECASE)
    if m:
        return now - timedelta(weeks=int(m.group(1)))

    # N个月前 (approximate as 30 days)
    m = re.match(r"(\d+)\s*个月前", text)
    if m:
        return now - timedelta(days=int(m.group(1)) * 30)

    m = re.match(r"(\d+)\s*(?:month|months)\s+ago", text, re.IGNORECASE)
    if m:
        return now - timedelta(days=int(m.group(1)) * 30)

    # 今天 HH:MM
    m = re.match(r"今天\s*(\d{1,2}):(\d{2})$", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return now.replace(hour=h, minute=mi, second=0, microsecond=0)

    # 昨天 HH:MM
    m = re.match(r"昨天\s*(\d{1,2}):(\d{2})$", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            base = now - timedelta(days=1)
            return base.replace(hour=h, minute=mi, second=0, microsecond=0)

    return None
