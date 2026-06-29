"""Google Calendar 投影の純ロジック (gws/network を直接呼ばない)。"""
from __future__ import annotations

import json
import datetime


def _link_label(post: dict) -> str:
    kind = post.get("kind")
    title = post.get("title") or ""
    if kind == "announce":
        return "⚠️ 中止" if "中止" in title else "📣 お知らせ"
    if kind == "report":
        return "📝 報告"
    return "🔗 その他"


def build_description(posts: list[dict], limit: int = 1000) -> str:
    bodies = [p for p in posts if p.get("kind") != "report" and (p.get("body") or "").strip()]
    bodies.sort(key=lambda p: p.get("published") or "")
    text = "\n\n".join(p["body"].strip() for p in bodies)
    if len(text) > limit:
        text = text[:limit].rstrip() + "…（続きはリンク先で）"
    links = "\n".join(f"{_link_label(p)}: {p['url']}" for p in posts)
    return (text + "\n\n" + links).strip() if text else links


def ical_uid_for(event: dict) -> str:
    # canonical の開催日を一意キーにする (1日1イベント)。デプロイ済み UID と一致。
    return f"omc-{event['date']}@okumusashi-mtb"


def build_event_body(event: dict) -> dict:
    d = datetime.date.fromisoformat(event["date"])
    posts = (event.get("source") or {}).get("posts") or []
    return {
        "summary": event["summary"],
        "start": {"date": d.isoformat()},
        "end": {"date": (d + datetime.timedelta(days=1)).isoformat()},
        "description": build_description(posts),
        "iCalUID": ical_uid_for(event),
    }


# category とイベント summary の「別系統」判定用キーワード（矛盾検出）。
_CATEGORY_WORDS = {
    "里山整備": ["里山", "整備", "清掃", "道普請"],
    "定期作業": ["定期", "じてんしゃ", "自転車広場", "名栗"],
    "清掃活動": ["清掃", "ごみ"],
    "自転車教室": ["教室", "じてんしゃ", "自転車"],
    "総会": ["総会"],
    "ライド": ["ライド"],
}


def _contradicts(event: dict, existing_summary: str) -> bool:
    words = _CATEGORY_WORDS.get(event.get("category") or "", [])
    if not words:
        return False  # category 不明なら矛盾とみなさない(安全側=上書き可)
    return not any(w in (existing_summary or "") for w in words)


def decide_action(event: dict, existing: list[dict]) -> dict:
    uid = ical_uid_for(event)
    ours = [e for e in existing if e.get("iCalUID") == uid]
    if ours:
        return {"action": "update_ours", "target": ours[0], "reason": "our event"}
    manual = [e for e in existing if e.get("iCalUID") != uid]
    if not manual:
        return {"action": "create", "target": None, "reason": "no existing"}
    if len(manual) > 1:
        return {"action": "skip_review", "target": None, "reason": "multiple manual events"}
    m = manual[0]
    if _contradicts(event, m.get("summary") or ""):
        return {"action": "skip_review", "target": m, "reason": "summary contradicts category"}
    return {"action": "overwrite_manual", "target": m, "reason": "consistent manual event"}


def needs_update(target: dict, body: dict, fields=("summary", "description")) -> bool:
    return any((target.get(f) or "") != (body.get(f) or "") for f in fields)


def parse_gws_json(text: str):
    s = text.lstrip()
    for i, ch in enumerate(s):
        if ch in "{[":
            return json.loads(s[i:])
    raise ValueError("no JSON found in gws output")
