# site/ — 奥武蔵マウンテンバイク友の会 ウェブサイト

会の活動記録を公開するウェブサイト（<https://tecolicom.github.io/OMC/>）のソース。
Astro + Tailwind CSS の静的サイトで、リポジトリの活動データ（`../calendar/`）から
トップ・活動一覧・活動詳細・会について のページを生成する。

## 何が見られる

- **トップ**: 会の紹介、最近の活動、Google カレンダー（今後の予定）の埋め込み
- **活動アーカイブ**: 全活動を年別に一覧（種別フィルタ付き）。写真の無い活動は会のロゴを表示
- **活動詳細**: お知らせ／報告ごとの本文（段落・字下げを保持）と写真（クリックで拡大・前後送り）
- **会について**: 会の説明・活動エリア

## データの出どころ

- 活動・記事・写真リンク: `../calendar/events/` と `../calendar/sources/blog/`（canonical データ）
- 写真の実体: `src/assets/photos/`（`scripts/fetch-photos.mjs` でブログから取り込み済み。ビルド時に WebP 最適化）
- 今後の予定カレンダー: Google カレンダー `okumusashi.mtb@gmail.com` の公開埋め込み（ブラウザがライブ読み込み）

## 開発・ビルド

Node は nodenv 管理、`../.node-version` = 22.22.2（Astro 7 は Node ≥22.12 が必要）。
リポジトリ直下の `make` が便利：

```bash
make site-dev      # ローカルで開発表示（http://localhost:4321/OMC/）
make site-build    # 本番ビルド（site/dist/ に出力）
make site-photos   # 不足している写真をブログから取り込む
```

`site/` 内で直接 `npm run dev` / `npm run build` / `npx vitest run` も可。

## 公開（デプロイ）

`main` に push すると GitHub Actions（`../.github/workflows/deploy-site.yml`）が
Node 22.22.2 でビルドし、GitHub Pages（base path `/OMC`）へ自動公開する。

## 主な構成

| 場所 | 内容 |
|---|---|
| `src/data/activities.ts` | 活動データ層（events×archive を記事 URL で結合、写真名の解決、slug 生成） |
| `src/lib/photos.ts` | 取り込み済み写真の解決（`getPhoto`） |
| `src/components/` | `ActivityCard` / `PhotoGrid` / `Lightbox` など |
| `src/pages/` | `index` / `activities`（一覧・`[slug]` 詳細）/ `about` |
| `src/layouts/Base.astro` | 共通レイアウト |
| `src/assets/photos/` | 取り込んだ写真（ビルドで WebP 最適化） |
| `scripts/fetch-photos.mjs` | ブログ画像の取り込み |
| `src/data/activities.test.ts` | データ層のテスト（vitest） |

全体像（この保管庫の目的やカレンダーとの関係）は、リポジトリ直下の `../README.md` を参照。
