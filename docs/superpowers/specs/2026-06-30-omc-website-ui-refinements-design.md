# OMC サイト UI 改善 設計（Phase A 仕上げ）

日付: 2026-06-30
ブランチ: website-phaseA
関連: docs/superpowers/specs/2026-06-30-omc-website-design.md

## 背景

Phase A のローカルプレビュー確認中に出た 3 点のフィードバックに対応する。
1 活動カード = 1 カレンダーイベントで、その日の `source.posts`（お知らせ/報告/関連記事）を
`kind` で束ねて 1 つの活動として表示している構造は維持する。

## 変更点

### 1. 写真なしイベントのデフォルトカバー（活動カード）

- 画像を 1 枚も持たないイベント（48 件）のカードに OMC ロゴを表示する。
- ロゴ素材: 公式ブログ（okumusashimtb.wixsite.com/omcweb）から取得した
  `c3395c_58a6ea367ffd42b98475ed2951dcfbe0.jpg`（269×271、クリーム地に赤茶の装飾枠、
  "OKUMUSASHI MTB CLUB"）。`site/src/assets/omc-logo.jpg` として取り込む。
- 表示: ロゴは図像なので `object-contain`（全体が見える・余白あり、クリーム地に中央配置）。
  写真があるカードは従来どおり `object-cover`（切り抜き）。
- Astro `Image` で最適化（WebP 化）する。

### 2. 詳細ページで お知らせ/報告 の写真を分離

- 現状の「上部に全記事の写真を 1 グリッドで合体表示」を廃止する。
- 各記事セクションの中に、その記事の写真を表示する。セクションの構成は:

  ```
  📝 報告 / 📣 お知らせ / 🔗 記事   ← kind 見出し
    [写真][写真][写真]              ← その記事の写真（あれば。写真→本文の順）
    本文…
    元の記事を見る →
  ```

- 写真が本文より上、という現状の並び（写真→本文）は維持する。
- 該当記事に写真がなければそのセクションは写真を出さない（テキストのみ）。

### 3. 記事の時系列整列

- 各活動内の記事（articles）を `published` 昇順（時系列）に並べ替える。
- 理由: 現状は `source.posts` がクローラの発見順のままで論理的順序になっておらず、
  例えば 2024-05-26 では お知らせ(公開 05-13) より 報告(公開 05-29) が先に表示されていた。
- 昇順整列により「告知 → 実施 → 報告」の自然な流れになり、多くのケースで
  お知らせが先・報告が後になる。複数の関連記事も古い順に並ぶ。

## 実装方針

### データ層 `site/src/data/activities.ts`

- `Article` 型に `photos: string[]`（記事ごとの写真ファイル名、記事内で重複排除）を追加する。
- `buildActivities` 内で:
  - 各記事の `photos` を `images` から `photoFilename` 変換 + 記事内 dedup で生成する。
  - 各活動の `articles` を `published` 昇順にソートする（安定ソート）。
  - 活動全体の `photos`（カバー判定用）は、ソート後の記事順に走査して全記事横断で
    重複排除して生成する（既存仕様を維持）。

### `site/src/components/ActivityCard.astro`

- カバー写真（`activity.photos` の最初に存在する写真）が無い場合、OMC ロゴを表示する。
- 写真あり: `object-cover`。ロゴ: `object-contain`（クリーム地）。

### `site/src/pages/activities/[slug].astro`

- 上部の `PhotoGrid`（合体表示）を削除する。
- 各記事セクションで「kind 見出し → `PhotoGrid filenames={art.photos}` → 本文 → 元記事リンク」を出す。
- `articles` は既にデータ層で時系列ソート済みのものをそのまま使う。

### 素材

- `site/src/assets/omc-logo.jpg` を追加（上記ロゴ）。

## テスト

- データ層テスト（vitest）を追加・更新する:
  - 各活動の `articles` が `published` 昇順に並ぶこと。
  - `Article.photos` が `images` から正しく生成され、記事内で重複排除されること。
  - 活動横断の `photos` 重複排除が維持されること。
- `make site-build` が成功すること（全ページビルド）。

## スコープ外（Phase B 以降）

- 写真ライトボックス、今後の予定（ICS）、デザイン磨き込み、独自ドメイン。
