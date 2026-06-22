"""奥武蔵 MTB ブログの RSS/記事 → canonical イベントの純解析ロジック。"""
from __future__ import annotations

import datetime
import re
import xml.etree.ElementTree as ET


def _parse_pubdate(s: str) -> datetime.date:
    # 例: "Thu, 11 Jun 2026 10:44:12 GMT"
    return datetime.datetime.strptime(s.strip(), "%a, %d %b %Y %H:%M:%S %Z").date()


def parse_rss(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    items = []
    for it in root.iter("item"):
        def text(tag: str) -> str:
            el = it.find(tag)
            return (el.text or "").strip() if el is not None else ""
        items.append({
            "title": text("title"),
            "link": text("link"),
            "guid": text("guid"),
            "pub_date": _parse_pubdate(text("pubDate")),
        })
    return items


_MD_RE = re.compile(r"(\d{1,2})\s*[/／]\s*(\d{1,2})")


def extract_event_date(title: str, pub_date: datetime.date) -> datetime.date | None:
    m = _MD_RE.search(title)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    year = pub_date.year
    if month - pub_date.month > 6:
        year -= 1
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None
