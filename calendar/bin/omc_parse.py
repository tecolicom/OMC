"""奥武蔵 MTB ブログの RSS/記事 → canonical イベントの純解析ロジック。"""
from __future__ import annotations

import datetime
import hashlib
import re
import xml.etree.ElementTree as ET


def _parse_pubdate(s: str) -> datetime.date:
    # 例: "Thu, 11 Jun 2026 10:44:12 GMT"
    return datetime.datetime.strptime(s.strip(), "%a, %d %b %Y %H:%M:%S %Z").date()


def _item_text(item, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""


def parse_rss(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    items = []
    for it in root.iter("item"):
        items.append({
            "title": _item_text(it, "title"),
            "link": _item_text(it, "link"),
            "guid": _item_text(it, "guid"),
            "pub_date": _parse_pubdate(_item_text(it, "pubDate")),
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


def post_kind(title: str) -> str:
    if "報告" in title or "しました" in title:
        return "report"
    if "お知らせ" in title or "します" in title:
        return "announce"
    return "other"


# 判定順に評価 (先にマッチした種別を採用)。里山は清掃語より先に見る。
_ACTIVITY_RULES = [
    ("総会", ["総会"]),
    ("自転車教室", ["自転車教室"]),
    ("里山整備", ["里山"]),
    ("定期作業", ["名栗定期作業", "定期作業"]),
    ("清掃活動", ["清掃", "ごみゼロ", "ごみゼロの日"]),
]


def classify_activity(title: str) -> str:
    for label, keywords in _ACTIVITY_RULES:
        if any(k in title for k in keywords):
            return label
    return "その他"


_LEADING_DATE_RE = re.compile(r"^\s*[【\[]?\s*\d{1,2}\s*[/／]\s*\d{1,2}\s*(?:\([^)]*\))?\s*の?")
_TRAILING_RE = re.compile(
    r"(?:のお知らせ|のご報告|の報告|を開催しました|を開催します|報告)\s*[】\]]?\s*$"
)


def clean_summary(title: str) -> str:
    s = _LEADING_DATE_RE.sub("", title)
    s = _TRAILING_RE.sub("", s)
    s = s.strip(" 　【】[]")
    return s if s else title.strip()


def _uid_for(date: datetime.date) -> str:
    return hashlib.sha1(date.isoformat().encode("utf-8")).hexdigest()[:12]


def build_events(items: list[dict]) -> list[dict]:
    groups: dict[datetime.date, list[dict]] = {}
    for it in items:
        date = extract_event_date(it["title"], it["pub_date"])
        if date is None:
            continue
        rec = {
            "category": classify_activity(it["title"]),
            "kind": post_kind(it["title"]),
            "summary": clean_summary(it["title"]),
            "src": {
                "kind": post_kind(it["title"]),
                "url": it["link"],
                "title": it["title"],
                "published": it["pub_date"],
            },
        }
        groups.setdefault(date, []).append(rec)

    events = []
    for date in sorted(groups):
        recs = groups[date]
        category = next((r["category"] for r in recs if r["category"] != "その他"), "その他")
        if category != "その他":
            summary = next(r["summary"] for r in recs if r["category"] == category)
        else:
            report = next((r for r in recs if r["kind"] == "report"), None)
            summary = report["summary"] if report else recs[0]["summary"]
        events.append({
            "date": date,
            "category": category,
            "all_day": True,
            "uid": _uid_for(date),
            "summary": summary,
            "sources": [r["src"] for r in recs],
        })
    return events


def _report_or_first_url(event: dict) -> str:
    for s in event["sources"]:
        if s["kind"] == "report":
            return s["url"]
    return event["sources"][0]["url"]


def event_to_yaml_dict(event: dict, fetched: datetime.date) -> dict:
    posts = [
        {"kind": s["kind"], "url": s["url"], "title": s["title"],
         "published": s["published"].isoformat()}
        for s in event["sources"]
    ]
    return {
        "summary": event["summary"],
        "date": event["date"].isoformat(),
        "all_day": event["all_day"],
        "category": event["category"],
        "description": "出典: " + _report_or_first_url(event),
        "source": {
            "type": "omc-blog",
            "crawler": "cal-omc-blog-fetch",
            "fetched": fetched.isoformat(),
            "posts": posts,
        },
    }


def event_filename(event: dict) -> str:
    d = event["date"]
    return "%04d/%02d-%02d_%s.yaml" % (d.year, d.month, d.day, event["uid"])
