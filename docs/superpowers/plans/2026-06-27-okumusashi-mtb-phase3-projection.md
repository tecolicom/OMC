# 奥武蔵 MTB 暦体 Phase 3 (Google Calendar 投影) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** canonical イベント (`calendar/events/*.yaml`, 145件) を Google Calendar `okumusashi.mtb@gmail.com` へ冪等に投影する `cal-omc`。description に お知らせ本文＋全リンク、新規は終日・既存は時刻保存、矛盾は保留。既定 dry-run、`--apply` で書き込み。

**Architecture:** 飯能 `cal-myhanno`（Python + `gws` + Service Account、iCalUID で upsert）に準拠。純ロジック（description 組み立て・イベント本体・突合判定）を `omc_project.py` に置き pytest で固め、`gws` 呼び出しは薄い注入可能な層に隔離する。`cal-omc` CLI は canonical を読み、日付ごとに既存イベントを引いて決定（create/update/overwrite/skip）を計画し、dry-run で一覧、`--apply` で実行、`snapshots/` にバックアップ。

**Tech Stack:** Python 3.10+ / 標準ライブラリ (subprocess, json, datetime) / PyYAML / pytest / `gws`（googleworkspace/cli）/ Service Account (`~/.config/omc/sa.json`)。

## Global Constraints

- 対象カレンダー: `okumusashi.mtb@gmail.com`。認証: `GOOGLE_APPLICATION_CREDENTIALS` 未設定なら `~/.config/omc/sa.json`（hanno の myhanno SA 流用、writer 確認済）。
- 我々が管理するイベントの iCalUID = `omc-<uid>@okumusashi-mtb`（`<uid>` = canonical の date 由来 12 桁）。
- description = お知らせ本文（report 以外の post の body、複数は日付順に連結、合計 **1000 文字**超は切り「…（続きはリンク先で）」付与）＋ 空行 ＋ リンク集（全 post を kind ラベル付き: 📣お知らせ / ⚠️中止（announce かつタイトルに「中止」）/ 📝報告 / 🔗その他）。report は**リンクのみ**（本文不掲載）。
- 新規作成は**終日**（`start.date` / `end.date`=翌日）。既存イベントを上書きする際、既存が時刻付き（`start.dateTime`）なら **start/end を保持**し summary/description のみ更新。
- 冪等 upsert: iCalUID で既存検索 → 無ければ `import`、有れば**差分があるときのみ** `update`。
- 突合（開催日キー）: その日に (a) 我々 iCalUID イベント → 更新/skip、(b) 手動イベントで**矛盾しない** → 上書き（時刻保持）、(c) **矛盾** → `projection-review-needed.txt` に出して skip、(d) 無し → 新規。
- 「矛盾」初期判定: 同日に手動イベントが複数 / 既存 summary が canonical の category と明確に別系統なら矛盾。曖昧なら保留側（安全）。
- **既定は dry-run**（書き込み API を一切呼ばない）。`--apply` で実書き込み。`--year YYYY` / `--limit N` で範囲限定。
- `gws` の stdout 先頭に出る非 JSON 行（`Using keyring backend:` 等）は最初の `{`/`[` 以降を JSON とみなして読み飛ばす。
- 日本語 UTF-8。`omc_project.py` は純ロジック（gws/network を直接呼ばない、注入された呼び出し器を使う）。
- 作業ルート: `/Users/utashiro/Git/tecolicom/OMC`。テストは `calendar/` から `python3 -m pytest tests/`。

---

## File Structure

- `calendar/bin/omc_project.py` — 純ロジック: `build_description`, `build_event_body`, `ical_uid_for`, `decide_action`, `needs_update`, `parse_gws_json`。テスト対象。
- `calendar/bin/cal-omc` — CLI: canonical 読込 → 既存照会(gws) → decide → dry-run 出力 / `--apply` 実行(import/update) → snapshots。gws 呼び出しを内包し、計画ロジックは omc_project に委譲。
- `calendar/tests/test_omc_project.py` — 純ロジックのテスト。
- `calendar/tests/test_cal_omc.py` — CLI の dry-run 計画を fake 既存イベントで検証（network なし）。
- `calendar/snapshots/events/<safe-iCalUID>.json` — apply 後の Calendar 状態ミラー。
- `calendar/projection-review-needed.txt` — 矛盾で保留した日の一覧。

---

### Task 1: description 組み立て `build_description`

**Files:**
- Create: `calendar/bin/omc_project.py`
- Test: `calendar/tests/test_omc_project.py`

**Interfaces:**
- Produces: `build_description(posts: list[dict], limit: int = 1000) -> str`。`posts` は canonical の `source.posts[]`（各 `{kind,url,title,published,body?,images?}`）。本文は report 以外の `body` を日付（published）順に連結、limit 超で切詰め。続いてリンク集（全 post、kind ラベル付き）。

- [ ] **Step 1: 失敗テストを書く** (`test_omc_project.py`)

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import omc_project


def test_build_description_announce_body_and_links():
    posts = [
        {"kind": "report", "url": "https://x/r", "title": "5/17里山整備の報告", "published": "2025-05-20"},
        {"kind": "announce", "url": "https://x/a", "title": "5/17里山整備のお知らせ",
         "published": "2025-05-08", "body": "9時集合です。"},
    ]
    d = omc_project.build_description(posts)
    assert d.startswith("9時集合です。")          # お知らせ本文（report 本文は出さない）
    assert "📣 お知らせ: https://x/a" in d
    assert "📝 報告: https://x/r" in d


def test_build_description_marks_cancel_and_truncates():
    posts = [
        {"kind": "announce", "url": "https://x/c", "title": "5/17活動中止のお知らせ",
         "published": "2025-05-16", "body": "あ" * 1500},
    ]
    d = omc_project.build_description(posts, limit=1000)
    assert "…（続きはリンク先で）" in d
    assert "⚠️ 中止: https://x/c" in d


def test_build_description_report_only_no_body():
    posts = [{"kind": "report", "url": "https://x/r", "title": "里山整備の報告",
              "published": "2025-05-20", "body": "本文は出さない"}]
    d = omc_project.build_description(posts)
    assert "本文は出さない" not in d
    assert d.strip().startswith("📝 報告:")
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_project.py -k build_description -v`
Expected: FAIL（モジュール無し）。

- [ ] **Step 3: 実装** (`omc_project.py`)

```python
"""Google Calendar 投影の純ロジック (gws/network を直接呼ばない)。"""
from __future__ import annotations

import json


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
```

- [ ] **Step 4: 成功確認 + commit**

Run: `cd calendar && python3 -m pytest tests/test_omc_project.py -k build_description -v` → PASS
```bash
git add calendar/bin/omc_project.py calendar/tests/test_omc_project.py
git commit -m "feat: 投影 description 組み立て build_description (Phase 3)"
```

---

### Task 2: イベント本体 `build_event_body` + `ical_uid_for`

**Files:**
- Modify: `calendar/bin/omc_project.py`
- Test: `calendar/tests/test_omc_project.py`

**Interfaces:**
- Produces:
  - `ical_uid_for(event: dict) -> str` — `f"omc-{event['uid']}@okumusashi-mtb"`（canonical event は `uid` を持つ。無ければ date から導出: 失敗時は date 文字列）。
  - `build_event_body(event: dict) -> dict` — 終日イベント本体 `{summary, start:{date}, end:{date 翌日}, description, iCalUID}`。`event` は canonical（`{summary,date,uid,source:{posts}}`）。

- [ ] **Step 1: 失敗テストを書く**

```python
import datetime as _dt

def test_build_event_body_allday():
    event = {
        "summary": "里山整備活動", "date": "2025-05-17", "uid": "abc123def456",
        "source": {"posts": [
            {"kind": "report", "url": "https://x/r", "title": "報告", "published": "2025-05-20"},
            {"kind": "announce", "url": "https://x/a", "title": "お知らせ", "published": "2025-05-08", "body": "9時集合"},
        ]},
    }
    b = omc_project.build_event_body(event)
    assert b["summary"] == "里山整備活動"
    assert b["start"] == {"date": "2025-05-17"}
    assert b["end"] == {"date": "2025-05-18"}     # 終日 end は翌日(排他)
    assert b["iCalUID"] == "omc-abc123def456@okumusashi-mtb"
    assert "9時集合" in b["description"]
    assert "📣 お知らせ: https://x/a" in b["description"]
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_project.py -k build_event_body -v` → FAIL

- [ ] **Step 3: 実装** (`omc_project.py` に追記。先頭に `import datetime`)

```python
import datetime


def ical_uid_for(event: dict) -> str:
    uid = event.get("uid") or event.get("date", "")
    return f"omc-{uid}@okumusashi-mtb"


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
```

- [ ] **Step 4: 成功確認 + commit**

Run: `cd calendar && python3 -m pytest tests/test_omc_project.py -k build_event_body -v` → PASS
```bash
git add calendar/bin/omc_project.py calendar/tests/test_omc_project.py
git commit -m "feat: 終日イベント本体 build_event_body + ical_uid_for (Phase 3)"
```

---

### Task 3: 突合判定 `decide_action` + `needs_update`

**Files:**
- Modify: `calendar/bin/omc_project.py`
- Test: `calendar/tests/test_omc_project.py`

**Interfaces:**
- Produces:
  - `decide_action(event, existing: list[dict]) -> dict` — その日付の既存イベント list を見て決定を返す。`existing` は gws の event オブジェクト list（`{iCalUID,id,summary,start,...}`）。返り値 `{"action": "...", "target": <existing event or None>, "reason": str}`。action ∈ `create` / `update_ours` / `overwrite_manual` / `skip_review`。
    - 我々 iCalUID（`ical_uid_for(event)`）の既存があれば → `update_ours`（target=それ）。
    - 無く、手動イベントが**ちょうど1件**で矛盾しなければ → `overwrite_manual`（target=それ）。
    - 手動が複数、または summary が canonical category と別系統（`_contradicts`）→ `skip_review`。
    - 既存ゼロ → `create`。
  - `needs_update(target: dict, body: dict) -> bool` — summary か description が違えば True（終日/時刻は overwrite 時に保持するので比較しない）。

- [ ] **Step 1: 失敗テストを書く**

```python
def _ev(summary, uid=None):
    e = {"summary": summary, "id": "eid_" + summary, "start": {"date": "2025-05-17"}}
    if uid: e["iCalUID"] = uid
    return e

EVENT = {"summary": "里山整備活動", "date": "2025-05-17", "uid": "u1", "category": "里山整備",
         "source": {"posts": [{"kind": "announce", "url": "https://x/a", "title": "お知らせ", "published": "2025-05-08", "body": "b"}]}}


def test_decide_create_when_no_existing():
    assert omc_project.decide_action(EVENT, [])["action"] == "create"


def test_decide_update_ours():
    ours = _ev("里山整備活動", uid="omc-u1@okumusashi-mtb")
    r = omc_project.decide_action(EVENT, [ours])
    assert r["action"] == "update_ours" and r["target"] is ours


def test_decide_overwrite_single_manual_consistent():
    manual = _ev("里山整備（自治会）")          # 同系統(里山) → 矛盾しない
    r = omc_project.decide_action(EVENT, [manual])
    assert r["action"] == "overwrite_manual" and r["target"] is manual


def test_decide_skip_when_multiple_manual():
    r = omc_project.decide_action(EVENT, [_ev("A"), _ev("B")])
    assert r["action"] == "skip_review"


def test_decide_skip_when_contradicts():
    r = omc_project.decide_action(EVENT, [_ev("第10回総会")])   # category 別系統
    assert r["action"] == "skip_review"


def test_needs_update():
    body = {"summary": "里山整備活動", "description": "X"}
    assert omc_project.needs_update({"summary": "里山整備活動", "description": "X"}, body) is False
    assert omc_project.needs_update({"summary": "別", "description": "X"}, body) is True
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_omc_project.py -k "decide or needs_update" -v` → FAIL

- [ ] **Step 3: 実装** (`omc_project.py` に追記)

```python
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


def needs_update(target: dict, body: dict) -> bool:
    return (target.get("summary") or "") != body.get("summary") \
        or (target.get("description") or "") != body.get("description")
```

- [ ] **Step 4: 成功確認 + commit**

Run: `cd calendar && python3 -m pytest tests/test_omc_project.py -v` → 全 PASS
```bash
git add calendar/bin/omc_project.py calendar/tests/test_omc_project.py
git commit -m "feat: 突合判定 decide_action + needs_update (Phase 3)"
```

---

### Task 4: CLI `cal-omc`（dry-run 計画 / --apply / snapshots）

**Files:**
- Create: `calendar/bin/cal-omc`
- Test: `calendar/tests/test_cal_omc.py`

**Interfaces:**
- Consumes: `omc_project.*`、canonical `events/*.yaml`、`gws`。
- Produces: 実行可能 CLI。`--events-dir`(既定 `events`)、`--year`、`--limit`、`--apply`(既定 dry-run)、`--review-file`(既定 `projection-review-needed.txt`)、`--snapshot-dir`(既定 `snapshots`)、`--cal-id`(既定 `okumusashi.mtb@gmail.com`)。
- 計画ロジックはテスト可能に: `plan_events(events, fetch_existing) -> list[dict]` を CLI 内に持ち、`fetch_existing(date)` 注入で network なしにテスト。

- [ ] **Step 1: 失敗テストを書く** (`test_cal_omc.py`、dry-run plan を fake で検証)

```python
import os, sys, importlib.util

HERE = os.path.dirname(__file__)
BIN = os.path.join(HERE, "..", "bin", "cal-omc")


def _load_cli():
    spec = importlib.util.spec_from_file_location("cal_omc", BIN)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.join(HERE, "..", "bin"))
    spec.loader.exec_module(mod)
    return mod


def test_plan_events_decides_per_date():
    cli = _load_cli()
    events = [
        {"summary": "里山整備活動", "date": "2025-05-17", "uid": "u1", "category": "里山整備",
         "source": {"posts": [{"kind": "announce", "url": "https://x/a", "title": "お知らせ",
                               "published": "2025-05-08", "body": "9時集合"}]}},
        {"summary": "名栗定期作業", "date": "2025-06-01", "uid": "u2", "category": "定期作業",
         "source": {"posts": [{"kind": "report", "url": "https://x/r", "title": "報告", "published": "2025-06-02"}]}},
    ]
    # u1 の日には我々イベントが既存、u2 の日には何も無い
    def fetch_existing(date):
        if date == "2025-05-17":
            return [{"iCalUID": "omc-u1@okumusashi-mtb", "id": "e1",
                     "summary": "里山整備活動", "description": "9時集合\n\n📣 お知らせ: https://x/a"}]
        return []
    plan = cli.plan_events(events, fetch_existing)
    by_uid = {p["event"]["uid"]: p for p in plan}
    assert by_uid["u1"]["action"] == "update_ours"
    assert by_uid["u1"]["needs_update"] is False     # 同内容 → 更新不要
    assert by_uid["u2"]["action"] == "create"
```

- [ ] **Step 2: 失敗確認**

Run: `cd calendar && python3 -m pytest tests/test_cal_omc.py -v` → FAIL

- [ ] **Step 3: 実装** (`calendar/bin/cal-omc`)

```python
#!/usr/bin/env python3
"""cal-omc — canonical イベントを Google Calendar へ投影 (既定 dry-run, --apply で書込)。

cal-myhanno に倣い gws + Service Account で iCalUID upsert。突合判定は omc_project。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import omc_project
import yaml

DEFAULT_CAL = "okumusashi.mtb@gmail.com"
DEFAULT_SA = os.path.expanduser("~/.config/omc/sa.json")


def _ensure_creds() -> None:
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        if os.path.exists(DEFAULT_SA):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = DEFAULT_SA
        else:
            sys.exit(f"error: GOOGLE_APPLICATION_CREDENTIALS 未設定かつ {DEFAULT_SA} が無い")


def _gws(*args: str, params: dict | None = None, body: dict | None = None) -> dict:
    cmd = ["gws", *args, "--format", "json"]
    if params is not None:
        cmd += ["--params", json.dumps(params, ensure_ascii=False)]
    if body is not None:
        cmd += ["--json", json.dumps(body, ensure_ascii=False)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"gws failed: {proc.stderr.strip()}")
    return omc_project.parse_gws_json(proc.stdout)


def _make_fetch_existing(cal_id: str):
    def fetch_existing(date: str):
        # その日(終日含む)に重なるイベント。singleEvents=False で iCalUID を保持。
        res = _gws("calendar", "events", "list", params={
            "calendarId": cal_id, "singleEvents": False, "showDeleted": False,
            "timeMin": date + "T00:00:00Z", "timeMax": date + "T23:59:59Z", "maxResults": 50})
        return res.get("items", []) if isinstance(res, dict) else []
    return fetch_existing


def plan_events(events: list[dict], fetch_existing) -> list[dict]:
    plan = []
    for ev in events:
        existing = fetch_existing(ev["date"])
        decision = omc_project.decide_action(ev, existing)
        body = omc_project.build_event_body(ev)
        nu = True
        if decision["target"] is not None:
            nu = omc_project.needs_update(decision["target"], body)
        plan.append({"event": ev, "action": decision["action"], "target": decision["target"],
                     "reason": decision["reason"], "body": body, "needs_update": nu})
    return plan


def _load_events(events_dir: str, year: str | None, limit: int | None) -> list[dict]:
    files = sorted(glob.glob(os.path.join(events_dir, "*", "*.yaml")))
    if year:
        files = [f for f in files if os.sep + year + os.sep in f]
    if limit:
        files = files[:limit]
    return [yaml.safe_load(open(f, encoding="utf-8")) for f in files]


def _apply_one(cal_id: str, p: dict) -> str:
    body = dict(p["body"])
    if p["action"] == "create":
        _gws("calendar", "events", "import", params={"calendarId": cal_id}, body=body)
        return "created"
    if p["action"] in ("update_ours", "overwrite_manual"):
        if not p["needs_update"]:
            return "unchanged"
        target = p["target"]
        patch = {"summary": body["summary"], "description": body["description"]}
        if p["action"] == "create" or p["action"] == "update_ours":
            patch["start"] = body["start"]; patch["end"] = body["end"]
        # overwrite_manual: 既存の start/end (時刻) を保持 → summary/description のみ
        _gws("calendar", "events", "patch",
             params={"calendarId": cal_id, "eventId": target["id"]}, body=patch)
        return "updated"
    return "skipped"


def _snapshot(cal_id: str, snap_dir: str) -> int:
    res = _gws("calendar", "events", "list", params={
        "calendarId": cal_id, "singleEvents": False, "showDeleted": False, "maxResults": 2500})
    items = res.get("items", []) if isinstance(res, dict) else []
    os.makedirs(os.path.join(snap_dir, "events"), exist_ok=True)
    for e in items:
        uid = e.get("iCalUID") or e.get("id", "")
        safe = uid.replace("@", "_at_").replace(".", "_").replace("/", "_")
        with open(os.path.join(snap_dir, "events", safe + ".json"), "w", encoding="utf-8") as f:
            json.dump(e, f, ensure_ascii=False, indent=2)
    return len(items)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events-dir", default="events")
    ap.add_argument("--year", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--review-file", default="projection-review-needed.txt")
    ap.add_argument("--snapshot-dir", default="snapshots")
    ap.add_argument("--cal-id", default=DEFAULT_CAL)
    args = ap.parse_args()

    _ensure_creds()
    events = _load_events(args.events_dir, args.year, args.limit)
    plan = plan_events(events, _make_fetch_existing(args.cal_id))

    counts = {"create": 0, "update": 0, "unchanged": 0, "skip_review": 0}
    review = []
    for p in plan:
        ev = p["event"]
        if p["action"] == "skip_review":
            counts["skip_review"] += 1
            review.append((ev["date"], ev["summary"],
                           (p["target"] or {}).get("summary", ""), p["reason"]))
            print(f"SKIP  {ev['date']} {ev['summary']!r} ({p['reason']})")
            continue
        if p["action"] == "create":
            counts["create"] += 1; verb = "CREATE"
        elif not p["needs_update"]:
            counts["unchanged"] += 1; verb = "UNCHANGED"
        else:
            counts["update"] += 1; verb = "UPDATE" + ("(manual)" if p["action"] == "overwrite_manual" else "")
        print(f"{verb:16} {ev['date']} {ev['summary']}")
        if args.apply and (p["action"] == "create" or p["needs_update"]):
            _apply_one(args.cal_id, p)

    if review:
        with open(args.review_file, "w", encoding="utf-8") as f:
            for d, s, es, r in review:
                f.write(f"{d}\t{s}\t{es}\t{r}\n")

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] create={counts['create']} update={counts['update']} "
          f"unchanged={counts['unchanged']} skip_review={counts['skip_review']}")
    if args.apply:
        n = _snapshot(args.cal_id, args.snapshot_dir)
        print(f"snapshot: {n} events -> {args.snapshot_dir}/events/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

(注: `parse_gws_json` は Task 4 で `omc_project` に追加する純関数。`_apply_one` の overwrite_manual は patch に start/end を含めない＝既存時刻保持。)

- [ ] **Step 2.5: `parse_gws_json` を omc_project に追加（テスト付き）**

`test_omc_project.py` に:
```python
def test_parse_gws_json_skips_prefix():
    out = "Using keyring backend: keyring\n{\"items\": [{\"id\": \"x\"}]}\n"
    assert omc_project.parse_gws_json(out)["items"][0]["id"] == "x"
    assert omc_project.parse_gws_json("[]") == []
```
`omc_project.py` に:
```python
def parse_gws_json(text: str):
    s = text.lstrip()
    for i, ch in enumerate(s):
        if ch in "{[":
            return json.loads(s[i:])
    raise ValueError("no JSON found in gws output")
```

- [ ] **Step 3: 失敗→実装→成功確認**

Run: `cd calendar && python3 -m pytest tests/ -v`
Expected: 全 PASS（純ロジック + plan_events の fake テスト + parse_gws_json）。`chmod +x calendar/bin/cal-omc`。

- [ ] **Step 4: Commit**

```bash
chmod +x calendar/bin/cal-omc
git add calendar/bin/cal-omc calendar/bin/omc_project.py calendar/tests/test_cal_omc.py calendar/tests/test_omc_project.py
git commit -m "feat: CLI cal-omc (dry-run計画/--apply/snapshots) + parse_gws_json (Phase 3)"
```

---

### Task 5: dry-run 確認 → 段階 apply → 検証（実カレンダー）

**Files:**
- Create: `calendar/snapshots/events/*.json`、`calendar/projection-review-needed.txt`（生成物）

**Interfaces:**
- Consumes: `cal-omc`、実 Google Calendar。
- Produces: Google Calendar に投影されたイベント + snapshot + レビュー一覧。

**※ このタスクは実カレンダーへ書き込む。dry-run で確認してから段階的に apply する。各 apply 前に出力を人間が確認する。**

- [ ] **Step 1: 全件 dry-run（書き込み無し）**

Run:
```bash
cd calendar && python3 bin/cal-omc --events-dir events
```
出力の CREATE/UPDATE/SKIP 件数と内訳を確認。`SKIP`（矛盾保留）の各行と `projection-review-needed.txt` を目視。既存手動イベントとの突合が妥当か確認する。

- [ ] **Step 2: 1 年だけ apply（最小範囲で実書き込みを検証）**

Run:
```bash
cd calendar && python3 bin/cal-omc --events-dir events --year 2025 --apply
```
Google Calendar（`okumusashi.mtb@gmail.com`）で 2025 のイベントが作成されたか、description にお知らせ本文＋リンクが入っているか、既存手動イベントが妥当に扱われたかを確認。

- [ ] **Step 3: 冪等性確認（再 apply で unchanged）**

Run:
```bash
cd calendar && python3 bin/cal-omc --events-dir events --year 2025 --apply
```
Expected: `create=0 update=0 unchanged=<前回create+update>`（重複を作らない）。

- [ ] **Step 4: 全件 apply**

Run:
```bash
cd calendar && python3 bin/cal-omc --events-dir events --apply
```
全 145 イベントを投影。snapshot 生成を確認。

- [ ] **Step 5: snapshot と review をコミット**

```bash
git add calendar/snapshots calendar/projection-review-needed.txt
git commit -m "data: Google Calendar 投影の snapshot + 投影レビュー一覧"
```

---

## 完了条件
- `cd calendar && python3 -m pytest tests/ -q` 全 PASS（Phase 1 golden 含む）。
- dry-run で投影計画が妥当、`--apply` 再実行で重複が出ない（冪等）。
- Google Calendar に 145 イベントが description（お知らせ本文＋全リンク）付きで投影され、`snapshots/` にバックアップ。
- 矛盾した既存イベントは上書きされず `projection-review-needed.txt` に残る。

## 後続（対象外）
- city-tecoli `global-ideas.yaml` への暦体登録（`/ideas/okumusashi-mtb/` 公開）。spec 別 Phase。
- 自動定期実行（cron）。
