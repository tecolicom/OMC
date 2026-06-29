# 奥武蔵マウンテンバイク友の会 暦体の構築

作成: 2026-06-22 / 対象: OMC データリポジトリ + city.tecoli.com への暦体登録

奥武蔵マウンテンバイク友の会を city-tecoli (city.tecoli.com) の暦体 (entity / idea) として
公開する。イベントの正 (source of truth) は Google Calendar とし、その中身を公式サイト
(Wix ブログ) の活動履歴からクロールして構築する。本リポジトリ (OMC) は、その
クロール → canonical YAML → Google Calendar 投影 のパイプラインと記録を管理する。

設計・実装は飯能の前例 `city-tecoli/city-data/hanno-data/calendar/` (以下 hanno-data) に
全面的に準拠する。

## 目的

1. 暦体「奥武蔵マウンテンバイク友の会」を `https://city.tecoli.com/ideas/okumusashi-mtb/` として公開する。
2. 空に近い Google Calendar (`okumusashi.mtb@gmail.com`) を、公式サイトの活動履歴 (13 年分) で埋める。
3. 以後の運用 (新しい活動の追加・再投影) を本リポジトリで継続管理できるようにする。

## 背景 (確定事実)

- **暦体の登録機構**: city-tecoli は場所非依存の暦体を `src/data/global-ideas.yaml` に定義する
  (`src/lib/idea-seeds.ts`)。id は `idea:global:<slug>`、URL は `/ideas/<slug>/`。ページ
  `src/pages/ideas/[slug]/index.astro` (SSR) と一覧 `src/pages/ideas/index.astro` が既存。
  エントリ構造は `cities/<city>/config.yaml` の `ideas:` と同じ
  (`slug` / `name_ja` / `name_en` / `url` / `calendars[].{ical_url,label,default_on}`)。
  `global-ideas.yaml` は `import.meta.glob(..., {query:'?raw', eager:true})` で **ビルド時に
  バンドルへ inline** されるため、反映には rebuild + deploy が必要。
- **アプリは外部公開 ICS を読むだけ**: `calendars[].ical_url` に公開 ICS URL を書く。アプリ側は
  イベント実体を保持しない。`/api/calendar` の SSRF 許可ホストは `calendar.google.com` / `icloud`
  のみ。Google Calendar の公開 ICS はこの許可に収まる。
- **対象 Google Calendar**: id = `okumusashi.mtb@gmail.com`。公開 ICS =
  `https://calendar.google.com/calendar/ical/okumusashi.mtb%40gmail.com/public/basic.ics`
  (HTTP 200・取得確認済、`X-WR-CALNAME: 奥武蔵マウンテンバイク友の会`)。現状イベントは僅少。
- **公式サイト (クロール元)**: `https://okumusashimtb.wixsite.com/omcweb` (Wix)。
  - `/blog` (活動記録ブログ) と `/blog-feed.xml` (RSS) を持つ。
  - RSS は**最新 20 件のみ** (2026-01〜06)。会は「第 13 回総会」= 設立 13 年で、全履歴は RSS に無い。
  - Wix Blog API (`/_api/communities-blog-node-api/_api/posts`) は `instance` トークン必須。
    トークンは JS が動的生成し静的 HTML には無い → **全件取得にはヘッドレスブラウザが必要**。
  - 記事タイトルに**イベント日 (`M/D`)** が入る (例「6/7 名栗定期作業の報告」)。`pubDate` は
    投稿日 (報告日)。一部は `【2/15(日)の活動報告】` のように 【】内に日付。
  - 1 イベントにつき「お知らせ」(予告) と「報告」(事後) の**2 記事ペア**が出る。
- **Google Calendar 管理の前例 (hanno-data)**: `bin/cal-myhanno` (Python + `gws` =
  googleworkspace/cli) が **Service Account** (`~/.config/myhanno/sa.json`,
  `GOOGLE_APPLICATION_CREDENTIALS`) で複数カレンダーを管理。
  - **YAML が canonical / Google Calendar は投影先**。全イベント終日、時刻は description 冒頭の
    `🕒 HH:MM–HH:MM` marker で保持。
  - `events/<year>/<MM-DD>_<uid>.yaml` (1 イベント 1 ファイル)。`source:` フィールド有り =
    クローラ管理、無し = 手動キュレーション (クローラ不可侵)。
  - `snapshots/<calendar-key>/events/<uid>.json` で Calendar 状態をミラー。
  - 個人 gmail カレンダーへの書き込みは、**カレンダーを SA のメールアドレスに「予定の変更」権限で
    共有**すれば可能 (ドメイン委任不要)。

## スコープ

### 対象
- OMC リポジトリの整備 (データリポジトリ構造)。
- Wix ブログのクローラ (`cal-omc-blog-fetch`): RSS + 全履歴 (ヘッドレス)。
- canonical イベント YAML の生成 (`events/`)。
- Google Calendar への投影ラッパ (`cal-omc`)。
- city-tecoli への暦体登録 (`global-ideas.yaml` への 1 エントリ追加)。

### 非対象 (YAGNI)
- city-tecoli が OMC を直接消費する仕組み (data-sync / vendoring)。OMC は独立リポジトリで、
  city-tecoli との接点は「Google Calendar の公開 ICS URL を `global-ideas.yaml` に 1 行書く」のみ。
- 英訳カレンダー (hanno の `*.en`)。当面日本語のみ。
- 自動定期実行 (cron 等)。手動運用から始める。
- Google Calendar API の OAuth ユーザフロー。Service Account + カレンダー共有で実現する。

## 設計

### 1. リポジトリ構成

```
OMC/
├── README.md                         暦体の概要・運用手順・city-tecoli 登録先
├── idea.yaml                         暦体の正規メタ (global-ideas.yaml 転記元の記録)
├── .gitignore                        sources キャッシュ・SA 鍵・__pycache__ 等を無視
└── calendar/
    ├── README.md                     カレンダー運用説明 (hanno-data/README を簡略移植)
    ├── bin/
    │   ├── _lib.py                   共通ヘルパ (hanno-data の _lib.py から必要分のみ流用)
    │   ├── cal-omc-blog-fetch        Wix ブログクローラ → events YAML
    │   └── cal-omc                   Google Calendar 投影ラッパ (cal-myhanno を流用・単純化)
    ├── events/
    │   └── <year>/<MM-DD>_<uid>.yaml  canonical イベント (source: 付き)
    ├── snapshots/
    │   └── events/<uid>.json          Google Calendar 状態ミラー
    ├── sources/
    │   └── blog/                      クロール入力キャッシュ (RSS XML / 記事 HTML / API JSON)
    └── tests/
        ├── fixtures/                  クロール入力の固定スナップショット
        └── golden/                   期待出力 YAML (回帰ロック)
```

OMC は単一暦体のリポジトリなので、hanno-data の多 source・多カレンダー・多都市の汎用機構は
持ち込まず、単一ブログ → 単一カレンダーに単純化する。

### 2. クローラ `cal-omc-blog-fetch`

入力 = Wix ブログ、出力 = `events/<year>/<MM-DD>_<uid>.yaml`。2 系統の取得を持つ。

- **RSS 系統 (コア・確実)**: `https://okumusashimtb.wixsite.com/omcweb/blog-feed.xml` を curl 取得。
  最新 20 件。`sources/blog/feed.xml` にキャッシュ。
- **アーカイブ系統 (全履歴・ヘッドレス)**: Claude in Chrome で `/blog` を開き、Wix Blog API
  (`/_api/communities-blog-node-api/_api/posts?offset=N&size=M`) を `instance` トークン付きで
  ページネーション呼び出しして全記事 JSON を取得する。取得 JSON を `sources/blog/posts-*.json`
  にキャッシュし、以後の YAML 生成はキャッシュからの決定論的処理にする (再クロール不要)。
  - 段階構成: **まず RSS 系統で確実なコアを作り**、その後アーカイブ系統で過去へ延伸する。
    アーカイブ取得が技術的に阻まれた場合も RSS 分のコアは成立する。

各記事 (RSS item / API post) からイベントを抽出する純ロジック (テスト対象):

- **イベント日の決定**: タイトル先頭の `M/D` (全角スラッシュ `／` も)、無ければ `【M/D...】`。
  年は記事の投稿日 (pubDate / firstPublishedDate) の年を既定とし、「投稿月 < イベント月」かつ
  差が大きい場合 (例 1 月投稿で 12 月イベント) は前年に補正する。
- **重複排除**: 同一イベントを指す「お知らせ」と「報告」を、(イベント日 + 正規化した活動名) で
  1 件に統合する。本文・URL は「報告」側を優先。
- **種別タグ**: タイトルから活動種別を分類 (名栗定期作業 / 里山整備・清掃 / 子ども自転車教室 /
  総会 / 日高市清掃 / その他)。`category` フィールドへ。
- **summary**: タイトルから日付接頭辞・「のお知らせ/報告」等の語尾を整理した活動名。
- **description**: 記事本文の要約 (LLM は使わず、本文先頭の決定論的抜粋) + 出典記事 URL。
- **終日イベント**として出力 (hanno と同じ方針。時刻が判明する場合のみ marker)。
- `source:` フィールドにクローラ識別子・元記事 URL・取得日を記録 (クローラ管理の印)。

`events/<year>/<MM-DD>_<uid>.yaml` の `uid` は元記事の安定 ID (Wix post id / RSS guid) から導出し、
再実行で同一イベントが同一ファイルに収束する (冪等) ようにする。

### 3. 人間レビュー (チェックポイント)

散文タイトルからの自動抽出は誤りを含む (特に古い記事は命名規約が異なる)。`events/` 生成後、
コミット前に目視レビューする工程を運用に組み込む。`tests/golden/` でパーサ出力をバイト一致で
ロックし、パーサ変更時の意図しない差分を検出する (hanno-data の golden テスト方式)。

### 4. Google Calendar 投影 `cal-omc`

- hanno-data の `cal-myhanno` を流用し、単一カレンダー (`okumusashi.mtb@gmail.com`) 向けに単純化。
- 認証 = Service Account。`GOOGLE_APPLICATION_CREDENTIALS` 未設定時は `~/.config/omc/sa.json` を試す
  (hanno の `~/.config/myhanno/sa.json` と同パターン、別パス)。
- `events/` の canonical YAML を Google Calendar へ upsert (iCalUID で突合)。`snapshots/` に
  投影後の状態をミラーして監査・バックアップにする。
- **冪等**: 同じ `events/` を二度投影しても重複イベントを作らない (iCalUID キー)。

#### 利用者の事前作業 (認証セットアップ)

1. GCP でサービスアカウントを作成し `sa.json` を取得 (hanno の myhanno SA を流用してもよい)。
   `~/.config/omc/sa.json` に置く。
2. Google Calendar 設定で `okumusashi.mtb@gmail.com` のカレンダーを **SA のメールアドレスに共有し
   「予定の変更権限」** を付与する。

### 5. city-tecoli への暦体登録

> **【訂正 2026-06-29】** 本節の「`global-ideas.yaml`(config seed)へ登録」は誤り。city-tecoli の設計
> (`docs/superpowers/specs/2026-06-22-calendar-ideas-source-design.md`)では、omc =
> `idea:global:okumusashi-mtb` は **Blobs のみの動的エンティティ**として**管理 UI(EntityManage)で登録**する
> (config seed には入れない)。areas:[hanno,hidaka,chichibu,ome] / categories:[スポーツ] も管理 UI で設定。
> → 下記の global-ideas.yaml 追加は行わない。`idea.yaml` は管理 UI 登録時の参照メタとして使う。
> 以下は当初案の記録として残す。

~~`city-tecoli/src/data/global-ideas.yaml` の `ideas:` に 1 エントリ追加 (既存 `movies` と同構造):~~ (撤回)

```yaml
  - slug: okumusashi-mtb
    name_ja: 奥武蔵マウンテンバイク友の会
    name_en: Okumusashi MTB Club
    url: https://okumusashimtb.wixsite.com/omcweb
    calendars:
      - ical_url: https://calendar.google.com/calendar/ical/okumusashi.mtb%40gmail.com/public/basic.ics
        label: 日本語
        default_on: true
```

これで `/ideas/okumusashi-mtb/` (詳細) と暦体一覧に出る。反映は city-tecoli の rebuild + deploy 時。
この変更は city-tecoli リポジトリ側のコミットになる (OMC の `idea.yaml` はその転記元の記録)。

## データフロー全体

```
Wix ブログ ──(cal-omc-blog-fetch: RSS + ヘッドレス)──▶ sources/blog/ キャッシュ
   │                                                          │
   │                                          (決定論パース・重複排除・日付/種別抽出)
   ▼                                                          ▼
events/<year>/<MM-DD>_<uid>.yaml (canonical) ◀── 人間レビュー / golden テスト
   │
   │(cal-omc: Service Account 投影, iCalUID upsert)
   ▼
Google Calendar (okumusashi.mtb@gmail.com) ──公開 ICS──▶ city-tecoli /ideas/okumusashi-mtb/
   ▲                                                          ▲
   └── snapshots/ ミラー (バックアップ)        global-ideas.yaml に ical_url 登録 ──┘
```

## テスト / 確認

- 単体: イベント日抽出 (`M/D`・`【M/D】`・全角)、年補正 (1 月投稿×12 月イベント)、お知らせ/報告の
  重複排除、種別分類、uid 冪等性。
- golden: 既知の RSS スナップショット → 期待 `events/` YAML をバイト一致でロック。
- 実データ確認: RSS 20 件から期待件数の unique イベントが生成されること。
- 投影確認: `cal-omc` で test カレンダー (または dry-run) に upsert → 二度実行で重複が出ないこと。
- 公開確認: 投影後、公開 ICS にイベントが現れること。city-tecoli を build/deploy 後に
  `/ideas/okumusashi-mtb/` が表示され、day card に予定が出ること。

## 段階 (plan で確定)

- **Phase 1**: OMC リポジトリ整備 + RSS クローラ + canonical YAML 生成 + golden テスト
  (ヘッドレス不要・自己完結で検証できる確実なコア)。
- **Phase 2**: ヘッドレスによる全履歴アーカイブ取得 → 過去へ延伸 + 人間レビュー。
- **Phase 3**: `cal-omc` 投影ラッパ + Service Account 認証 + snapshots。
- **Phase 4**: city-tecoli への `global-ideas.yaml` 登録 + build/deploy 反映確認。

Phase 境界は writing-plans で確定する。
