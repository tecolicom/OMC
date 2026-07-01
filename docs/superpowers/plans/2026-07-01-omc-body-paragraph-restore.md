# 記事本文の段落(改行)忠実復元 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 記事アーカイブ `calendar/sources/blog/*.yaml` の `body` を、記事HTMLの本文コンテナから段落(改行)付きで忠実に復元する。

**Architecture:** `omc_parse.py` に本文抽出 `extract_post_body`(post-description コンテナの `<p>` を段落抽出、失敗時は現行 description にフォールバック)を追加。新モジュール `omc_refresh.py` + CLI `cal-omc-body-refresh` で、既存アーカイブを再取得し「内容が空白除去で一致する場合のみ改行を追加」して body だけ安全に更新する。events/カレンダー投影は触らない。

**Tech Stack:** Python 3.10, pytest, PyYAML, urllib

## Global Constraints

- 対象は `calendar/sources/blog/*.yaml` の `body` のみ。title/published/images/cover は保持する。
- `calendar/events/*.yaml` は再生成しない(events の body は website も Google Calendar 投影も未参照。触らないことで投影に影響を与えない)。
- website(site/) のコードは変更しない(詳細ページは既に `whitespace-pre-line`)。
- 内容保全ガード: 新 body と旧 body を「全空白除去 + NFKC 正規化」して比較し、一致する場合のみ改行を追加更新する。不一致は上書きせず content-changed として報告。
- `omc_parse.py` は純解析ロジックを保つ(ネットワークIOを入れない)。ネットワーク取得は CLI 側。
- テスト実行: リポジトリ直下で `make test`(= `cd calendar && python3 -m pytest tests/ -q`)。焦点テストは `cd calendar && python3 -m pytest tests/<file> -q`。
- フッター著作権行(`Proudly created with Wix` を含む、または `©`/`(c)` で始まる行)は本文から除外する。
- 作業ブランチ: website-phaseA。コミットは小刻みに。

---

### Task 1: `extract_post_body` 抽出関数 + テスト + `extract_post_meta` 配線

**Files:**
- Modify: `calendar/bin/omc_parse.py`
- Create: `calendar/tests/fixtures/post-body-paragraphs.html`
- Test: `calendar/tests/test_omc_parse.py`

**Interfaces:**
- Consumes: 既存 `_clean_body(text)`、`_html`(標準ライブラリ html)、`unicodedata`、`json`、`re`(omc_parse で import 済)
- Produces:
  - `extract_post_body(html: str) -> str` — post-description コンテナ内 `<p>` を段落抽出し `\n` 連結。無い/空なら JSON-LD description を `_clean_body` した値。
  - `extract_post_meta` の返す `body` が `extract_post_body(html)` 由来になる。

- [ ] **Step 1: テスト用 fixture を作る**

Create `calendar/tests/fixtures/post-body-paragraphs.html`:

```html
<html><head>
<script type="application/ld+json">{"@type":"BlogPosting","headline":"里山整備のご案内","datePublished":"2023-09-10T00:00:00.000Z","description":"見回りを行います。ご参加ください。■集合:8:30"}</script>
</head><body>
<nav><p>Home</p><p>ブログ</p></nav>
<div data-hook="post-description">
<p><span class="a">見回りを行います。</span></p>
<p><span class="a">ご参加ください。</span></p>
<p><span class="a">■集合:8:30</span></p>
</div>
<footer><p>© 2019 by Okumusashi MTB Club. Proudly created with Wix.com</p></footer>
</body></html>
```

- [ ] **Step 2: 失敗するテストを書く**

`calendar/tests/test_omc_parse.py` の末尾に追記:

```python
def test_extract_post_body_paragraphs():
    h = open(os.path.join(os.path.dirname(__file__), "fixtures", "post-body-paragraphs.html"),
             encoding="utf-8").read()
    body = omc_parse.extract_post_body(h)
    # post-description 内の <p> が段落として \n 連結される。nav とフッターは除外
    assert body == "見回りを行います。\nご参加ください。\n■集合:8:30"


def test_extract_post_body_falls_back_to_description():
    # post-description が無い記事は従来どおり JSON-LD description(1行)を返す
    h = ('<script type="application/ld+json">'
         '{"@type":"BlogPosting","headline":"x","datePublished":"2020-01-01T00:00:00Z",'
         '"description":"一行の説明文です。"}</script>')
    assert omc_parse.extract_post_body(h) == "一行の説明文です。"


def test_extract_post_body_empty_when_no_body():
    h = ('<script type="application/ld+json">'
         '{"@type":"BlogPosting","headline":"x","datePublished":"2020-01-01T00:00:00Z"}</script>')
    assert omc_parse.extract_post_body(h) == ""


def test_extract_post_meta_uses_post_body_paragraphs():
    h = open(os.path.join(os.path.dirname(__file__), "fixtures", "post-body-paragraphs.html"),
             encoding="utf-8").read()
    meta = omc_parse.extract_post_meta(h)
    assert "\n" in meta["body"]
    assert meta["body"].splitlines()[0] == "見回りを行います。"
```

- [ ] **Step 3: テストを実行して失敗を確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_parse.py -q`
Expected: 新テストが FAIL(`extract_post_body` 未定義 / `AttributeError`)。

- [ ] **Step 4: 実装する**

`calendar/bin/omc_parse.py`、`_clean_body`(37行あたり)の直後に追加:

```python
_P_BLOCK_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S)
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
    """記事HTMLの本文を段落(改行)付きで返す。

    post-description コンテナ内の <p> ブロックを段落として \n 連結する。
    見つからない/空の場合は従来どおり JSON-LD description を _clean_body した値。
    """
    idx = html.find('data-hook="post-description"')
    if idx != -1:
        lines = []
        for block in _P_BLOCK_RE.findall(html[idx:]):
            t = unicodedata.normalize("NFKC", _html.unescape(_TAG_RE.sub("", block))).strip()
            if t and not _is_footer_line(t):
                lines.append(t)
        body = "\n".join(lines)
        if body:
            return body
    return _clean_body(_description_from_jsonld(html))
```

さらに `extract_post_meta` 内の body 生成(現状 `body = _clean_body(item.get("description") or "")`)を次に置き換える:

```python
                body = extract_post_body(html)
```

- [ ] **Step 5: テストを実行して成功を確認**

Run: `cd calendar && python3 -m pytest tests/ -q`
Expected: 全 PASS。既存 `test_extract_post_meta_includes_body`(post-recent.html は post-description 無し→フォールバックで従来body)も維持。golden も維持(blog-fetch は RSS 経路)。

- [ ] **Step 6: コミット**

```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add calendar/bin/omc_parse.py calendar/tests/test_omc_parse.py calendar/tests/fixtures/post-body-paragraphs.html
git commit -m "feat(calendar): extract_post_body で記事本文を段落付き抽出(失敗時はdescriptionにフォールバック)"
```

---

### Task 2: body-only リフレッシュ (`omc_refresh.py` + CLI + Makefile) + テスト

**Files:**
- Create: `calendar/bin/omc_refresh.py`
- Create: `calendar/bin/cal-omc-body-refresh`
- Modify: `Makefile`
- Test: `calendar/tests/test_omc_refresh.py`

**Interfaces:**
- Consumes: `omc_parse.extract_post_body`、`omc_parse.dump_archive_yaml`(Task 1 / 既存)
- Produces:
  - `omc_refresh.reconcile_body(old_body: str, html: str) -> tuple[str, str]` — 戻り値 (書き込むbody, status)。status は `"updated"|"unchanged"|"content-changed"`。
  - `omc_refresh.refresh_dir(cache_dir: str, fetch_fn, sleep_fn=..., limit=None) -> dict` — summary(`updated`,`unchanged`,`content-changed`,`error` の件数と `files` 一覧)。`updated` のときのみファイルの body を書き換える。
  - CLI `cal-omc-body-refresh`(実ネットワークで `refresh_dir` を回す)。

- [ ] **Step 1: 失敗するテストを書く**

Create `calendar/tests/test_omc_refresh.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import omc_refresh  # noqa: E402
import yaml  # noqa: E402

PD = ('<div data-hook="post-description">'
      '<p><span>あ。</span></p><p><span>い。</span></p><p><span>う。</span></p></div>'
      '<footer><p>© 2019 by Okumusashi MTB Club. Proudly created with Wix.com</p></footer>')


def test_reconcile_body_updated_when_content_matches():
    # 旧body は同じ内容の1行、HTML は段落あり → 改行を足して更新
    new, status = omc_refresh.reconcile_body("あ。い。う。", PD)
    assert status == "updated"
    assert new == "あ。\nい。\nう。"


def test_reconcile_body_content_changed_is_not_overwritten():
    new, status = omc_refresh.reconcile_body("まったく別の本文", PD)
    assert status == "content-changed"
    assert new == "まったく別の本文"  # 旧を保持(上書きしない)


def test_reconcile_body_unchanged_when_already_equal():
    new, status = omc_refresh.reconcile_body("あ。\nい。\nう。", PD)
    assert status == "unchanged"


def test_refresh_dir_updates_only_body(tmp_path):
    p = tmp_path / "post-x.yaml"
    p.write_text(yaml.safe_dump(
        {"url": "https://x/post/x", "title": "T", "published": "2023-09-10",
         "body": "あ。い。う。", "images": ["https://static.wixstatic.com/media/z.jpg"]},
        allow_unicode=True, sort_keys=False), encoding="utf-8")
    summary = omc_refresh.refresh_dir(str(tmp_path), fetch_fn=lambda url: PD, sleep_fn=lambda: None)
    assert summary["updated"] == 1
    rec = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert rec["body"] == "あ。\nい。\nう。"      # 改行が入った
    assert rec["title"] == "T"                     # 他フィールドは保持
    assert rec["images"] == ["https://static.wixstatic.com/media/z.jpg"]
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_refresh.py -q`
Expected: FAIL(`omc_refresh` が無い / ModuleNotFoundError)。

- [ ] **Step 3: `omc_refresh.py` を実装する**

Create `calendar/bin/omc_refresh.py`:

```python
"""アーカイブ(sources/blog/*.yaml)の body だけを段落付きに安全更新するロジック。"""
from __future__ import annotations

import glob
import os
import re
import unicodedata

import yaml

import omc_parse


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


def reconcile_body(old_body: str, html: str) -> tuple[str, str]:
    new = omc_parse.extract_post_body(html)
    if _norm(new) != _norm(old_body):
        return old_body, "content-changed"
    if new == old_body:
        return old_body, "unchanged"
    return new, "updated"


def refresh_dir(cache_dir: str, fetch_fn, sleep_fn=lambda: None, limit=None) -> dict:
    summary = {"updated": 0, "unchanged": 0, "content-changed": 0, "error": 0, "files": []}
    paths = sorted(glob.glob(os.path.join(cache_dir, "*.yaml")))
    if limit:
        paths = paths[:limit]
    for path in paths:
        with open(path, encoding="utf-8") as f:
            rec = yaml.safe_load(f)
        url = (rec or {}).get("url")
        try:
            html = fetch_fn(url)
        except Exception as e:  # noqa: BLE001
            summary["error"] += 1
            summary["files"].append((path, "error", f"{type(e).__name__}"))
            continue
        new_body, status = reconcile_body(rec.get("body", ""), html)
        summary[status] += 1
        if status == "updated":
            rec["body"] = new_body
            with open(path, "w", encoding="utf-8") as f:
                f.write(omc_parse.dump_archive_yaml(rec))
        if status in ("content-changed", "error"):
            summary["files"].append((path, status, url))
        sleep_fn()
    return summary
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_refresh.py -q`
Expected: 4 tests PASS。

- [ ] **Step 5: CLI `cal-omc-body-refresh` を作る**

Create `calendar/bin/cal-omc-body-refresh`:

```python
#!/usr/bin/env python3
"""cal-omc-body-refresh — 既存アーカイブを再取得し body だけ段落付きに更新する。

events は再生成しない。内容が一致する場合のみ改行を追加(content-changed は上書きしない)。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import omc_refresh  # noqa: E402


def _fetch(url: str) -> str:
    sp = urllib.parse.urlsplit(url)
    u2 = urllib.parse.urlunsplit(
        (sp.scheme, sp.netloc, urllib.parse.quote(sp.path), sp.query, sp.fragment))
    req = urllib.request.Request(u2, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="sources/blog")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    summary = omc_refresh.refresh_dir(
        args.cache_dir, _fetch, sleep_fn=lambda: time.sleep(0.3), limit=args.limit)
    print("updated=%d unchanged=%d content-changed=%d error=%d" % (
        summary["updated"], summary["unchanged"], summary["content-changed"], summary["error"]))
    for path, status, info in summary["files"]:
        print("  %s\t%s\t%s" % (status, path, info))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

その後、実行権限を付与:

```bash
chmod +x calendar/bin/cal-omc-body-refresh
```

- [ ] **Step 6: Makefile にターゲットを追加する**

`Makefile` の `.PHONY` 行に `body-refresh` を加え(既存 `.PHONY: ... site-build` の行末に追記)、`fetch:` ターゲットの直後に次を追加:

```makefile
body-refresh: ## 既存アーカイブの本文を段落付きに更新(body のみ, events は不変)
	cd $(CAL) && $(PY) bin/cal-omc-body-refresh $(if $(LIMIT),--limit $(LIMIT),)
```

- [ ] **Step 7: 全テストを実行して成功を確認**

Run: `make test`
Expected: 全 PASS(既存 + 新規)。

- [ ] **Step 8: コミット**

```bash
cd /Users/utashiro/Git/tecolicom/OMC
chmod +x calendar/bin/cal-omc-body-refresh
git add calendar/bin/omc_refresh.py calendar/bin/cal-omc-body-refresh calendar/tests/test_omc_refresh.py Makefile
git commit -m "feat(calendar): cal-omc-body-refresh で本文を段落付きに安全更新(内容一致時のみ)"
```

---

### Task 3: 実データへ適用 + 検証 + プレビュー (controller 実行)

**Files:**
- Modify(データ): `calendar/sources/blog/*.yaml`(body のみ)

このタスクはネットワーク取得と canonical データ更新を伴う。段階的に実行し、サマリを確認する。

- [ ] **Step 1: 少数で試行(5件)**

Run: `cd /Users/utashiro/Git/tecolicom/OMC && make body-refresh LIMIT=5`
Expected: `updated=… unchanged=… content-changed=… error=…` が表示される。content-changed/error があれば url が列挙される。異常が無いか確認。

- [ ] **Step 2: 試行分の diff を目視**

Run: `cd /Users/utashiro/Git/tecolicom/OMC && git diff -- calendar/sources/blog | head -80`
Expected: 変更は `body:` が 1行(単一スカラー)から `body: |-` ブロック(複数行)へ変わるだけ。内容語は不変。おかしければ Step で停止し報告。

- [ ] **Step 3: 全件適用**

Run: `cd /Users/utashiro/Git/tecolicom/OMC && make body-refresh`
Expected: サマリ表示。updated 件数が大半、content-changed は Wix 側編集された記事のみ(あれば url を記録)。

- [ ] **Step 4: 不変条件を検証**

Run:
```bash
cd /Users/utashiro/Git/tecolicom/OMC && python3 - <<'PY'
import glob, yaml, subprocess, re, unicodedata
def norm(s): return re.sub(r"\s+","",unicodedata.normalize("NFKC",s or ""))
changed = subprocess.run(["git","diff","--name-only","--","calendar/sources/blog"],
                         capture_output=True,text=True).stdout.split()
bad=0
for path in changed:
    new=yaml.safe_load(open(path))
    old=yaml.safe_load(subprocess.run(["git","show",f"HEAD:{path}"],capture_output=True,text=True).stdout)
    # body 以外は不変
    for k in ("url","title","published","images","cover"):
        if new.get(k)!=old.get(k): print("FIELD CHANGED",path,k); bad+=1
    # body は内容(空白除去)不変・空にならない
    if norm(new.get("body",""))!=norm(old.get("body","")): print("BODY CONTENT CHANGED",path); bad+=1
    if old.get("body") and not new.get("body"): print("BODY EMPTIED",path); bad+=1
print("changed files:",len(changed)," violations:",bad)
PY
```
Expected: `violations: 0`。1件でもあれば停止して報告(該当ファイルを個別確認)。

- [ ] **Step 5: website プレビューで段落表示を確認**

dev サーバー稼働中(http://localhost:4321/OMC/)。里山整備等のお知らせを含む活動詳細を開き、本文が段落(改行)で表示されることを目視。
(dev サーバーが止まっていれば `make site-dev`。)

- [ ] **Step 6: コミット**

```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add calendar/sources/blog
git commit -m "data(calendar): 記事本文を段落付きに更新(body-refresh, 内容不変・改行のみ追加)"
```

content-changed で要確認の記事があれば、コミットメッセージ本文か ledger に url を記録し、ユーザーに提示する。

---

## Self-Review

- **Spec coverage:** 抽出ロジック=Task 1、body-only リフレッシュ+内容保全ガード+events非変更=Task 2、実データ適用+不変条件検証+プレビュー=Task 3、テスト=各 Task。website 変更不要は Global Constraints に明記。全要件にタスク対応。
- **Placeholder scan:** プレースホルダなし(全コード掲載)。
- **Type consistency:** `extract_post_body(html)->str`(Task 1)を Task 2 `reconcile_body`/`refresh_dir` が使用。`reconcile_body(old_body,html)->(str,str)`、`refresh_dir(cache_dir,fetch_fn,sleep_fn,limit)->dict` は Task 2 内で定義・使用。`dump_archive_yaml`(既存)で body 複数行が `|` ブロックスカラー出力(omc_parse の representer 済)。一致を確認。
