# 奥武蔵 MTB 暦体 Phase 2.5 (本文・写真取り込み + YAMLアーカイブ) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ブログ記事の本文（JSON-LD `description`）と写真リンク（wixstatic 元URL）を取り込み、生HTMLキャッシュを読みやすい YAML 記事アーカイブ（コミット対象）へ移行し、canonical イベントの各記事に本文・写真を付与する。

**Architecture:** Phase 1/2 の `omc_parse.py`（純ロジック）+ 薄い CLI 構成を踏襲。`extract_post_meta` に本文、新 `extract_post_images` に写真抽出を追加。アーカイブは 1記事=1 YAML（`sources/blog/<slug>.yaml`、本文はブロックスカラー）でコミットする。既存359 HTML から再fetchせず移行。`build_events`/`event_to_yaml_dict` が `source.posts[]` に body（report以外）/ images を載せる。

**Tech Stack:** Python 3.10+ / 標準ライブラリ (re, json, html, unicodedata, urllib, datetime) / PyYAML / pytest。LLM・ブラウザ不使用。

## Global Constraints

- 本文 = JSON-LD `BlogPosting.description` を `html.unescape` + NFKC 正規化、行 rstrip・前後空行除去。無ければ `""`。
- 写真 = `https://static.wixstatic.com/media/<id>.<ext>` の**元URL**（`/v1/fill/...` を除去）、media id で dedupe、最大レンダリング幅 **200 以上**のみ採用（UIアイコン除外）。cover = `og:image`（無ければ JSON-LD `image.url`）。画像は HTML 全体から抽出（JSON-LD ではない）。
- アーカイブ YAML: `sources/blog/<slug>.yaml`、`{url, title, published, body, images, cover}`。`body` はブロックスカラー(`|`)。`images`/`cover` は空なら省略。**コミットする**（`.gitignore` は `*.html` のみ無視、`*.yaml` 追跡）。
- ファイル名 slug = URL の `/post/` 以下を unquote → `/`→`_` → パス不可文字（`<>:"\\|?*` と制御文字）除去。URL から再現可能。
- canonical: `source.posts[]` に `body`（kind が report 以外のとき）と `images`（あれば、kind 不問）を追加。report は body を持たない。
- **Phase 1 golden 不変**: RSS 経路（`cal-omc-blog-fetch`、本文・画像を持たない）の出力は不変。各タスクで `tests/test_golden.py` の PASS を確認する。
- 日本語 UTF-8 保持。`omc_parse.py` は純ロジック（fetch しない）。CLI が I/O。
- 作業ルート: `/Users/utashiro/Git/tecolicom/OMC`。

---

## File Structure

- `calendar/bin/omc_parse.py` — 拡張: `extract_post_meta`(body), `extract_post_images`(新), `slugify_post_url`(新), YAML block-scalar representer 登録, `build_events`/`event_to_yaml_dict`(body/images)。
- `calendar/bin/cal-omc-archive-fetch` — キャッシュを YAML アーカイブに変更、body/images を item に渡す。
- `calendar/bin/migrate-html-cache` — 新規・一回限り: 既存 `sources/blog/*.html` → `*.yaml` アーカイブ。
- `calendar/tests/test_omc_parse.py` — Task 1〜4 のテスト追記。
- `calendar/tests/test_archive_cli.py` — Task 5 のテスト更新。
- `calendar/tests/fixtures/post-images.html` — 画像抽出用 fixture（新規）。
- `.gitignore` — `sources/blog/*.html` のみ無視に変更。

---

### Task 1: `extract_post_meta` に本文(body)を追加

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Produces: `extract_post_meta(html) -> {"title", "pub_date", "body"} | None`。`body` = JSON-LD `description` を `html.unescape` + NFKC、各行 rstrip、前後空行除去。`description` 不在で `body=""`。title/pub_date は既存仕様。

- [ ] **Step 1: 失敗テストを追記** (`test_omc_parse.py`)

```python
def test_extract_post_meta_includes_body():
    h = open(os.path.join(os.path.dirname(__file__), "fixtures", "post-recent.html"),
             encoding="utf-8").read()
    meta = omc_parse.extract_post_meta(h)
    assert meta["title"] == "5/31日高市ごみゼロの日活動報告"
    assert meta["pub_date"] == _dt.date(2026, 6, 3)
    assert meta["body"].startswith("5/31は日高市ごみゼロの日。")
    assert "参加者は6名" in meta["body"]


def test_extract_post_meta_body_empty_when_no_description():
    h = ('<script type="application/ld+json">'
         '{"@type":"BlogPosting","headline":"x","datePublished":"2020-01-01T00:00:00Z"}</script>')
    assert omc_parse.extract_post_meta(h)["body"] == ""
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k extract_post_meta -v`
Expected: `test_extract_post_meta_includes_body` が KeyError/FAIL（body 未実装）。

- [ ] **Step 3: 実装** (`omc_parse.py` の `extract_post_meta` を差し替え。先頭 import に `import html as _html` が無ければ追加)

```python
def _clean_body(text: str) -> str:
    t = unicodedata.normalize("NFKC", _html.unescape(text))
    lines = [ln.rstrip() for ln in t.split("\n")]
    return "\n".join(lines).strip("\n")


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
                body = _clean_body(item.get("description") or "")
                return {"title": headline, "pub_date": pub, "body": body}
    return None
```

(注: 既存実装にあった headline 正規化・published パースは維持。`description` を `_clean_body` で本文化。)

- [ ] **Step 4: 成功確認 + Phase1 回帰**

Run: `cd calendar && python3 -m pytest tests/ -v`
Expected: 全 PASS（`test_golden.py` 含む。RSS 経路は extract_post_meta 非経由なので不変）。

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: extract_post_meta に本文(body)を追加 (Phase 2.5)"
```

---

### Task 2: 写真抽出 `extract_post_images`

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Create: `calendar/tests/fixtures/post-images.html`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Produces: `extract_post_images(html) -> {"images": list[str], "cover": str | None}`。`images` = wixstatic media の**元URL**（dedupe・最大幅200以上・出現順）。`cover` = og:image（無ければ JSON-LD `image.url`）。

- [ ] **Step 1: 画像 fixture を作成** (`tests/fixtures/post-images.html`)

```html
<html><head>
<meta property="og:image" content="https://static.wixstatic.com/media/c3395c_cover.jpg/v1/fill/w_640/cover.jpg"/>
<script type="application/ld+json">{"@type":"BlogPosting","headline":"写真記事","datePublished":"2024-01-01T00:00:00Z","image":{"@type":"ImageObject","url":"https://static.wixstatic.com/media/c3395c_cover.jpg/v1/fill/w_640/cover.jpg"}}</script>
</head><body>
<img src="https://static.wixstatic.com/media/c3395c_photoA.jpg/v1/fill/w_1890,h_1000/photoA.jpg"/>
<img src="https://static.wixstatic.com/media/c3395c_photoA.jpg/v1/fill/w_320,h_200/photoA.jpg"/>
<img src="https://static.wixstatic.com/media/c3395c_photoB.png/v1/fill/w_976/photoB.png"/>
<img src="https://static.wixstatic.com/media/icon_small.png/v1/fill/w_78/icon.png"/>
</body></html>
```

- [ ] **Step 2: 失敗テストを追記**

```python
def test_extract_post_images():
    h = open(os.path.join(os.path.dirname(__file__), "fixtures", "post-images.html"),
             encoding="utf-8").read()
    res = omc_parse.extract_post_images(h)
    assert res["images"] == [
        "https://static.wixstatic.com/media/c3395c_photoA.jpg",
        "https://static.wixstatic.com/media/c3395c_photoB.png",
    ]
    assert res["cover"] == "https://static.wixstatic.com/media/c3395c_cover.jpg/v1/fill/w_640/cover.jpg"


def test_extract_post_images_empty():
    res = omc_parse.extract_post_images("<html><body>no images</body></html>")
    assert res == {"images": [], "cover": None}
```

(注: `c3395c_cover.jpg` は og:image 由来で `cover` に入り、`images` には含めない。`icon_small.png` は w_78<200 で除外。`photoA` は w_1890 で採用し dedupe で1本、`photoB` は w_976 で採用。)

- [ ] **Step 3: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k extract_post_images -v`
Expected: FAIL（未実装）。

- [ ] **Step 4: 実装** (`omc_parse.py` に追記)

```python
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
```

- [ ] **Step 5: 成功確認 + commit**

Run: `cd calendar && python3 -m pytest tests/ -v` → 全 PASS。
```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py calendar/tests/fixtures/post-images.html
git commit -m "feat: 写真抽出 extract_post_images (Phase 2.5)"
```

---

### Task 3: slug 生成 + YAML アーカイブ read/write (ブロックスカラー)

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Produces:
  - `slugify_post_url(url) -> str` — `/post/` 以下を unquote、`/`→`_`、パス不可文字除去。拡張子は付けない。
  - `dump_archive_yaml(record: dict) -> str` — record を YAML 文字列に（`body` は複数行ならブロックスカラー）。
  - モジュール import 時に str 用 block-scalar representer を `yaml.SafeDumper` に登録（複数行 str を `|` で出力）。

- [ ] **Step 1: 失敗テストを追記**

```python
import yaml as _yaml  # ファイル先頭にあれば不要

def test_slugify_post_url():
    assert omc_parse.slugify_post_url(
        "https://okumusashimtb.wixsite.com/omcweb/post/2019/07/23/8月4日名栗の整備") \
        == "2019_07_23_8月4日名栗の整備"
    # 全角括弧やスラッシュ混じり
    assert "/" not in omc_parse.slugify_post_url(
        "https://okumusashimtb.wixsite.com/omcweb/post/5-31日高市/ごみゼロ")


def test_dump_archive_yaml_block_body():
    rec = {"url": "https://x/post/a", "title": "t", "published": "2024-01-01",
           "body": "1行目\n2行目\n", "images": ["https://static.wixstatic.com/media/x.jpg"]}
    s = omc_parse.dump_archive_yaml(rec)
    assert "body: |" in s                       # ブロックスカラー
    assert "  1行目" in s and "  2行目" in s
    back = _yaml.safe_load(s)
    assert back["title"] == "t"
    assert back["body"].splitlines()[:2] == ["1行目", "2行目"]
    assert back["images"] == ["https://static.wixstatic.com/media/x.jpg"]
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k "slugify or dump_archive" -v`
Expected: FAIL。

- [ ] **Step 3: 実装** (`omc_parse.py`。先頭 import に `import urllib.parse` を追加。`import yaml` も追加し、representer 登録)

```python
import urllib.parse
import yaml

# 複数行 str は YAML ブロックスカラー(|)で出力（アーカイブ可読性）。単一行は既定どおり。
def _block_str_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

yaml.add_representer(str, _block_str_representer, Dumper=yaml.SafeDumper)

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
```

- [ ] **Step 4: 成功確認 + Phase1 回帰**

Run: `cd calendar && python3 -m pytest tests/ -v`
Expected: 全 PASS。**`test_golden.py` が PASS**（golden イベントは複数行文字列を含まないので representer の影響なし＝バイト不変）。

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: slugify_post_url + YAMLアーカイブ書き出し(ブロックスカラー) (Phase 2.5)"
```

---

### Task 4: canonical に body/images を載せる

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: `build_events` の item が任意で `body` / `images` を持つ（`{title, link, guid, pub_date, body?, images?}`）。
- Produces: `source.posts[]` の各 post に、kind が report 以外なら `body`（あれば）、kind 不問で `images`（あれば）を含める。`event_to_yaml_dict` がそれを出力。body/images が無い post は従来どおり `{kind,url,title,published}` のみ。

- [ ] **Step 1: 失敗テストを追記**

```python
def test_build_events_carries_body_and_images():
    items = [
        {"title": "5/17里山整備活動のお知らせ", "link": "https://x/a", "guid": "a",
         "pub_date": _dt.date(2025, 5, 1), "body": "9時集合です", "images": []},
        {"title": "5/17里山整備活動の報告", "link": "https://x/r", "guid": "r",
         "pub_date": _dt.date(2025, 5, 20), "body": "実施しました", "images": ["https://static.wixstatic.com/media/p.jpg"]},
    ]
    ev = omc_parse.build_events(items)[0]
    d = omc_parse.event_to_yaml_dict(ev, _dt.date(2026, 6, 22), crawler="cal-omc-archive-fetch")
    posts = {p["kind"]: p for p in d["source"]["posts"]}
    assert posts["announce"]["body"] == "9時集合です"   # お知らせは本文あり
    assert "body" not in posts["report"]                 # 報告は本文なし
    assert posts["report"]["images"] == ["https://static.wixstatic.com/media/p.jpg"]
    assert "images" not in posts["announce"]             # 空 images は省略
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -k carries_body_and_images -v`
Expected: FAIL。

- [ ] **Step 3: 実装**

(a) `build_events` の各 item から rec を作る箇所で、body/images を rec の `src` に持たせる。`src` 構築を次に変更:

```python
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
```

(b) `event_to_yaml_dict` の posts 構築を、kind に応じて body/images を条件付きで含める形に変更:

```python
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
```

(注: RSS 経路の item は body/images を持たないので `src["body"]=""`、`src["images"]=[]` となり、`event_to_yaml_dict` は body/images キーを出力しない＝従来出力と**バイト不変**。golden 維持。)

- [ ] **Step 4: 成功確認 + Phase1 回帰（最重要）**

Run: `cd calendar && python3 -m pytest tests/ -v`
Expected: 全 PASS。**`test_golden.py` が PASS**（RSS 経路は body/images 空 → キー非出力 → 不変）。

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py
git commit -m "feat: canonical の posts に body/images を付与 (report は body なし) (Phase 2.5)"
```

---

### Task 5: `cal-omc-archive-fetch` を YAML アーカイブキャッシュへ

**Files:**
- Modify: `calendar/bin/cal-omc-archive-fetch`
- Test: `calendar/tests/test_archive_cli.py`

**Interfaces:**
- キャッシュを `<cache-dir>/<slug>.yaml`（`{url,title,published,body,images,cover}`）に変更。キャッシュ命中時は YAML を読む。ミス時のみ fetch → `extract_post_meta` + `extract_post_images` → アーカイブ YAML 書き出し。build_events へ渡す item に `body`/`images` を含める。

- [ ] **Step 1: テストを更新** (`test_archive_cli.py`)

既存テストはキャッシュに HTML を置いていた。これを「アーカイブ YAML を置く」方式に変更し、本文/画像が canonical に載ることを検証する。テスト全体を次に置き換え:

```python
import os, subprocess, sys, glob, yaml

HERE = os.path.dirname(__file__)
BIN = os.path.join(HERE, "..", "bin", "cal-omc-archive-fetch")
SITEMAP = os.path.join(HERE, "fixtures", "sitemap-sample.xml")
POST_URL = "https://okumusashimtb.wixsite.com/omcweb/post/sample-a"


def _slug(url):
    sys.path.insert(0, os.path.join(HERE, "..", "bin"))
    import omc_parse
    return omc_parse.slugify_post_url(url)


def test_archive_cli_uses_yaml_cache_and_carries_body(tmp_path):
    cache = tmp_path / "cache"; cache.mkdir()
    rec = {
        "url": POST_URL,
        "title": "5/31日高市ごみゼロの日活動報告",
        "published": "2026-06-03",
        "body": "早朝より作業しました。",
        "images": ["https://static.wixstatic.com/media/c3395c_p.jpg"],
    }
    (cache / f"{_slug(POST_URL)}.yaml").write_text(
        yaml.safe_dump(rec, allow_unicode=True, sort_keys=False), encoding="utf-8")
    out = tmp_path / "events"
    r = subprocess.run(
        [sys.executable, BIN, "--sitemap-file", SITEMAP, "--cache-dir", str(cache),
         "--out-dir", str(out), "--review-file", str(tmp_path / "rev.txt"),
         "--fetched", "2026-06-22"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    files = glob.glob(str(out / "2026" / "05-31_*.yaml"))
    assert len(files) == 1
    d = yaml.safe_load(open(files[0], encoding="utf-8"))
    post = d["source"]["posts"][0]
    assert post["kind"] == "report"
    assert "body" not in post                       # 報告は本文なし
    assert post["images"] == ["https://static.wixstatic.com/media/c3395c_p.jpg"]
    assert d["source"]["crawler"] == "cal-omc-archive-fetch"
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_archive_cli.py -v`
Expected: FAIL（CLI がまだ HTML キャッシュ方式）。

- [ ] **Step 3: 実装** (`cal-omc-archive-fetch` の `_load_cached` とループ部を変更)

`import hashlib` を `import yaml` 利用に置換しないが、キャッシュは slug+yaml にする。`_load_cached` を `_load_record` に置き換え:

```python
def _fetch(url: str) -> str:
    sp = urllib.parse.urlsplit(url)
    u2 = urllib.parse.urlunsplit(
        (sp.scheme, sp.netloc, urllib.parse.quote(sp.path), sp.query, sp.fragment))
    req = urllib.request.Request(u2, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _load_record(url: str, cache_dir: str) -> dict | None:
    path = os.path.join(cache_dir, omc_parse.slugify_post_url(url) + ".yaml")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    html = _fetch(url)
    meta = omc_parse.extract_post_meta(html)
    if meta is None:
        return None
    imgs = omc_parse.extract_post_images(html)
    record = {
        "url": url,
        "title": meta["title"],
        "published": meta["pub_date"].isoformat(),
        "body": meta["body"],
    }
    if imgs["images"]:
        record["images"] = imgs["images"]
    if imgs["cover"]:
        record["cover"] = imgs["cover"]
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(omc_parse.dump_archive_yaml(record))
    time.sleep(0.3)
    return record
```

メインループを次に変更（`hashlib` import は不要になるので削除可）:

```python
    items = []
    review = []
    for url in urls:
        try:
            record = _load_record(url, args.cache_dir)
        except Exception as e:
            review.append((url, "", f"fetch-error:{type(e).__name__}"))
            continue
        if record is None:
            review.append((url, "", "no-jsonld"))
            continue
        try:
            pub = datetime.date.fromisoformat(str(record["published"])[:10])
        except (ValueError, KeyError, TypeError):
            review.append((url, record.get("title", ""), "bad-date"))
            continue
        title = record.get("title", "")
        if omc_parse.extract_event_date(title, pub) is None:
            review.append((url, title, "no-date"))
            continue
        items.append({"title": title, "link": url, "guid": url, "pub_date": pub,
                      "body": record.get("body", ""), "images": record.get("images", [])})

    events = omc_parse.build_events(items)
    for ev in events:
        path = os.path.join(args.out_dir, omc_parse.event_filename(ev))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(omc_parse.event_to_yaml_dict(ev, fetched, crawler="cal-omc-archive-fetch"), f,
                           allow_unicode=True, sort_keys=False)
```

- [ ] **Step 4: 成功確認 + 全回帰**

Run:
```bash
chmod +x calendar/bin/cal-omc-archive-fetch
cd calendar && python3 -m pytest tests/ -v
```
Expected: 全 PASS（golden 含む）。

- [ ] **Step 5: Commit**

```bash
git add calendar/bin/cal-omc-archive-fetch calendar/tests/test_archive_cli.py
git commit -m "feat: cal-omc-archive-fetch を YAMLアーカイブキャッシュ + body/images へ (Phase 2.5)"
```

---

### Task 6: .gitignore + 移行スクリプト + アーカイブ生成 + canonical 再生成

**Files:**
- Modify: `.gitignore`
- Create: `calendar/bin/migrate-html-cache`
- Create: `calendar/sources/blog/*.yaml`（アーカイブ、コミット）
- Modify: `calendar/events/*/*.yaml`（本文・画像付きで再生成）

**Interfaces:**
- Consumes: 既存 `sources/blog/*.html`（359件）、Task 1〜5 の関数/CLI。
- Produces: コミット済み YAML アーカイブ + 本文/画像付き canonical。

- [ ] **Step 1: `.gitignore` を変更**

`/calendar/sources/` の行を削除し、次を追加（html のみ無視、yaml は追跡）:

```
/calendar/sources/blog/*.html
```

- [ ] **Step 2: 移行スクリプトを作成** (`calendar/bin/migrate-html-cache`)

```python
#!/usr/bin/env python3
"""migrate-html-cache — 既存 sources/blog/*.html から YAML アーカイブを生成（一回限り）。

再 fetch しない。各 HTML から JSON-LD 本文 + 画像を抽出し <slug>.yaml を書く。
URL は HTML 内の canonical/og:url から復元する。
"""
from __future__ import annotations
import glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import omc_parse


def _post_url(html: str) -> str | None:
    m = re.search(r'<meta property="og:url" content="([^"]+)"', html) \
        or re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def main() -> int:
    cache_dir = sys.argv[1] if len(sys.argv) > 1 else "sources/blog"
    htmls = glob.glob(os.path.join(cache_dir, "*.html"))
    written = skipped = 0
    for hp in htmls:
        html = open(hp, encoding="utf-8", errors="replace").read()
        url = _post_url(html)
        meta = omc_parse.extract_post_meta(html)
        if not url or meta is None:
            skipped += 1
            continue
        imgs = omc_parse.extract_post_images(html)
        rec = {"url": url, "title": meta["title"],
               "published": meta["pub_date"].isoformat(), "body": meta["body"]}
        if imgs["images"]:
            rec["images"] = imgs["images"]
        if imgs["cover"]:
            rec["cover"] = imgs["cover"]
        out = os.path.join(cache_dir, omc_parse.slugify_post_url(url) + ".yaml")
        with open(out, "w", encoding="utf-8") as f:
            f.write(omc_parse.dump_archive_yaml(rec))
        written += 1
    print(f"html={len(htmls)} written={written} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 移行を実行しアーカイブ生成**

Run:
```bash
chmod +x calendar/bin/migrate-html-cache
cd calendar && python3 bin/migrate-html-cache sources/blog
ls sources/blog/*.yaml | wc -l    # ~359 期待
```
出力 `html=359 written=~359 skipped=~0` を確認。数件抽出できないものがあれば、その URL を控える（致命的でなければ続行）。

- [ ] **Step 4: アーカイブを目視確認**

Run: `head -40 calendar/sources/blog/*8月4日*.yaml 2>/dev/null | head -40`
本文がブロックスカラーで読め、images が元URLで入っていることを確認。

- [ ] **Step 5: canonical を本文・画像付きで再生成**

Run:
```bash
cd calendar && rm -rf events/20*/ && python3 bin/cal-omc-archive-fetch --fetched 2026-06-22
echo "events: $(ls events/*/*.yaml | wc -l)"   # 145 期待
python3 -m pytest tests/ -q                     # 全 PASS
```
1件サンプルを確認:
```bash
cat calendar/events/2025/*05-18*.yaml   # お知らせ body、報告 images が載るか
```

- [ ] **Step 6: 巨大 HTML を削除**

Run: `rm -f calendar/sources/blog/*.html`
（`*.html` は .gitignore 済みなので元々コミット対象外。ディスク節約のため削除。）

- [ ] **Step 7: Commit**（アーカイブ YAML・.gitignore・移行スクリプト・再生成 events）

```bash
git add .gitignore calendar/bin/migrate-html-cache calendar/sources/blog/ calendar/events
git commit -m "data: YAMLアーカイブ(本文・写真リンク)をコミット + canonical を本文/画像付きで再生成"
```

---

## 完了条件

- `cd calendar && python3 -m pytest tests/ -q` が全 PASS（Phase 1 golden 含め不変）。
- `calendar/sources/blog/*.yaml`（~359件）が版管理に入り、本文・写真リンク・記事リンクを保持。
- `calendar/events/*/*.yaml`（145件）が本文（お知らせ）・写真（主に報告）付きで再生成。

## 後続（本プラン対象外）
- **Phase 3**: `cal-omc` で canonical → Google Calendar 投影（description にお知らせ本文+全リンク、終日/既存時刻保存、冪等 upsert、矛盾は保留、dry-run→apply）。spec の Phase 3 節を別 plan で詳細化。
