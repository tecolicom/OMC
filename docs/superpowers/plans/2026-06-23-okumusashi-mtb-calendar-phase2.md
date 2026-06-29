# 奥武蔵マウンテンバイク友の会 暦体 Phase 2 (全履歴アーカイブ) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wix ブログの全履歴 (sitemap 経由の 359 記事、2016〜2026) を curl で取得し、各記事の JSON-LD から canonical イベント YAML を生成して Phase 1 の `events/` を過去へ延伸する。日付が抽出できない記事はスキップしてレビュー一覧に出す。

**Architecture:** Phase 1 が確立した「純解析ロジック (`omc_parse.py`) + 薄い I/O CLI + canonical YAML + golden テスト」を踏襲・再利用する。Phase 2 はヘッドレスブラウザを使わず、`blog-posts-sitemap.xml` で全記事 URL を列挙し、各記事ページの JSON-LD (`BlogPosting` の `headline` / `datePublished`) を curl で取得する決定論経路。日付抽出器 `extract_event_date` を旧形式 (`M月D日`・全角・ハイフン) 対応に拡張し、`build_events` の date ベース dedup をそのまま使う。

**Tech Stack:** Python 3.10+ / 標準ライブラリ (urllib, xml.etree, re, json, unicodedata, hashlib, datetime, time) / PyYAML / pytest。LLM・外部 API・ブラウザは使わない。

## Global Constraints

- イベントの正は Google Calendar、canonical は OMC の `events/<year>/<MM-DD>_<uid>.yaml` (Phase 1 と同形式)。
- イベント日 = 記事タイトル (JSON-LD `headline`) 内の日付。`datePublished` は投稿(報告)日であり**イベント日ではない**。年の既定は `datePublished` の年、`event_month - pub_month > 6` のとき前年補正 (Phase 1 と同一規則)。
- 全イベント**終日** (`all_day: True`)、`source.type: "omc-blog"` (Phase 1 と同一)。dedup は **date 単位** (Phase 1 で確定済み)。
- 日付を抽出できない記事 (月のみ・範囲予定・日付なし) は **events に書かず**、`calendar/events-review-needed.txt` に `<url>\t<title>\t<理由>` で記録する (推測で日付を捏造しない)。
- 日本語はすべて UTF-8 でそのまま保持 (ASCII 化しない)。`omc_parse.py` は純ロジック、CLI は I/O のみ。
- Phase 1 の既存 10 イベントと golden テストは**壊さない** (`extract_event_date` 拡張は後方互換、Phase 1 golden が引き続き一致すること)。
- クロール入力キャッシュは `calendar/sources/blog/` (.gitignore 済み) に置き、再実行はキャッシュを使う。実サイトへの fetch はリクエスト間に 0.3 秒以上の間隔を空ける。
- 対象 sitemap: `https://okumusashimtb.wixsite.com/omcweb/blog-posts-sitemap.xml`。記事 URL は非 ASCII を含むのでパスを `urllib.parse.quote` でエンコードして取得する。
- 作業ディレクトリのルートは OMC リポジトリ (`/Users/utashiro/Git/tecolicom/OMC`)。

---

## File Structure

- `calendar/bin/omc_parse.py` — 既存。`extract_event_date` / `classify_activity` / `clean_summary` を拡張 (Task 3, 4)。`parse_sitemap` / `extract_post_meta` を追加 (Task 1, 2)。
- `calendar/bin/cal-omc-archive-fetch` — 新規 CLI。sitemap → 記事 fetch(キャッシュ) → build_events → events/ + review 一覧 (Task 5)。
- `calendar/tests/test_omc_parse.py` — 既存。Task 1〜4 の単体テストを追記。
- `calendar/tests/test_archive_cli.py` — 新規。CLI を fixture で検証 (Task 5)。
- `calendar/tests/fixtures/sitemap-sample.xml` — sitemap の小サンプル (Task 5)。
- `calendar/tests/fixtures/post-*.html` — 記事ページの JSON-LD 抽出テスト用 fixture (Task 2)。
- `calendar/events/<year>/...` — 生成物の延伸 (Task 6)。
- `calendar/events-review-needed.txt` — 日付抽出不能記事のレビュー一覧 (Task 5, 6)。
- `calendar/sources/blog/` — fetch キャッシュ (gitignore 済み、コミットしない)。

---

### Task 1: sitemap パース (`parse_sitemap`)

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: なし
- Produces: `parse_sitemap(xml: str) -> list[str]` — `<url><loc>...</loc></url>` の `loc` を出現順に返す。`/post/` を含む URL のみ (ブログ記事に限定)。

- [ ] **Step 1: 失敗するテストを書く** (`test_omc_parse.py` に追記)

```python
def test_parse_sitemap_returns_post_locs_in_order():
    xml = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://okumusashimtb.wixsite.com/omcweb/post/5-31a</loc><lastmod>2026-06-03</lastmod></url>
<url><loc>https://okumusashimtb.wixsite.com/omcweb/post/2017/02/01/b</loc><lastmod>2017-02-01</lastmod></url>
<url><loc>https://okumusashimtb.wixsite.com/omcweb/about-us</loc></url>
</urlset>"""
    locs = omc_parse.parse_sitemap(xml)
    assert locs == [
        "https://okumusashimtb.wixsite.com/omcweb/post/5-31a",
        "https://okumusashimtb.wixsite.com/omcweb/post/2017/02/01/b",
    ]
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k parse_sitemap -v`
Expected: FAIL (`AttributeError: ... parse_sitemap`)

- [ ] **Step 3: 実装** (`omc_parse.py` に追記)

```python
def parse_sitemap(xml: str) -> list[str]:
    root = ET.fromstring(xml)
    locs = []
    for el in root.iter():
        if el.tag.endswith("}loc") or el.tag == "loc":
            url = (el.text or "").strip()
            if "/post/" in url:
                locs.append(url)
    return locs
```

- [ ] **Step 4: 成功確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k parse_sitemap -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: sitemap パース parse_sitemap (Phase 2)"
```

---

### Task 2: 記事 JSON-LD 抽出 (`extract_post_meta`)

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`
- Create: `calendar/tests/fixtures/post-recent.html`, `calendar/tests/fixtures/post-old.html`

**Interfaces:**
- Consumes: なし
- Produces: `extract_post_meta(html: str) -> dict | None` — 記事 HTML 内の `<script type="application/ld+json">` から `@type` が `BlogPosting`/`Article`/`NewsArticle` の要素を探し、`{"title": headline, "pub_date": datetime.date}` を返す。`datePublished` の先頭 10 文字 (`YYYY-MM-DD`) を日付に。見つからなければ `None`。

- [ ] **Step 1: fixture を実サイトから取得** (テストの固定入力にする)

Run:
```bash
mkdir -p calendar/tests/fixtures
python3 - <<'PY'
import urllib.request, urllib.parse
def fetch(u):
    sp = urllib.parse.urlsplit(u)
    u2 = urllib.parse.urlunsplit((sp.scheme, sp.netloc, urllib.parse.quote(sp.path), sp.query, sp.fragment))
    req = urllib.request.Request(u2, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
import re
# JSON-LD だけ抜き出して保存 (HTML 全体は巨大なので ld+json ブロックのみ fixture 化)
for name, url in [
    ("post-recent", "https://okumusashimtb.wixsite.com/omcweb/post/5-31日高市ごみゼロの日活動報告"),
    ("post-old", "https://okumusashimtb.wixsite.com/omcweb/post/2017/02/01/桜並木の整備（２月１６日）"),
]:
    h = fetch(url)
    blocks = re.findall(r'<script type="application/ld\+json">.*?</script>', h, re.S)
    with open(f"calendar/tests/fixtures/{name}.html", "w", encoding="utf-8") as f:
        f.write("\n".join(blocks))
    print(name, "blocks:", len(blocks))
PY
```
(以後この fixture は更新しない)

- [ ] **Step 2: 失敗するテストを書く**

```python
import datetime as _dt  # ファイル先頭の import 群に既にあれば不要

def test_extract_post_meta_recent():
    html = open(os.path.join(os.path.dirname(__file__), "fixtures", "post-recent.html"),
                encoding="utf-8").read()
    meta = omc_parse.extract_post_meta(html)
    assert meta["title"] == "5/31日高市ごみゼロの日活動報告"
    assert meta["pub_date"] == _dt.date(2026, 6, 3)


def test_extract_post_meta_old():
    html = open(os.path.join(os.path.dirname(__file__), "fixtures", "post-old.html"),
                encoding="utf-8").read()
    meta = omc_parse.extract_post_meta(html)
    assert meta["title"] == "桜並木の整備（２月１６日）"
    assert meta["pub_date"] == _dt.date(2017, 2, 1)


def test_extract_post_meta_none():
    assert omc_parse.extract_post_meta("<html><body>no json-ld</body></html>") is None
```

(`import os` がファイル先頭に無ければ追加する)

- [ ] **Step 3: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k extract_post_meta -v`
Expected: FAIL

- [ ] **Step 4: 実装** (`omc_parse.py` に追記。先頭の import に `import json` を追加)

```python
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
                try:
                    pub = datetime.date.fromisoformat(str(published)[:10])
                except ValueError:
                    continue
                return {"title": headline, "pub_date": pub}
    return None
```

- [ ] **Step 5: 成功確認 + commit**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k extract_post_meta -v`
Expected: PASS
```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py calendar/tests/fixtures/post-recent.html calendar/tests/fixtures/post-old.html
git commit -m "feat: 記事 JSON-LD 抽出 extract_post_meta (Phase 2)"
```

---

### Task 3: `extract_event_date` を旧形式対応へ拡張

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: なし
- Produces: 既存 `extract_event_date(title, pub_date) -> datetime.date | None` を拡張。NFKC 正規化後、`M月D日` を優先、無ければ `M/D` または `M-D` を取る。年補正規則は不変。**後方互換**: Phase 1 の全 `extract_event_date` テストと golden が引き続き通る。

- [ ] **Step 1: 失敗するテストを書く** (新形式)

```python
def test_extract_event_date_kanji_md():
    assert omc_parse.extract_event_date("12月21日（日）の活動報告", _dt.date(2025, 12, 23)) == _dt.date(2025, 12, 21)
    assert omc_parse.extract_event_date("7月20日-里山整備活動のご案内", _dt.date(2024, 7, 10)) == _dt.date(2024, 7, 20)


def test_extract_event_date_fullwidth_kanji():
    # 全角「２月１６日」(NFKC で半角化して抽出)
    assert omc_parse.extract_event_date("桜並木の整備（２月１６日）", _dt.date(2017, 2, 1)) == _dt.date(2017, 2, 16)


def test_extract_event_date_hyphen():
    assert omc_parse.extract_event_date("9-15-里山整備活動のお知らせ", _dt.date(2024, 9, 10)) == _dt.date(2024, 9, 15)
    assert omc_parse.extract_event_date("8-4（日）名栗じてんしゃ広場定期作業のお知らせ", _dt.date(2024, 8, 1)) == _dt.date(2024, 8, 4)


def test_extract_event_date_prefers_kanji_over_other_digits():
    # 「第12回」等の数字に引っ張られず、月日を取る
    assert omc_parse.extract_event_date("第12回総会 11月3日 開催報告", _dt.date(2023, 11, 5)) == _dt.date(2023, 11, 3)


def test_extract_event_date_kanji_year_correction():
    # 12 月のイベントを 1 月に報告 → 前年
    assert omc_parse.extract_event_date("12月28日 年末作業の報告", _dt.date(2027, 1, 5)) == _dt.date(2026, 12, 28)
```

- [ ] **Step 2: 既存テストも含めて失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k extract_event_date -v`
Expected: 新テストが FAIL、既存 (basic/no_space/in_brackets/fullwidth_slash/none) は PASS のまま。

- [ ] **Step 3: 実装** (`omc_parse.py` の `extract_event_date` と `_MD_RE` を差し替え。先頭 import に `import unicodedata` を追加)

```python
_MDJ_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")          # 12月21日
_MD_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[/／-]\s*(\d{1,2})(?!\d)")  # 5/31, 5-31, 9-15


def extract_event_date(title: str, pub_date: datetime.date) -> datetime.date | None:
    t = unicodedata.normalize("NFKC", title)
    m = _MDJ_RE.search(t) or _MD_RE.search(t)
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

(注: 旧 `_MD_RE` は全角スラッシュ `／` を含んでいた。新 `_MD_RE` も `[/／-]` で対応し、加えて NFKC 正規化で全角数字・全角スラッシュも吸収する。`(?<!\d)...(?!\d)` で「第12回」内の数字や年などの誤マッチを抑止する。)

- [ ] **Step 4: 全テスト PASS を確認 (Phase 1 回帰含む)**

Run: `cd calendar && python3 -m pytest tests/ -v`
Expected: 既存 (Phase 1 の omc_parse / cli / golden) + 新規すべて PASS。**特に `tests/test_golden.py` が PASS** であること (Phase 1 の 10 イベントが不変)。

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: extract_event_date を M月D日/全角/ハイフン対応に拡張 (後方互換, Phase 2)"
```

---

### Task 4: `classify_activity` / `clean_summary` をアーカイブ語彙へ拡張

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: なし
- Produces: 既存 `classify_activity` / `clean_summary` を拡張。Phase 1 の既存テストは不変で通る。
  - `classify_activity`: 追加キーワード — `里山道整備`→里山整備、`道普請`→里山整備、`じてんしゃ広場`/`自転車広場`→定期作業、`ライド`→ライド(新カテゴリ)。
  - `clean_summary`: 末尾の `のご案内` を追加除去。さらに末尾の `（M月D日）` / `（曜日）` のような括弧注記を除去 (例「桜並木の整備（２月１６日）」→「桜並木の整備」)。

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_classify_activity_archive_vocab():
    assert omc_parse.classify_activity("7月20日-里山道整備活動のご案内") == "里山整備"
    assert omc_parse.classify_activity("鳩山道普請の報告") == "里山整備"
    assert omc_parse.classify_activity("6月2日じてんしゃ広場定期作業のお知らせ") == "定期作業"
    assert omc_parse.classify_activity("12月14日-土-の里山整備活動＆ライドの報告") == "里山整備"
    assert omc_parse.classify_activity("新春ライドのお知らせ") == "ライド"


def test_clean_summary_archive():
    assert omc_parse.clean_summary("7月20日-里山整備活動のご案内") == "里山整備活動"
    assert omc_parse.clean_summary("桜並木の整備（２月１６日）") == "桜並木の整備"
    assert omc_parse.clean_summary("12月21日（日）の活動報告") == "活動"
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k "classify_activity or clean_summary" -v`
Expected: 新テスト FAIL、既存 PASS。

- [ ] **Step 3: 実装** (`_ACTIVITY_RULES` と `clean_summary` 周りを差し替え)

`_ACTIVITY_RULES` を次に差し替え (順序が優先度):

```python
_ACTIVITY_RULES = [
    ("総会", ["総会"]),
    ("自転車教室", ["自転車教室"]),
    ("里山整備", ["里山", "里山道整備", "道普請"]),
    ("定期作業", ["名栗定期作業", "定期作業", "じてんしゃ広場", "自転車広場"]),
    ("清掃活動", ["清掃", "ごみゼロ", "ごみゼロの日"]),
    ("ライド", ["ライド"]),
]
```

`clean_summary` の正規表現を拡張 (先頭日付除去は NFKC 後の `M月D日` も外せるようにし、末尾の括弧注記と `のご案内` を追加):

```python
_LEADING_DATE_RE = re.compile(
    r"^\s*[【\[]?\s*(?:\d{1,2}\s*月\s*\d{1,2}\s*日|\d{1,2}\s*[/／-]\s*\d{1,2})"
    r"\s*(?:[（(][^）)]*[）)])?\s*[-－]?\s*の?"
)
_TRAILING_RE = re.compile(
    r"(?:のお知らせ|のご案内|のご報告|の報告|を開催しました|を開催します|報告)\s*[】\]]?\s*$"
)
_TRAILING_PAREN_RE = re.compile(r"[（(]\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*[）)]\s*$")

# 注: `活動報告` は末尾候補に入れない。入れると「活動報告」全体が消えて空になり、Phase 1 の
# clean_summary("【2/15(日)の活動報告】")=="活動" が壊れる。`報告` だけで「活動報告」→「活動」になる。


def clean_summary(title: str) -> str:
    s = unicodedata.normalize("NFKC", title)
    s = _LEADING_DATE_RE.sub("", s)
    s = _TRAILING_PAREN_RE.sub("", s)
    s = _TRAILING_RE.sub("", s)
    s = s.strip(" 　【】[]-－")
    return s if s else unicodedata.normalize("NFKC", title).strip()
```

(注: `clean_summary` も NFKC 正規化する。Phase 1 の RSS タイトルは既にほぼ半角なので結果は不変。`12月21日（日）の活動報告` → 先頭 `12月21日（日）の` 除去 → `活動報告` → 末尾 `活動報告`→ `報告` の前に `活動報告` は無いので `報告` 除去で `活動`。)

- [ ] **Step 4: 全テスト PASS (Phase 1 回帰含む)**

Run: `cd calendar && python3 -m pytest tests/ -v`
Expected: すべて PASS。`test_golden.py` 含め Phase 1 不変。

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: classify_activity/clean_summary をアーカイブ語彙へ拡張 (Phase 2)"
```

---

### Task 5: CLI `cal-omc-archive-fetch` (sitemap → キャッシュ fetch → events + review 一覧)

**Files:**
- Create: `calendar/bin/cal-omc-archive-fetch`
- Create: `calendar/tests/fixtures/sitemap-sample.xml`
- Test: `calendar/tests/test_archive_cli.py`

**Interfaces:**
- Consumes: `omc_parse.parse_sitemap` / `extract_post_meta` / `build_events` / `event_to_yaml_dict` / `event_filename`
- Produces: 実行可能 CLI。sitemap (URL or `--sitemap-file`) から記事 URL を列挙し、各記事ページを取得 (`--cache-dir` にキャッシュ、既定 `sources/blog`) → `extract_post_meta` → `build_events` → `--out-dir` (既定 `events`) に YAML 出力。日付抽出不能の記事は `--review-file` (既定 `events-review-needed.txt`) に `url\ttitle\treason` で出す。`--fetched YYYY-MM-DD` で取得日固定。`--limit N` で先頭 N 記事のみ (テスト/段階実行用)。標準出力に `posts=.. events=.. skipped=..`。

実装方針:
- 各記事の取得は「キャッシュ優先」: キャッシュキー = URL の sha1。`<cache-dir>/<sha1>.html` があれば読む、無ければ fetch して保存 (fetch 間 0.3 秒 sleep)。fetch は Task 2 Step 1 と同じパス quote 方式。
- `extract_post_meta` が None、または `extract_event_date(meta["title"], meta["pub_date"])` が None の記事 → review 一覧へ (reason は "no-jsonld" / "no-date")。
- それ以外を `{"title","link","guid","pub_date"}` の item にして集約し、最後に `build_events` → YAML 書き出し (`yaml.safe_dump(..., allow_unicode=True, sort_keys=False)`)。

- [ ] **Step 1: 小さな sitemap fixture を作る**

`calendar/tests/fixtures/sitemap-sample.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://okumusashimtb.wixsite.com/omcweb/post/sample-a</loc></url>
</urlset>
```

- [ ] **Step 2: 失敗するテストを書く** (`tests/test_archive_cli.py`)

ローカルキャッシュに記事 HTML を置けば fetch せずに通ることを使う。テストは `--cache-dir` に 1 記事分の JSON-LD を事前配置し、その sha1 ファイル名で読ませる。

```python
import os, subprocess, sys, glob, hashlib

HERE = os.path.dirname(__file__)
BIN = os.path.join(HERE, "..", "bin", "cal-omc-archive-fetch")
SITEMAP = os.path.join(HERE, "fixtures", "sitemap-sample.xml")
POST_URL = "https://okumusashimtb.wixsite.com/omcweb/post/sample-a"
LDJSON = ('<script type="application/ld+json">'
          '{"@type":"BlogPosting","headline":"5/31日高市ごみゼロの日活動報告",'
          '"datePublished":"2026-06-03T02:08:16.709Z"}</script>')


def test_archive_cli_uses_cache_and_writes_event(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    key = hashlib.sha1(POST_URL.encode("utf-8")).hexdigest()
    (cache / f"{key}.html").write_text(LDJSON, encoding="utf-8")
    out = tmp_path / "events"
    review = tmp_path / "review.txt"
    r = subprocess.run(
        [sys.executable, BIN, "--sitemap-file", SITEMAP, "--cache-dir", str(cache),
         "--out-dir", str(out), "--review-file", str(review), "--fetched", "2026-06-22"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    files = glob.glob(str(out / "2026" / "05-31_*.yaml"))
    assert len(files) == 1
    body = open(files[0], encoding="utf-8").read()
    assert "summary: 日高市ごみゼロの日活動" in body
    assert "type: omc-blog" in body
```

- [ ] **Step 3: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_archive_cli.py -v`
Expected: FAIL (CLI 不在)

- [ ] **Step 4: 実装** (`calendar/bin/cal-omc-archive-fetch`)

```python
#!/usr/bin/env python3
"""cal-omc-archive-fetch — Wix ブログ全履歴 (sitemap) → canonical イベント YAML.

sitemap で全記事 URL を列挙し、各記事ページの JSON-LD から headline/datePublished を取り、
イベント日が抽出できたものを events/ に出力する。抽出不能はレビュー一覧へ。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import omc_parse  # noqa: E402
import yaml  # noqa: E402

SITEMAP_URL = "https://okumusashimtb.wixsite.com/omcweb/blog-posts-sitemap.xml"


def _fetch(url: str) -> str:
    sp = urllib.parse.urlsplit(url)
    u2 = urllib.parse.urlunsplit(
        (sp.scheme, sp.netloc, urllib.parse.quote(sp.path), sp.query, sp.fragment))
    req = urllib.request.Request(u2, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _load_cached(url: str, cache_dir: str) -> str:
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    path = os.path.join(cache_dir, f"{key}.html")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    html = _fetch(url)
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    time.sleep(0.3)
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitemap-file", default=None)
    ap.add_argument("--cache-dir", default="sources/blog")
    ap.add_argument("--out-dir", default="events")
    ap.add_argument("--review-file", default="events-review-needed.txt")
    ap.add_argument("--fetched", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    fetched = (datetime.date.fromisoformat(args.fetched)
               if args.fetched else datetime.date.today())

    if args.sitemap_file:
        with open(args.sitemap_file, encoding="utf-8") as f:
            sitemap_xml = f.read()
    else:
        sitemap_xml = _fetch(SITEMAP_URL)
    urls = omc_parse.parse_sitemap(sitemap_xml)
    if args.limit:
        urls = urls[: args.limit]

    items = []
    review = []
    for url in urls:
        html = _load_cached(url, args.cache_dir)
        meta = omc_parse.extract_post_meta(html)
        if meta is None:
            review.append((url, "", "no-jsonld"))
            continue
        if omc_parse.extract_event_date(meta["title"], meta["pub_date"]) is None:
            review.append((url, meta["title"], "no-date"))
            continue
        items.append({"title": meta["title"], "link": url, "guid": url,
                      "pub_date": meta["pub_date"]})

    events = omc_parse.build_events(items)
    for ev in events:
        path = os.path.join(args.out_dir, omc_parse.event_filename(ev))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(omc_parse.event_to_yaml_dict(ev, fetched), f,
                           allow_unicode=True, sort_keys=False)

    if review:
        os.makedirs(os.path.dirname(os.path.abspath(args.review_file)), exist_ok=True)
        with open(args.review_file, "w", encoding="utf-8") as f:
            for url, title, reason in review:
                f.write(f"{url}\t{title}\t{reason}\n")

    print(f"posts={len(urls)} events={len(events)} skipped={len(review)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 実行権限 + テスト + commit**

Run:
```bash
chmod +x calendar/bin/cal-omc-archive-fetch
cd calendar && python3 -m pytest tests/ -v
```
Expected: 全 PASS (Phase 1 + Phase 2 単体 + archive cli)。
```bash
git add calendar/bin/cal-omc-archive-fetch calendar/tests/test_archive_cli.py calendar/tests/fixtures/sitemap-sample.xml
git commit -m "feat: CLI cal-omc-archive-fetch (sitemap 全履歴 → events + review 一覧)"
```

---

### Task 6: 全履歴クロール実行・人間レビュー・本番反映

**Files:**
- Create/Modify: `calendar/events/<year>/*.yaml` (延伸)
- Create: `calendar/events-review-needed.txt`

**Interfaces:**
- Consumes: CLI `cal-omc-archive-fetch`
- Produces: 2016〜2026 のレビュー済み canonical イベント + レビュー一覧。

- [ ] **Step 1: 全履歴を取得・生成** (キャッシュは sources/blog/、gitignore 済み)

Run:
```bash
cd calendar && python3 bin/cal-omc-archive-fetch --fetched 2026-06-22
```
359 記事を順に取得 (初回は数分)。出力 `posts=359 events=.. skipped=..` を記録。

- [ ] **Step 2: 生成イベントを人間レビュー**

Run:
```bash
cd calendar && python3 - <<'PY'
import glob, yaml
for f in sorted(glob.glob("events/*/*.yaml")):
    d = yaml.safe_load(open(f, encoding="utf-8"))
    print(d["date"], "|", d["category"], "|", d["summary"])
PY
```
日付・summary・category が活動内容と整合するか通覧する。特に:
- 旧形式 (`M月D日`・全角・`/YYYY/MM/DD/` パス) の年・日が正しいか。
- 同日に別活動が併存していないか (date dedup で意図せず統合されていないか)。
誤りがあれば該当 Task (3/4) のルールを直し、`bin/cal-omc-archive-fetch` を再実行 (キャッシュ使用で高速) して再確認する。

- [ ] **Step 3: レビュー一覧を確認**

Run: `wc -l calendar/events-review-needed.txt && cat calendar/events-review-needed.txt`
`no-date` (月のみ・範囲・日付なし) が妥当にスキップされているか確認。ここから手動で暦体に足したい行があれば、`source:` を持たない手動イベント YAML として別途追加できる (クローラ不可侵)。本 Task では一覧の出力までを成果とする。

- [ ] **Step 4: 全テスト最終確認**

Run: `cd calendar && python3 -m pytest tests/ -q`
Expected: 全 PASS。

- [ ] **Step 5: Commit** (events 本体と review 一覧。キャッシュ sources/blog はコミットしない = .gitignore 済み)

```bash
git add calendar/events calendar/events-review-needed.txt
git commit -m "data: 2016-2026 の全履歴イベント (sitemap 由来) を生成 + レビュー一覧"
```

---

## このプランの完了条件

- `cd calendar && python3 -m pytest tests/ -q` が全 PASS (Phase 1 の golden を含め不変)。
- `calendar/events/` が 2016〜2026 のレビュー済みイベントで埋まっている。
- `calendar/events-review-needed.txt` に日付抽出不能記事が列挙されている。

## 後続プラン (本プランの対象外)

- **Phase 3**: `cal-omc` 投影ラッパ (`gws` + Service Account) で `events/` → Google Calendar upsert + snapshots。利用者の SA 鍵・カレンダー共有が前提。
- **Phase 4**: city-tecoli への暦体登録。**【訂正 2026-06-29】** omc は **Blobs 動的エンティティ**として
  **管理 UI で登録**する（`global-ideas.yaml` には転記しない。このリポジトリから city-tecoli は編集しない）。

## 注記 (spec からの逸脱)

spec (2026-06-22) は Phase 2 を「ヘッドレス (Claude in Chrome) で Wix Blog API をページネーション取得」と想定していた。実調査の結果、`blog-posts-sitemap.xml` (359 記事) + 各記事の JSON-LD という**ブラウザ不要・決定論・テスト可能**な経路が判明したため、本 plan はそちらを採用する (より堅牢で、ブラウザ拡張の接続に依存しない)。設計意図 (全履歴から暦体を構築) は不変。
