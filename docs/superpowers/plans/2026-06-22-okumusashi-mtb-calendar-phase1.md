# 奥武蔵マウンテンバイク友の会 暦体 Phase 1 (RSS コア) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OMC リポジトリを整備し、Wix ブログの RSS フィードから奥武蔵マウンテンバイク友の会の活動イベントを抽出して canonical な `events/<year>/<MM-DD>_<uid>.yaml` を生成する、テスト済みの決定論クローラを作る。

**Architecture:** 純粋な解析ロジック (日付抽出・年補正・お知らせ/報告の重複排除・種別分類・要約) を `bin/omc_parse.py` に置き pytest で固める。CLI `bin/cal-omc-blog-fetch` は HTTP 取得とファイル出力だけを担い、解析は `omc_parse` に委譲する。飯能の前例 `city-tecoli/city-data/hanno-data/calendar/` に準拠 (YAML が canonical、`source:` 付き = クローラ管理)。

**Tech Stack:** Python 3.10+ / 標準ライブラリ (urllib, xml.etree, re, hashlib, datetime) / PyYAML / pytest。LLM・外部 API は使わない。

## Global Constraints

- イベントの正は Google Calendar、canonical は OMC の `events/*.yaml` (本 plan が生成する)。
- イベント日 = 記事タイトル内の `M/D`。投稿日 (`pubDate`) は報告日であり**イベント日ではない**。
- 全イベント**終日** (all_day) として出力する (時刻情報は本 Phase では扱わない)。
- クローラが生成するイベントは必ず `source.type: omc-blog` を持つ (クローラ管理の印)。
- 対象 RSS: `https://okumusashimtb.wixsite.com/omcweb/blog-feed.xml` (最新 20 件)。
- 出力先: `calendar/events/<year>/<MM-DD>_<uid>.yaml` (1 イベント 1 ファイル、冪等)。
- 文字列はすべて UTF-8。日本語をそのまま保持する (ASCII 化しない)。
- 作業ディレクトリのルートは OMC リポジトリ (`/Users/utashiro/Git/tecolicom/OMC`)。

---

## File Structure

- `README.md` — 暦体の概要・運用手順・city-tecoli 登録先 (Task 1)
- `idea.yaml` — 暦体の正規メタ。`global-ideas.yaml` 転記元の記録 (Task 1)
- `calendar/README.md` — カレンダー運用説明 (Task 1)
- `calendar/bin/omc_parse.py` — 純解析ロジック (Task 2〜6)。テスト対象
- `calendar/bin/cal-omc-blog-fetch` — CLI。RSS 取得 → omc_parse → YAML 出力 (Task 7〜8)
- `calendar/tests/test_omc_parse.py` — omc_parse の単体テスト (Task 2〜6)
- `calendar/tests/test_golden.py` — 固定 RSS → 期待 YAML のゴールデン回帰 (Task 9)
- `calendar/tests/fixtures/feed-sample.xml` — 固定 RSS スナップショット (Task 9)
- `calendar/tests/golden/` — 期待出力 YAML (Task 9)
- `calendar/events/` — 生成物 (Task 8 で初投入)

---

### Task 1: リポジトリ整備 (README / idea.yaml / calendar 雛形)

**Files:**
- Create: `README.md`
- Create: `idea.yaml`
- Create: `calendar/README.md`
- Create: `calendar/bin/.gitkeep`
- Create: `calendar/events/.gitkeep`

**Interfaces:**
- Consumes: なし
- Produces: `idea.yaml` (city-tecoli の `global-ideas.yaml` へ転記する正規メタ)

- [ ] **Step 1: `idea.yaml` を作成**

```yaml
# 暦体「奥武蔵マウンテンバイク友の会」の正規メタ。
# city-tecoli/src/data/global-ideas.yaml の ideas[] へこの内容を転記する (Phase 4)。
# id は idea:global:okumusashi-mtb、公開 URL は https://city.tecoli.com/ideas/okumusashi-mtb/
slug: okumusashi-mtb
name_ja: 奥武蔵マウンテンバイク友の会
name_en: Okumusashi MTB Club
url: https://okumusashimtb.wixsite.com/omcweb
calendars:
  - ical_url: https://calendar.google.com/calendar/ical/okumusashi.mtb%40gmail.com/public/basic.ics
    label: 日本語
    default_on: true
google_calendar_id: okumusashi.mtb@gmail.com
```

- [ ] **Step 2: `README.md` を作成**

```markdown
# OMC — 奥武蔵マウンテンバイク友の会 暦体

city.tecoli.com の暦体 `/ideas/okumusashi-mtb/` を管理するデータリポジトリ。

- イベントの正 (source of truth): Google Calendar `okumusashi.mtb@gmail.com`
- canonical データ: `calendar/events/<year>/<MM-DD>_<uid>.yaml`
- 公式サイト (クロール元): https://okumusashimtb.wixsite.com/omcweb

## 構成

- `idea.yaml` — 暦体メタ (city-tecoli の global-ideas.yaml 転記元)
- `calendar/` — クローラと canonical イベント (詳細は calendar/README.md)

## 設計

docs/superpowers/specs/2026-06-22-okumusashi-mtb-calendar-design.md を参照。
```

- [ ] **Step 3: `calendar/README.md` を作成**

```markdown
# calendar/

Wix ブログの活動履歴 → canonical YAML → Google Calendar 投影 のパイプライン。

- `bin/cal-omc-blog-fetch` — Wix ブログ RSS クローラ (events YAML 生成)
- `bin/omc_parse.py` — 解析ロジック (テスト対象)
- `events/<year>/<MM-DD>_<uid>.yaml` — canonical イベント (`source:` 付き = クローラ管理)
- `tests/` — 単体 + ゴールデン回帰テスト

## 使い方

    python3 bin/cal-omc-blog-fetch          # RSS を取得し events/ を更新
    python3 -m pytest tests/                 # テスト

`source:` を持たない手動イベントはクローラが触らない。
```

- [ ] **Step 4: 空ディレクトリ保持用の `.gitkeep` を作成**

```bash
mkdir -p calendar/bin calendar/events
touch calendar/bin/.gitkeep calendar/events/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add README.md idea.yaml calendar/README.md calendar/bin/.gitkeep calendar/events/.gitkeep
git commit -m "scaffold: OMC リポジトリ整備 (README / idea.yaml / calendar 雛形)"
```

---

### Task 2: RSS パース (`parse_rss`)

**Files:**
- Create: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: なし
- Produces: `parse_rss(xml: str) -> list[dict]`。各 dict は `{"title": str, "link": str, "guid": str, "pub_date": datetime.date}`。RSS の `<item>` を出現順に返す。

- [ ] **Step 1: 失敗するテストを書く**

`calendar/tests/test_omc_parse.py`:

```python
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import omc_parse


RSS = """<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title>
<link>https://okumusashimtb.wixsite.com/omcweb/post/a</link>
<guid>guid-a</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item>
<item><title><![CDATA[6/14第13回総会のお知らせ]]></title>
<link>https://okumusashimtb.wixsite.com/omcweb/post/b</link>
<guid>guid-b</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item>
</channel></rss>"""


def test_parse_rss_extracts_items_in_order():
    items = omc_parse.parse_rss(RSS)
    assert len(items) == 2
    assert items[0]["title"] == "6/7 名栗定期作業の報告"
    assert items[0]["guid"] == "guid-a"
    assert items[0]["link"] == "https://okumusashimtb.wixsite.com/omcweb/post/a"
    assert items[0]["pub_date"] == datetime.date(2026, 6, 11)
    assert items[1]["title"] == "6/14第13回総会のお知らせ"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py::test_parse_rss_extracts_items_in_order -v`
Expected: FAIL (`AttributeError: module 'omc_parse' has no attribute 'parse_rss'`)

- [ ] **Step 3: 最小実装を書く**

`calendar/bin/omc_parse.py`:

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py::test_parse_rss_extracts_items_in_order -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: RSS パース parse_rss"
```

---

### Task 3: イベント日抽出と年補正 (`extract_event_date`)

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: なし
- Produces: `extract_event_date(title: str, pub_date: datetime.date) -> datetime.date | None`。タイトル内の最初の `M/D` (半角/全角スラッシュ、`【…】` 内も可) を取り、年は `pub_date` の年を既定、`event_month - pub_date.month > 6` のとき前年に補正する。`M/D` が無ければ `None`。

- [ ] **Step 1: 失敗するテストを書く**

`calendar/tests/test_omc_parse.py` に追記:

```python
import datetime as _dt


def test_extract_event_date_basic():
    d = omc_parse.extract_event_date("6/7 名栗定期作業の報告", _dt.date(2026, 6, 11))
    assert d == _dt.date(2026, 6, 7)


def test_extract_event_date_no_space():
    d = omc_parse.extract_event_date("1/18日高市道路清掃", _dt.date(2026, 1, 20))
    assert d == _dt.date(2026, 1, 18)


def test_extract_event_date_in_brackets():
    d = omc_parse.extract_event_date("【2/15(日)の活動報告】", _dt.date(2026, 2, 20))
    assert d == _dt.date(2026, 2, 15)


def test_extract_event_date_fullwidth_slash():
    d = omc_parse.extract_event_date("12／28 年末作業の報告", _dt.date(2027, 1, 5))
    # 12 月のイベントを 1 月に報告 → 前年補正
    assert d == _dt.date(2026, 12, 28)


def test_extract_event_date_none():
    d = omc_parse.extract_event_date("【日高市感謝状贈呈式出席の報告】", _dt.date(2026, 2, 28))
    assert d is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k extract_event_date -v`
Expected: FAIL (`AttributeError: ... extract_event_date`)

- [ ] **Step 3: 最小実装を書く**

`calendar/bin/omc_parse.py` に追記:

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k extract_event_date -v`
Expected: PASS (5 件)

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: イベント日抽出と年補正 extract_event_date"
```

---

### Task 4: 投稿種別と種別分類 (`post_kind` / `classify_activity`)

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `post_kind(title: str) -> str` — `"report"` (報告/しました/ご報告) / `"announce"` (お知らせ/します/開催します) / `"other"`。報告判定を先に評価する。
  - `classify_activity(title: str) -> str` — キーワードで活動種別を返す: `定期作業` / `里山整備` / `清掃活動` / `自転車教室` / `総会` / `その他`。

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_post_kind():
    assert omc_parse.post_kind("6/7 名栗定期作業の報告") == "report"
    assert omc_parse.post_kind("4/19子ども自転車教室を開催しました") == "report"
    assert omc_parse.post_kind("6/14第13回総会のお知らせ") == "announce"
    assert omc_parse.post_kind("4/19子ども自転車教室を開催します") == "announce"


def test_classify_activity():
    assert omc_parse.classify_activity("6/7 名栗定期作業の報告") == "定期作業"
    assert omc_parse.classify_activity("5/17飯能市里山清掃活動の報告") == "里山整備"
    assert omc_parse.classify_activity("5/31日高市ごみゼロの日活動報告") == "清掃活動"
    assert omc_parse.classify_activity("4/19子ども自転車教室を開催します") == "自転車教室"
    assert omc_parse.classify_activity("6/14第13回総会のお知らせ") == "総会"
    assert omc_parse.classify_activity("1/18日高市道路清掃") == "清掃活動"
    assert omc_parse.classify_activity("謎のイベント") == "その他"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k "post_kind or classify_activity" -v`
Expected: FAIL

- [ ] **Step 3: 最小実装を書く**

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k "post_kind or classify_activity" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: 投稿種別 post_kind と種別分類 classify_activity"
```

---

### Task 5: summary 整形 (`clean_summary`)

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: なし
- Produces: `clean_summary(title: str) -> str` — タイトルから先頭の `M/D` (曜日 `(日)` 付きも) と `【】`、末尾の「のお知らせ / の報告 / のご報告 / を開催します / を開催しました / 活動報告 / 報告」を除いた活動名。空になったら元タイトルを返す。

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_clean_summary():
    assert omc_parse.clean_summary("6/7 名栗定期作業の報告") == "名栗定期作業"
    assert omc_parse.clean_summary("6/14第13回総会のお知らせ") == "第13回総会"
    assert omc_parse.clean_summary("4/19子ども自転車教室を開催しました") == "子ども自転車教室"
    assert omc_parse.clean_summary("【2/15(日)の活動報告】") == "活動"
    assert omc_parse.clean_summary("1/18日高市道路清掃") == "日高市道路清掃"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k clean_summary -v`
Expected: FAIL

- [ ] **Step 3: 最小実装を書く**

```python
_LEADING_DATE_RE = re.compile(r"^\s*[【\[]?\s*\d{1,2}\s*[/／]\s*\d{1,2}\s*(?:\([^)]*\))?\s*の?")
_TRAILING_RE = re.compile(
    r"(?:のお知らせ|のご報告|の報告|を開催しました|を開催します|活動報告|報告)\s*[】\]]?\s*$"
)


def clean_summary(title: str) -> str:
    s = _LEADING_DATE_RE.sub("", title)
    s = _TRAILING_RE.sub("", s)
    s = s.strip(" 　【】[]")
    return s if s else title.strip()
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k clean_summary -v`
Expected: PASS

(注: `【2/15(日)の活動報告】` は先頭日付除去で `活動報告】` → 末尾 `活動報告` 除去で `活動` になる。意図どおり。)

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: summary 整形 clean_summary"
```

---

### Task 6: イベント組み立てと重複排除 (`build_events`)

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: `parse_rss` の item dict 群、`extract_event_date` / `post_kind` / `classify_activity` / `clean_summary`
- Produces: `build_events(items: list[dict]) -> list[dict]`。各イベント dict は:
  ```python
  {
    "date": datetime.date, "summary": str, "category": str, "all_day": True,
    "uid": str,                      # 12 桁の安定ハッシュ
    "sources": [ {"kind": str, "url": str, "title": str, "published": datetime.date}, ... ],
  }
  ```
  - イベント日が `None` の item は除外 (件数は呼び出し側でログ)。
  - 同一 `(date, category)` の item を 1 イベントに統合。`summary` は report 優先、無ければ最初の item。
  - `uid` = `(date, category)` から導出した `hashlib.sha1` の先頭 12 桁 (順不同で安定)。
  - 出力はイベント日の昇順。

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_build_events_dedups_announce_and_report():
    items = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title><link>https://x/report</link>
<guid>g1</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item>
<item><title><![CDATA[6/7名栗定期作業のお知らせ]]></title><link>https://x/announce</link>
<guid>g2</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item>
<item><title><![CDATA[6/14第13回総会のお知らせ]]></title><link>https://x/soukai</link>
<guid>g3</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item>
</channel></rss>""")
    events = omc_parse.build_events(items)
    assert len(events) == 2
    e0 = events[0]
    assert e0["date"].isoformat() == "2026-06-07"
    assert e0["summary"] == "名栗定期作業"
    assert e0["category"] == "定期作業"
    assert e0["all_day"] is True
    assert {s["kind"] for s in e0["sources"]} == {"report", "announce"}
    assert events[1]["summary"] == "第13回総会"


def test_build_events_skips_dateless():
    items = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[【日高市感謝状贈呈式出席の報告】]]></title><link>https://x/k</link>
<guid>g</guid><pubDate>Sat, 28 Feb 2026 00:00:00 GMT</pubDate></item>
</channel></rss>""")
    assert omc_parse.build_events(items) == []


def test_build_events_uid_stable_regardless_of_order():
    a = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title><link>https://x/r</link>
<guid>g1</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item></channel></rss>""")
    b = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7名栗定期作業のお知らせ]]></title><link>https://x/a</link>
<guid>g2</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item></channel></rss>""")
    assert omc_parse.build_events(a)[0]["uid"] == omc_parse.build_events(b)[0]["uid"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k build_events -v`
Expected: FAIL

- [ ] **Step 3: 最小実装を書く**

```python
import hashlib


def _uid_for(date: datetime.date, category: str) -> str:
    return hashlib.sha1(f"{date.isoformat()}|{category}".encode("utf-8")).hexdigest()[:12]


def build_events(items: list[dict]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for it in items:
        date = extract_event_date(it["title"], it["pub_date"])
        if date is None:
            continue
        category = classify_activity(it["title"])
        key = (date, category)
        src = {
            "kind": post_kind(it["title"]),
            "url": it["link"],
            "title": it["title"],
            "published": it["pub_date"],
        }
        if key not in groups:
            groups[key] = {
                "date": date, "category": category, "all_day": True,
                "uid": _uid_for(date, category),
                "summary": clean_summary(it["title"]),
                "_summary_from_report": src["kind"] == "report",
                "sources": [src],
            }
        else:
            g = groups[key]
            g["sources"].append(src)
            if src["kind"] == "report" and not g["_summary_from_report"]:
                g["summary"] = clean_summary(it["title"])
                g["_summary_from_report"] = True
    events = []
    for g in sorted(groups.values(), key=lambda g: g["date"]):
        g.pop("_summary_from_report", None)
        events.append(g)
    return events
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k build_events -v`
Expected: PASS (3 件)。続けて全体: `python3 -m pytest tests/test_omc_parse.py -v` で全件 PASS。

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: イベント組み立てと重複排除 build_events"
```

---

### Task 7: イベント YAML 直列化 (`event_to_yaml_dict`)

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: `build_events` の event dict
- Produces:
  - `event_to_yaml_dict(event: dict, fetched: datetime.date) -> dict` — canonical YAML へ書く順序付き dict 相当 (キー: `summary`, `date`(ISO 文字列), `all_day`, `category`, `description`, `source`)。`source` は `{type: "omc-blog", crawler: "cal-omc-blog-fetch", fetched: ISO, posts: [...]}`。`description` は report の URL (無ければ最初の source の URL) を `出典: <url>` として入れる。
  - `event_filename(event: dict) -> str` — `"<year>/<MM-DD>_<uid>.yaml"`。

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_event_to_yaml_dict_and_filename():
    items = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title><link>https://x/report</link>
<guid>g1</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item>
<item><title><![CDATA[6/7名栗定期作業のお知らせ]]></title><link>https://x/announce</link>
<guid>g2</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item>
</channel></rss>""")
    e = omc_parse.build_events(items)[0]
    d = omc_parse.event_to_yaml_dict(e, _dt.date(2026, 6, 22))
    assert d["summary"] == "名栗定期作業"
    assert d["date"] == "2026-06-07"
    assert d["all_day"] is True
    assert d["category"] == "定期作業"
    assert "出典: https://x/report" in d["description"]
    assert d["source"]["type"] == "omc-blog"
    assert d["source"]["fetched"] == "2026-06-22"
    assert len(d["source"]["posts"]) == 2
    assert omc_parse.event_filename(e) == "2026/06-07_%s.yaml" % e["uid"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k event_to_yaml -v`
Expected: FAIL

- [ ] **Step 3: 最小実装を書く**

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k event_to_yaml -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: イベント YAML 直列化 event_to_yaml_dict"
```

---

### Task 8: CLI `cal-omc-blog-fetch` (RSS 取得 → events 書き出し)

**Files:**
- Create: `calendar/bin/cal-omc-blog-fetch`
- Test: `calendar/tests/test_cli.py`

**Interfaces:**
- Consumes: `omc_parse.parse_rss` / `build_events` / `event_to_yaml_dict` / `event_filename`
- Produces: 実行可能 CLI。`--feed-file <path>` でローカル RSS から、無指定なら本番 RSS URL から取得。`--out-dir <dir>` (既定 `events`) 配下に YAML を書く。`--fetched YYYY-MM-DD` で取得日固定 (テスト用)。標準出力に生成件数を出す。

- [ ] **Step 1: 失敗するテストを書く**

`calendar/tests/test_cli.py`:

```python
import os, subprocess, sys, glob

BIN = os.path.join(os.path.dirname(__file__), "..", "bin", "cal-omc-blog-fetch")
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "feed-min.xml")


def _write_fixture():
    os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
    with open(FIXTURE, "w", encoding="utf-8") as f:
        f.write("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title><link>https://x/r</link>
<guid>g1</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item>
</channel></rss>""")


def test_cli_writes_event_yaml(tmp_path):
    _write_fixture()
    out = tmp_path / "events"
    r = subprocess.run(
        [sys.executable, BIN, "--feed-file", FIXTURE, "--out-dir", str(out),
         "--fetched", "2026-06-22"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    files = glob.glob(str(out / "2026" / "06-07_*.yaml"))
    assert len(files) == 1
    body = open(files[0], encoding="utf-8").read()
    assert "summary: 名栗定期作業" in body
    assert "type: omc-blog" in body
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd calendar && python3 -m pytest tests/test_cli.py -v`
Expected: FAIL (CLI が存在しない / 非実行)

- [ ] **Step 3: 最小実装を書く**

`calendar/bin/cal-omc-blog-fetch`:

```python
#!/usr/bin/env python3
"""cal-omc-blog-fetch — 奥武蔵 MTB ブログ RSS → canonical イベント YAML.

Phase 1 は RSS (最新 20 件) のみ。全履歴 (ヘッドレス) は後続 Phase で追加する。
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import omc_parse  # noqa: E402
import yaml  # noqa: E402

FEED_URL = "https://okumusashimtb.wixsite.com/omcweb/blog-feed.xml"


def _load_feed(feed_file: str | None) -> str:
    if feed_file:
        with open(feed_file, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed-file", default=None)
    ap.add_argument("--out-dir", default="events")
    ap.add_argument("--fetched", default=None, help="YYYY-MM-DD (既定: 今日)")
    args = ap.parse_args()

    fetched = (datetime.date.fromisoformat(args.fetched)
               if args.fetched else datetime.date.today())
    items = omc_parse.parse_rss(_load_feed(args.feed_file))
    events = omc_parse.build_events(items)

    written = 0
    for ev in events:
        rel = omc_parse.event_filename(ev)
        path = os.path.join(args.out_dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        doc = omc_parse.event_to_yaml_dict(ev, fetched)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
        written += 1

    skipped = len(items) - sum(len(e["sources"]) for e in events)
    print(f"items={len(items)} events={written} skipped_items={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 実行権限を付与しテストが通ることを確認**

Run:
```bash
chmod +x calendar/bin/cal-omc-blog-fetch
cd calendar && python3 -m pytest tests/test_cli.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/cal-omc-blog-fetch calendar/tests/test_cli.py calendar/tests/fixtures/feed-min.xml
git commit -m "feat: CLI cal-omc-blog-fetch (RSS → events YAML)"
```

---

### Task 9: ゴールデン回帰テスト (実 RSS スナップショット)

**Files:**
- Create: `calendar/tests/fixtures/feed-sample.xml`
- Create: `calendar/tests/golden/` (期待 YAML 群)
- Create: `calendar/tests/test_golden.py`

**Interfaces:**
- Consumes: CLI `cal-omc-blog-fetch`
- Produces: 実 RSS のスナップショットを固定入力に、`events/` 出力をバイト一致でロックする回帰テスト。

- [ ] **Step 1: 実 RSS をフィクスチャとして保存**

Run:
```bash
mkdir -p calendar/tests/fixtures
curl -sSL -A "Mozilla/5.0" -o calendar/tests/fixtures/feed-sample.xml \
  https://okumusashimtb.wixsite.com/omcweb/blog-feed.xml
```
(以後このファイルは更新しない = 固定スナップショット)

- [ ] **Step 2: 期待出力 (golden) を生成して目視レビュー**

Run:
```bash
cd calendar && python3 bin/cal-omc-blog-fetch \
  --feed-file tests/fixtures/feed-sample.xml --out-dir tests/golden --fetched 2026-06-22
ls -R tests/golden
```
生成された各 YAML を**目視レビュー**する (spec のチェックポイント)。`date` / `summary` / `category` が
活動内容と一致するか確認。誤りがあれば該当 Task のロジック/ルールを修正してから再生成する。
期待件数の目安: 2026-01〜06 の unique イベント約 10〜11 件。

- [ ] **Step 3: ゴールデンテストを書く**

`calendar/tests/test_golden.py`:

```python
import os, subprocess, sys, filecmp

HERE = os.path.dirname(__file__)
BIN = os.path.join(HERE, "..", "bin", "cal-omc-blog-fetch")
FIXTURE = os.path.join(HERE, "fixtures", "feed-sample.xml")
GOLDEN = os.path.join(HERE, "golden")


def test_golden_matches(tmp_path):
    out = tmp_path / "events"
    r = subprocess.run(
        [sys.executable, BIN, "--feed-file", FIXTURE, "--out-dir", str(out),
         "--fetched", "2026-06-22"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    expected = []
    for root, _, files in os.walk(GOLDEN):
        for fn in files:
            expected.append(os.path.relpath(os.path.join(root, fn), GOLDEN))
    assert expected, "golden が空"
    for rel in expected:
        got = os.path.join(str(out), rel)
        assert os.path.exists(got), f"未生成: {rel}"
        assert filecmp.cmp(os.path.join(GOLDEN, rel), got, shallow=False), \
            f"差分: {rel}"
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd calendar && python3 -m pytest tests/ -v`
Expected: PASS (単体 + CLI + golden すべて)

- [ ] **Step 5: Commit**

```bash
git add calendar/tests/fixtures/feed-sample.xml calendar/tests/golden calendar/tests/test_golden.py
git commit -m "test: 実 RSS スナップショットのゴールデン回帰テスト"
```

---

### Task 10: 本番 events/ の初回生成と確定

**Files:**
- Create: `calendar/events/2026/*.yaml` (生成物)

**Interfaces:**
- Consumes: CLI
- Produces: レビュー済みの canonical イベント (本番 `calendar/events/`)。

- [ ] **Step 1: 本番 events を生成**

Run:
```bash
cd calendar && python3 bin/cal-omc-blog-fetch --fetched 2026-06-22
```
(本番 RSS から取得。`events/.gitkeep` は残す)

- [ ] **Step 2: 生成物を目視レビュー**

Run: `ls -R calendar/events && cat calendar/events/2026/*.yaml`
各イベントの `date` / `summary` / `category` を活動内容と照合。日付なし記事 (例「日高市感謝状贈呈式」)
が落ちていること、お知らせ/報告ペアが 1 件に統合されていることを確認。

- [ ] **Step 3: Commit**

```bash
git add calendar/events
git commit -m "data: 2026 上半期の活動イベント (RSS 由来) を初回生成"
```

---

## このプランの完了条件

- `cd calendar && python3 -m pytest tests/ -v` が全 PASS。
- `calendar/events/2026/` にレビュー済みの canonical イベント YAML が存在する。
- OMC リポジトリに README / idea.yaml / calendar 一式がコミットされている。

## 後続プラン (本プランの対象外 — Phase 1 完了後に詳細化)

- **Phase 2**: ヘッドレス (Claude in Chrome) で Wix Blog API を `instance` トークン付きで
  ページネーション取得し、全履歴 (2013〜2025) を `sources/blog/` にキャッシュ → `omc_parse` で
  過去へ延伸。古い記事のタイトル規約差を実データで確認してからルール拡張・golden 追加。
- **Phase 3**: `cal-omc` 投影ラッパ (`gws` + Service Account)。`events/` → Google Calendar upsert
  (iCalUID キーで冪等)、`snapshots/` ミラー。利用者の SA 鍵・カレンダー共有が前提。
- **Phase 4**: city-tecoli への暦体登録。**【訂正 2026-06-29】** omc は **Blobs 動的エンティティ**として
  **管理 UI で登録**する（`global-ideas.yaml`=config seed には入れない。このリポジトリから city-tecoli は編集しない）。
  公開 URL は `/ideas/okumusashi-mtb/`。
