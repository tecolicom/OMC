# 本文取り込み + Google Calendar 投影 設計

作成: 2026-06-25 / 対象: OMC データリポジトリ + Google Calendar `okumusashi.mtb@gmail.com`

Phase 1/2 で構築した canonical イベント (145 件、開催日キー、`source.posts[]` に関連ブログ記事) を、
(A) **ブログ本文を取り込んでデータを充実させ** (Phase 2.5)、(B) **Google Calendar へ投影する** (Phase 3)。
飯能の前例 `hanno-data/calendar`（`cal-myhanno` = Python + `gws` + Service Account）に準拠する。

## 背景 (確定事実)

- **ブログ本文は JSON-LD にある**。各記事ページの `<script type="application/ld+json">` の `BlogPosting`
  に `headline`（タイトル）・`datePublished`（投稿日）・**`description`（本文全文）** が入る。本文は
  `&#010;` 等の HTML 実体・全角を含むので `html.unescape` + NFKC 正規化が要る。Phase 1/2 の
  `extract_post_meta` は headline/datePublished のみ取得していた。
- **本文に開催時刻が書かれている**（例「9時〜11時まで整備」「日時：１０月１５日　８時３０分〜
  １１時３０分」）。359 記事中、明確な時間レンジ 58 件・開始時刻 50 件・何らかの「N時」188 件。
  → **構造化した時刻抽出はしない**（自由文・ノイズあり）。本文を description に載せれば読めば分かる、
  というユーザ方針。
- **現キャッシュが肥大**。`cal-omc-archive-fetch` は生 HTML（1 記事 ≈ 960KB、359 件で ~340MB）を
  `sources/blog/<sha1>.html` にキャッシュしている。実際に要るのは JSON-LD の 3 項目のみ。
- **canonical の現状**。`events/<year>/<MM-DD>_<uid>.yaml`、`source.posts[]` は各記事の
  `{kind, url, title, published}`（kind = report / announce / other）。`description` は報告URL 1本のみ。
- **Google Calendar アクセス確認済**（2026-06）。SA `myhanno-bot@city-tecoli.iam.gserviceaccount.com`
  に当カレンダーを共有済み、`accessRole: writer`。鍵 `~/.config/omc/sa.json`（myhanno 流用）。
  操作は `gws`（googleworkspace/cli、`gws calendar events list/get/import/update --params/--json`）。
- **既存イベント**。カレンダーには手動作成イベントが既に存在し、一部は時刻付き（dateTime）。

## ユーザ確定方針

- カレンダー予定の本文 = **お知らせ本文（可能なら全文、長すぎたら切る）＋ 関連記事リンク全件**。
- **報告(report)は本文を入れずリンクのみ**。
- 時刻抽出はしない（本文で読める）。
- 既存イベントを上書きする際は**既存の時刻情報を保存**する。
- ブログと**矛盾しない既存イベントは上書きしてよい**、矛盾するものは残してレビュー。
- キャッシュは**読みやすい YAML**で保存する。

## スコープ

- **Phase 2.5（データ・キャッシュ改修）**: 本文抽出、YAML スリムキャッシュ移行、canonical に本文付与。
- **Phase 3（投影）**: `cal-omc` で canonical → Google Calendar に冪等 upsert、既存と突合。
- **非対象**: 構造化時刻抽出。city-tecoli への暦体登録 (別 Phase)。自動定期実行。

---

## Phase 2.5: 本文取り込み + YAML キャッシュ

### 1. `extract_post_meta` の拡張
返り値を `{title, pub_date, body}` に拡張。`body` = JSON-LD `BlogPosting.description` を
`html.unescape` + `unicodedata.normalize("NFKC", ...)` し、各行を rstrip、前後空行を除去した本文。
`description` が無ければ `body=""`。headline/pub_date の既存仕様は不変（後方互換）。

### 2. YAML スリムキャッシュ
- 1 記事 = 1 YAML ファイル `sources/blog/<slug>.yaml`:
  ```yaml
  url: https://okumusashimtb.wixsite.com/omcweb/post/2019/07/23/8月4日名栗…のお知らせ
  title: 8月4日名栗じてんしゃ広場定期整備のお知らせ
  published: '2019-07-23'
  body: |
    いつも名栗じてんしゃ広場の整備に参加して頂きありがとうございます。
    …
    日時   8月4日   9時より
  ```
- `body` は YAML **ブロックスカラー (`|`)** で改行保持（読みやすさ）。実装は str 用 representer で
  複数行は block style にする。
- **ファイル名 = URL スラッグの安全化**: `/post/` 以下を取り、`/`→`_`、パス不可文字
  (`<>:"\|?*` と制御文字) を除去/置換。URL から導出できるのでキャッシュ照合に使える（sha1 廃止）。
- キャッシュ照合: 取得前に URL からスラッグ→ファイル名を計算し、存在すれば読む、無ければ fetch して
  JSON-LD 抽出 → この YAML を書く（fetch 間 0.3 秒）。

### 3. 既存 HTML キャッシュの移行
- 現存する 359 件の `sources/blog/*.html` から `extract_post_meta` で `{title,pub_date,body}` を抽出し、
  上記 YAML に書き出す移行スクリプト（再 fetch しない）。
- 移行後、巨大な `*.html` は削除（`sources/blog` は .gitignore 済みなのでコミット対象外）。

### 4. canonical への本文付与
- `build_events` が `source.posts[]` に **`body` を追加**（kind が report 以外＝announce / other のとき）。
  **report は body を持たせない**（リンクのみの方針）。
- `event_to_yaml_dict` を本文対応に拡張するため、`build_events` が各 post に body を載せられるよう、
  CLI が item に body を渡す（`{title, link, guid, pub_date, body}`）。
- 既存の `description: 出典: <url>` は当面維持（canonical の description は Phase 3 の投影では使わず、
  投影側が posts から組み立てる）。
- 再生成: 移行済み YAML キャッシュから `cal-omc-archive-fetch` を再実行し、145 件を本文付きで更新。

### Phase 2.5 のテスト
- `extract_post_meta`: JSON-LD description を本文として返す（fixture: 既存 post-recent/old に
  description 入りブロックを使うか、新 fixture）。HTML 実体・全角の正規化、description 不在で body=""。
- YAML キャッシュ: slug 生成（全角・パス区切りを含む URL → 安全なファイル名、URL から再現可能）、
  body のブロックスカラー出力（読み戻して一致）。
- canonical: announce/other に body が付き、report に付かないこと。Phase 1 golden は本文を持たない
  RSS 経路なので**不変**であること（RSS 側の `extract_post_meta` 非経由を確認）。

---

## Phase 3: Google Calendar 投影 (`cal-omc`)

### 1. イベント description の組み立て
canonical イベントの `source.posts[]` から、Google Calendar 予定の description を生成:

```
<お知らせ本文（全文。複数あれば連結。長すぎる場合は truncate）>

📣 お知らせ: <announce url>
⚠️ 中止: <中止お知らせ url>
📝 報告: <report url>
```

- **本文**: kind が report 以外の post の `body` を採用（複数あれば日付順に連結、見出し付き）。
  report の body は使わない。
- **truncate**: 本文合計が閾値（既定 **1000 文字**）を超えたら超過分を切り、末尾に
  「…（続きはリンク先で）」を付ける。Google Calendar の description 上限（~8KB）には十分収まるが、
  読みやすさのため上限を設ける。
- **リンク集**: posts を全件、kind ラベル付き（📣お知らせ / ⚠️中止（タイトルに「中止」を含む
  announce）/ 📝報告 / 🔗その他）で列挙。報告もここに**リンクとして**出る（本文は出さない）。

### 2. イベントの日時
- **新規作成**: canonical は終日 → `start.date`/`end.date`（終日イベント）。
- **既存を上書き**: 既存イベントが時刻付き（`start.dateTime`）なら、**その start/end を保持**し、
  summary と description のみ更新する。既存が終日なら終日のまま。

### 3. 冪等 upsert と既存突合
- 我々が管理するイベントは **iCalUID = `omc-<uid>@okumusashi-mtb`**（`<uid>` は canonical の date 由来
  12 桁）。`gws calendar events import`（iCalUID 指定で upsert）で冪等化。
- **突合ロジック**（開催日キー、方針は記録済み reconcile）:
  - その日に **我々の iCalUID のイベントが既存** → import で更新（冪等）。
  - その日に **手動イベント**（別 iCalUID）があり **矛盾しない**（活動が両立。初期判定: summary が
    明確に食い違わない）→ **その既存イベントを上書き**（summary/description 更新、時刻保持）。
    上書きしたら、以後は我々管理として扱う（その eventId を記録、または iCalUID 付与を試みる）。
  - **矛盾する** → 上書きせず、`projection-review-needed.txt` に `date\tcanonical-summary\texisting-summary`
    を出して人手判断。
  - その日に既存なし → 新規作成。
- **「矛盾」初期判定**: 同日に複数の手動イベントがある／既存 summary が canonical の category と明らかに
  別系統（例 既存「総会」vs canonical「里山整備」）なら矛盾扱い。曖昧なら保留側に倒す（安全)。

### 4. 安全運用（dry-run → apply）
- `cal-omc` は既定 **dry-run**: 何を create/update/skip するかを一覧出力するのみ（API 書き込みなし）。
- `--apply` で実書き込み。`--year YYYY` や `--limit N` で範囲を絞れる（最初は 1 年で試す）。
- 投影後、`gws` で取得した状態を `snapshots/` にミラー（監査・バックアップ）。

### 5. gws 出力の扱い
- `gws` は stdout 先頭に `Using keyring backend: keyring` 等の行を出すことがある。JSON パース時は
  先頭の非 JSON 行を読み飛ばす（最初の `{`/`[` 以降を JSON とする）。

### Phase 3 のテスト
- description 組み立て（純関数）: お知らせ本文＋リンク集の整形、report 本文非掲載、truncate、
  複数 announce 連結、中止ラベル。golden 的にいくつかの canonical → 期待 description をロック。
- 日時: 既存 dateTime を保持して summary/description のみ更新する分岐。
- 突合: 我々 iCalUID 既存→更新、手動・非矛盾→上書き、矛盾→レビュー、無し→新規 の各分岐。
- dry-run が API を呼ばないこと（gws 呼び出しを差し替え可能にして検証、または dry-run 経路に
  書き込み API を通さない）。
- 実機: `--year` で 1 年分を dry-run→apply し、Google Calendar に反映・再実行で重複しないことを確認。

## 実装フェーズ

- **Phase 2.5**: extract_post_meta 拡張 / YAML キャッシュ / 移行 / canonical 本文付与（plan で詳細化）。
- **Phase 3**: description 組み立て / 日時 / 突合 / dry-run・apply / snapshots（plan で詳細化）。

各 Phase は単体で動作・テスト可能。Phase 2.5 を先にマージしてから Phase 3 に進む。

## 注記
Phase 1/2 の RSS 経路（`cal-omc-blog-fetch` + golden）は本文を扱わないため不変。本文・本設計は
アーカイブ経路（`cal-omc-archive-fetch`）と新規 `cal-omc` に閉じる。
