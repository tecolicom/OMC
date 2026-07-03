"""奥武蔵 MTB ブログの RSS/記事 → canonical イベントの純解析ロジック。"""
from __future__ import annotations

import datetime
import hashlib
import html as _html
import json
import re
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

import yaml

# 複数行 str は YAML ブロックスカラー(|)で出力（アーカイブ可読性）。単一行は既定どおり。
def _block_str_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

yaml.add_representer(str, _block_str_representer, Dumper=yaml.SafeDumper)


def _parse_pubdate(s: str) -> datetime.date:
    # 例: "Thu, 11 Jun 2026 10:44:12 GMT"
    return datetime.datetime.strptime(s.strip(), "%a, %d %b %Y %H:%M:%S %Z").date()


def _item_text(item, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _clean_body(text: str) -> str:
    t = unicodedata.normalize("NFKC", _html.unescape(text))
    lines = [ln.rstrip() for ln in t.split("\n")]
    return "\n".join(lines).strip("\n")


_TAG_RE = re.compile(r"<[^>]+>")


def _description_from_jsonld(html: str) -> str:
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in (data if isinstance(data, list) else [data]):
            if (isinstance(item, dict)
                    and item.get("@type") in ("BlogPosting", "Article", "NewsArticle")
                    and item.get("description") is not None):
                return item["description"]
    return ""


def _is_footer_line(t: str) -> bool:
    s = t.lstrip()
    return ("Proudly created with Wix" in t) or s.startswith("©") or s.startswith("(c)")


def extract_post_body(html: str) -> str:
    """記事HTMLの本文を段落構造付きで返す。

    post-description コンテナ内で、<p> 間の <br> スペーサーや空白のみの <p> を段落区切り(\\n\\n)、
    それ以外の連続する <p> を段落内の改行(\\n)として組み立てる。<p> 内の <br> も改行。
    行頭の字下げ(桁揃えの空白)は保持する(各行 rstrip のみ)。
    見つからない/空なら JSON-LD description を _clean_body した値。
    """
    idx = html.find('data-hook="post-description"')
    if idx != -1:
        end = html.find("Proudly created with Wix", idx)
        region = html[idx:end] if end > idx else html[idx:]
        parts = re.split(r"(<p\b[^>]*>.*?</p>)", region, flags=re.S)
        paras: list[str] = []
        cur: list[str] = []
        pending_break = False
        for seg in parts:
            if seg.startswith("<p"):
                seg = re.sub(r"<br\s*/?>", "\n", seg)
                t = _html.unescape(_TAG_RE.sub("", seg))
                t = "\n".join(ln.rstrip() for ln in t.split("\n")).strip("\n")
                if not t.strip():          # 空/空白のみの <p> は段落区切り
                    pending_break = True
                    continue
                if _is_footer_line(t):
                    continue
                if pending_break and cur:
                    paras.append("\n".join(cur))
                    cur = []
                cur.append(t)
                pending_break = False
            elif "<br" in seg:
                pending_break = True
        if cur:
            paras.append("\n".join(cur))
        body = "\n\n".join(paras)
        if body:
            return body
    return _clean_body(_description_from_jsonld(html))


def extract_post_meta(html: str) -> dict | None:
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in (data if isinstance(data, list) else [data]):
            if not isinstance(item, dict):
                continue
            if item.get("@type") in ("BlogPosting", "Article", "NewsArticle"):
                headline = item.get("headline")
                published = item.get("datePublished")
                if not headline or not published:
                    continue
                headline = re.sub(r"\s+", " ", _html.unescape(headline)).strip()
                if not headline:
                    continue
                try:
                    pub = datetime.date.fromisoformat(str(published)[:10])
                except ValueError:
                    continue
                body = extract_post_body(html)
                return {"title": headline, "pub_date": pub, "body": body}
    return None


_WIX_IMG_RE = re.compile(
    r'https://static\.wixstatic\.com/media/([A-Za-z0-9_~%.-]+\.(?:jpg|jpeg|png|gif|webp))'
    r'(?:/v1/[^"\'\s)]*?w_(\d+))?'
)
_OG_IMAGE_RE = re.compile(r'<meta property="og:image" content="([^"]+)"')


def extract_post_images(html: str) -> dict:
    # cover: og:image 優先、無ければ JSON-LD image.url
    cover = None
    m = _OG_IMAGE_RE.search(html)
    if m:
        cover = m.group(1)
    else:
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            for item in (data if isinstance(data, list) else [data]):
                if isinstance(item, dict) and item.get("@type") in ("BlogPosting", "Article", "NewsArticle"):
                    img = item.get("image")
                    if isinstance(img, dict) and img.get("url"):
                        cover = img["url"]
    cover_id = None
    if cover:
        cm = re.search(r'/media/([A-Za-z0-9_~%.-]+\.(?:jpg|jpeg|png|gif|webp))', cover)
        cover_id = cm.group(1) if cm else None
    # images: media id ごとの最大幅、200以上、cover と同一 id は除外
    maxw: dict[str, int] = {}
    order: list[str] = []
    for mid, w in _WIX_IMG_RE.findall(html):
        if mid not in maxw:
            order.append(mid)
        maxw[mid] = max(maxw.get(mid, 0), int(w) if w else 0)
    images = [
        f"https://static.wixstatic.com/media/{mid}"
        for mid in order
        if maxw[mid] >= 200 and mid != cover_id
    ]
    return {"images": images, "cover": cover}


def parse_sitemap(xml: str) -> list[str]:
    root = ET.fromstring(xml)
    locs = []
    for el in root.iter():
        if el.tag.endswith("}loc") or el.tag == "loc":
            url = (el.text or "").strip()
            if "/post/" in url:
                locs.append(url)
    return locs


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


_MDJ_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")          # 12月21日
_MD_SLASH_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[/／]\s*(\d{1,2})(?!\d)")           # 5/31
_MD_HYPHEN_RE = re.compile(r"(?<!\d)(\d{1,2})\s*-\s*(\d{1,2})(?![\d月年回名人時])")  # 5-31（月範囲等を除外）


def extract_event_date(title: str, pub_date: datetime.date) -> datetime.date | None:
    t = unicodedata.normalize("NFKC", title)
    m = _MDJ_RE.search(t) or _MD_SLASH_RE.search(t) or _MD_HYPHEN_RE.search(t)
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
    ("自転車教室", ["自転車教室", "じてんしゃ教室", "マウンテンバイク教室"]),
    ("里山整備", ["里山", "里山道整備", "道普請"]),
    ("定期作業", ["名栗定期作業", "定期作業", "定期整備", "じてんしゃ広場", "自転車広場"]),
    ("清掃活動", ["清掃", "ごみゼロ", "ごみゼロの日"]),
    ("ライド", ["ライド"]),
]


def classify_activity(title: str) -> str:
    for label, keywords in _ACTIVITY_RULES:
        if any(k in title for k in keywords):
            return label
    return "その他"


_LEADING_DATE_RE = re.compile(
    r"^\s*[【\[]?\s*(?:\d{1,2}\s*月\s*\d{1,2}\s*日|\d{1,2}\s*[/／-]\s*\d{1,2})"
    r"\s*(?:[（(][^）)]*[）)])?\s*[-－]?\s*の?"
)
_TRAILING_RE = re.compile(
    r"(?:のお知らせ|のご案内|のご報告|の報告|を開催しました|を開催します|報告)\s*[】\]]?\s*$"
)
_TRAILING_PAREN_RE = re.compile(r"[（(]\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*[）)]\s*$")


def clean_summary(title: str) -> str:
    s = unicodedata.normalize("NFKC", title)
    stripped = _LEADING_DATE_RE.sub("", s)
    # 日付除去の結果が助詞で始まる(=日付が文に組み込まれている)場合は、日付を残す
    if re.match(r"^\s*[はがのをにへとでも]", stripped):
        stripped = s
    s = stripped
    s = _TRAILING_PAREN_RE.sub("", s)
    s = _TRAILING_RE.sub("", s)
    s = s.strip(" 　【】[]-－、，")
    return s if s else unicodedata.normalize("NFKC", title).strip()


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
                "body": it.get("body") or "",
                "images": list(it.get("images") or []),
            },
        }
        groups.setdefault(date, []).append(rec)

    events = []
    for date in sorted(groups):
        recs = groups[date]
        ordered = [r for r in recs if r["kind"] == "report"] + \
                  [r for r in recs if r["kind"] != "report"]
        category = next((r["category"] for r in ordered if r["category"] != "その他"), "その他")
        if category != "その他":
            summary = next(r["summary"] for r in ordered if r["category"] == category)
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


def event_to_yaml_dict(event: dict, fetched: datetime.date,
                       crawler: str = "cal-omc-blog-fetch") -> dict:
    posts = []
    for s in event["sources"]:
        p = {"kind": s["kind"], "url": s["url"], "title": s["title"],
             "published": s["published"].isoformat()}
        if s["kind"] != "report" and s.get("body"):
            p["body"] = s["body"]
        if s.get("images"):
            p["images"] = list(s["images"])
        posts.append(p)
    return {
        "summary": event["summary"],
        "date": event["date"].isoformat(),
        "all_day": event["all_day"],
        "category": event["category"],
        "description": "出典: " + _report_or_first_url(event),
        "source": {
            "type": "omc-blog",
            "crawler": crawler,
            "fetched": fetched.isoformat(),
            "posts": posts,
        },
    }


_UNSAFE_FN_RE = re.compile(r'[<>:"\\|?*\x00-\x1f]')


def slugify_post_url(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    after = path.split("/post/", 1)[1] if "/post/" in path else path
    after = urllib.parse.unquote(after).strip("/")
    after = after.replace("/", "_")
    after = _UNSAFE_FN_RE.sub("", after)
    return after


def dump_archive_yaml(record: dict) -> str:
    return yaml.safe_dump(record, allow_unicode=True, sort_keys=False)


def event_filename(event: dict) -> str:
    d = event["date"]
    return "%04d/%02d-%02d_%s.yaml" % (d.year, d.month, d.day, event["uid"])
