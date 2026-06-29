# calendar/

会のブログ（Wix）の活動履歴を取り込み、活動記録（canonical YAML）にまとめ、会の Google カレンダーへ
反映するためのパイプライン一式。記事の本文・写真リンクのアーカイブ（保全）もここで持つ。

全体像と平易な説明は、リポジトリ直下の `../README.md` を参照。本ファイルは**維持担当者向けの技術メモ**。

## データの流れ

```
Wix ブログ ──(クロール)──▶ sources/blog/*.yaml ──(集約)──▶ events/<year>/*.yaml ──(投影)──▶ Google Calendar
              (RSS / 全記事)   記事アーカイブ(保全)        canonical イベント        okumusashi.mtb@gmail.com
                                                                                       └▶ snapshots/(控え)
```

## ディレクトリ

| 場所 | 内容 |
|---|---|
| `bin/` | 道具（クローラ・投影ツール・内部処理）。下表参照 |
| `events/<year>/<MM-DD>_<uid>.yaml` | canonical イベント（1 活動 1 ファイル、`source:` 付き＝クローラ管理） |
| `sources/blog/<slug>.yaml` | ブログ記事 1 本ずつの控え（title / published / body / images / cover）。**コミット対象＝保全** |
| `sources/blog/chrome-ids.txt` | 「全ページ共通の画像（会と無関係）」の既知リスト。dedupe が使う |
| `snapshots/events/*.json` | Google カレンダー登録後の状態の控え（バックアップ） |
| `events-review-needed.txt` | 日付が読み取れずスキップした記事の一覧（手動確認用） |
| `projection-review-needed.txt` | 投影時に「別団体の予定」等で保留した日の一覧 |
| `tests/` | 単体 + ゴールデン回帰テスト |

## 道具（`bin/`）

| 道具 | 役割 |
|---|---|
| `cal-omc-blog-fetch` | ブログ **RSS（最新約20件）** → events YAML。手早い差分更新用 |
| `cal-omc-archive-fetch` | ブログ **サイトマップ（全記事）** → events YAML + 記事アーカイブ（`sources/blog/`）。本文・写真も取得 |
| `dedupe-chrome-images` | アーカイブの画像から、多数記事に共通で出るサムネ（chrome）を除去。既知 id は `chrome-ids.txt` に永続化 |
| `cal-omc` | events → **Google カレンダー投影**。既定 dry-run（確認のみ）、`--apply` で実書き込み、`snapshots/` 出力 |
| `migrate-html-cache` | （一回限り・歴史的）旧 HTML キャッシュ → YAML アーカイブへの移行。通常は使わない |
| `omc_parse.py` | クロール／解析の純ロジック（RSS・JSON-LD・日付/種別抽出・dedup・YAML 化）。直接実行しない |
| `omc_project.py` | 投影の純ロジック（description 組み立て・イベント本体・突合判定）。直接実行しない |

## よく使う手順

```bash
cd calendar

# 全記事から活動記録を更新（本文・写真込み）
python3 bin/cal-omc-archive-fetch --fetched $(date +%F)
python3 bin/dedupe-chrome-images sources/blog

# Google カレンダーへ反映：まず確認（dry-run）→ 問題なければ --apply
python3 bin/cal-omc --events-dir events
python3 bin/cal-omc --events-dir events --apply

# 範囲を絞る例（1年だけ／件数制限）
python3 bin/cal-omc --events-dir events --year 2025 --apply

# テスト
python3 -m pytest tests/ -q
```

## イベント YAML の例（`events/`）

```yaml
summary: 名栗定期作業          # 活動名（新規作成時のカレンダー表題）
date: '2025-08-03'             # 開催日（記事タイトルから抽出。投稿日ではない）
all_day: true                 # 終日
category: 定期作業
description: '出典: <報告記事URL>'
source:                       # この欄があれば「クローラ管理」。手動イベントは source なし＝不可侵
  type: omc-blog
  crawler: cal-omc-archive-fetch
  posts:                      # 同じ活動の関連記事をまとめて保持
    - kind: announce          # お知らせ
      url: ...
      title: ...
      published: '2025-07-18'
      body: |                 # お知らせ本文（報告には body を入れない＝リンクのみ）
        ...
    - kind: report            # 報告
      url: ...
      images:                 # 写真のありか（元URL。主に報告に付く）
        - https://static.wixstatic.com/media/....jpg
```

## 仕組みのポイント

- **開催日が軸**。同じ日の「お知らせ」と「報告」（中止告知なども）は 1 つの活動にまとめる。
  カレンダーの説明（description）は **お知らせ本文＋関連記事リンク全件**、報告は**リンクのみ**。
- **投影は冪等**。各イベントは iCalUID `omc-<日付>@okumusashi-mtb` を持ち、`cal-omc` を何度実行しても
  予定が二重にならない。既存の手動イベントは**タイトル・時刻を残し、説明だけ**更新。別団体の予定は保留して触らない。
- **認証**：`cal-omc` は Service Account 鍵（`~/.config/omc/sa.json`）を使う。対象カレンダーを
  その SA に「予定の変更」権限で共有しておく必要がある。
- **写真の取り込み**は本文写真の元URLのみ（全ページ共通サムネは `dedupe-chrome-images` で除外）。

## ウェブサイト（city.tecoli.com）への登録について

会のページ `https://city.tecoli.com/ideas/okumusashi-mtb/` は、city.tecoli.com 側の **管理画面で登録する
「動的エンティティ」**（`idea:global:okumusashi-mtb`）として扱う。**このリポジトリから city.tecoli.com の
ファイルは編集しない**（疎結合）。会の基本情報の参照値は `../idea.yaml`。
