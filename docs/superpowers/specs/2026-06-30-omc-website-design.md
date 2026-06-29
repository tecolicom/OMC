# 奥武蔵マウンテンバイク友の会 ウェブサイト 設計

作成: 2026-06-30 / 対象: OMC リポジトリ内に新設する公開ウェブサイト（GitHub Pages）

OMC に保存した活動データ（活動記録・ブログ本文・写真）をもとに、**モダンで写真主体の公開サイト**を作り、
GitHub Pages で公開する。Wix の汎用サイトより、速度・見た目・自分たちのデータ活用で上回ることを狙う。

## 目的・性格（確定）

- **バランス型**: トップで会を紹介しつつ、豊富な**活動アーカイブ**もしっかり見せる。
- **アウトドア・写真主体**: 里山・MTB の自然な雰囲気。大判の写真、アースカラー、躍動感。スマホ最優先。

## 確定した方針（ユーザ承認済み）

1. 技術: **Astro + Tailwind CSS** → 静的ビルド → **GitHub Pages**（GitHub Actions で自動公開）。
2. 置き場所: **OMC リポジトリを public 化し、`site/` にサイトを同居**（データと同じリポジトリ）。
3. 公開URL: 当面 `https://tecolicom.github.io/OMC/`（独自ドメインは後回し）。
4. 写真: **取り込んで保存**（Wix のリサイズ版URLで web サイズ取得 → リポジトリに保存）、Astro が最適化。

## 背景（確定事実 / データ）

- `calendar/events/<year>/<MM-DD>_<uid>.yaml` … **活動 145 件**（2017–2026、開催日・種別・summary・`source.posts[]`）。
  種別: 里山整備47 / 定期作業52 / 清掃活動13 / 自転車教室14 / 総会3 / ライド1 / その他15。
  `source.posts[]` = `{kind(announce/report/other), url, title, published, body?(お知らせ側), images?}`。
- `calendar/sources/blog/<slug>.yaml` … **記事アーカイブ 359 件**（`url, title, published, body, images, cover`）。
  本文は**全記事にある**（報告も含む。events 側は報告 body を持たないので、本文はこちらが正）。
- 写真: ユニーク画像 **928 枚**。URL は `https://static.wixstatic.com/media/<id>...`。
  **元URLはフル解像度（最大30MB級）**なので使わない。Wix の変換URL（`/v1/fit/w_1600,...`）で web サイズを取得する。
- 画像は現状 HTTP 200 で取得可能（Wix CDN 稼働中）。取り込み後は Wix 非依存になる。

## アーキテクチャ

```
OMC リポジトリ (public)
├── calendar/            … 既存（活動データ・道具）。サイトはここを「読むだけ」
│   ├── events/*.yaml
│   └── sources/blog/*.yaml
├── site/                … 新規：Astro サイト
│   ├── src/
│   │   ├── data/        … YAML を読み込む loader（events + archive を url で結合）
│   │   ├── assets/photos/ … 取り込んだ写真（コミット）。<media-id>.jpg
│   │   ├── components/  … Hero / ActivityCard / PhotoGrid / Timeline / Filter / ...
│   │   ├── layouts/
│   │   └── pages/       … 各ページ（下記 IA）
│   ├── scripts/fetch-photos.mjs … 写真取り込みスクリプト（不足分のみ DL）
│   ├── astro.config.mjs … site/base 設定（/OMC/）
│   └── package.json
└── .github/workflows/deploy-site.yml … Pages へ自動公開
```

### データ層（site/src/data/）
- ビルド時に `../calendar/events/*.yaml`（活動）と `../calendar/sources/blog/*.yaml`（記事本文・写真）を
  `fs`+`yaml` で読み込む TypeScript モジュールを用意し、型付きで公開する。
- **結合**: 各活動（event）の `source.posts[]` の `url` で archive を引き、**各記事のフル本文＋写真**を付与する
  （events 側に無い「報告の本文」を archive から補う）。
- 公開する活動モデル（例）:
  ```ts
  type Activity = {
    date: string; category: string; title: string;   // event 由来
    articles: { kind: 'announce'|'report'|'other'; title: string; url: string;
                published: string; body: string; images: string[] }[];  // archive 結合
    photos: string[];   // articles の images を集約（media-id のリスト）
  }
  ```
- 写真の参照は **media-id**（URL から `/media/<id>` を取り出したもの）で行い、`assets/photos/<id>.jpg` に対応させる。

### 写真の取り込み（scripts/fetch-photos.mjs）
- archive の `images[]` + `cover` から**ユニークな media-id**を集め、`assets/photos/<id>.<ext>` が無いものだけ
  Wix 変換URL（`https://static.wixstatic.com/media/<id>/v1/fit/w_1600,h_1600,q_85,enc_auto/<file>`）で取得して保存。
- 取得した写真は**リポジトリにコミット**（≈数百MB 見込み。各 <1MB）。CI は再ダウンロードせず既存を使う。
- Astro の画像最適化（`astro:assets`、`import.meta.glob` で `assets/photos/` を読み込み）で **WebP・レスポンシブ**化。
- 失敗した画像はスキップしログ（壊れ画像でビルドを止めない）。

### 公開（GitHub Actions）
- `astro.config.mjs`: `site: 'https://tecolicom.github.io'`, `base: '/OMC'`。リンク・画像は `BASE_URL` を使う。
- `.github/workflows/deploy-site.yml`: `main` への push で `site/` をビルドし `actions/deploy-pages` で公開。
  写真はコミット済みなので CI でのダウンロードは不要。
- リポジトリ設定で Pages を「GitHub Actions」ソースに設定（手順は plan に明記、初回は人手設定）。

## 画面構成（IA）

| ページ | 内容 |
|---|---|
| `/`（トップ） | 写真ヒーロー＋会の一言紹介／最近の活動（写真カード）／写真ハイライト（グリッド）／Google カレンダー購読導線／入会・問い合わせへの導線 |
| `/activities/`（活動アーカイブ） | 年別タイムライン ＋ **種別フィルタ**（里山整備/定期作業/清掃/自転車教室/総会/ライド/その他）。活動カード一覧 |
| `/activities/<slug>/`（活動詳細） | 開催日・種別・タイトル／お知らせ本文・報告本文（種別ラベル付き）／**写真ギャラリー**／元記事リンク。slug は `<year>-<MM-DD>`（uid 付き） |
| `/gallery/`（写真ギャラリー） | 全活動の写真をまとめてグリッド表示（クリックで拡大＝ライトボックス、出典活動へリンク） |
| `/about/`（会について） | 活動内容・活動エリア・入会案内（`idea.yaml` ＋ 追記文）。公式ブログ・SNS へのリンク |

- **カレンダー**: 今後の予定は Google カレンダー（`okumusashi.mtb@gmail.com`）の購読ボタンを主とする
  （現状データは過去中心のため）。ビルド時に公開 ICS から「今後の予定」を読み、あれば表示する（任意・無ければ非表示）。

## 見た目（デザイン方針）

- **アースカラー**: 土（ブラウン）・若葉（グリーン）・空（ブルー）を基調に、写真が映える落ち着いた背景。
- **写真ファースト**: 一覧は写真カード／グリッド、活動詳細は大判ギャラリー。余白で写真を引き立てる。
- **タイポグラフィ**: 読みやすい和文（例: Noto Sans JP）＋ 見出しに英字ディスプレイ書体を効かせ、躍動感を出す。
- **動き控えめ**: ホバーやフェード程度。重い JS は使わない（Astro の静的＋必要箇所のみ島）。
- レスポンシブ（スマホ最優先）。アクセシビリティ（alt・コントラスト）に配慮。
- 具体のビジュアルは実装時に frontend-design で詰める（本 spec はトーンと構造を確定）。

## 実装フェーズ（plan で確定）

- **Phase A（コア）**: OMC を public 化 / `site/` に Astro 雛形 / データ層（events+archive 結合）/ 写真取り込み /
  トップ・活動アーカイブ・活動詳細・会について / Pages 自動公開。これで「見られるサイト」が成立。
- **Phase B（拡充）**: 写真ギャラリー（ライトボックス）/ カレンダー今後の予定 / デザイン磨き込み / 独自ドメイン。

## テスト / 確認

- データ層: events と archive の結合（url 一致）、本文・写真の付与、種別フィルタの集計を単体テスト（vitest）。
- 写真取り込み: 変換URLで取得・保存できること、既存はスキップ（冪等）。1枚で実地確認。
- ビルド: `astro build` がエラーなく通る。`base=/OMC` でリンク・画像が壊れない（プレビューで確認）。
- 公開: Actions で Pages にデプロイ → `https://tecolicom.github.io/OMC/` 表示確認（スマホ含む）。
- 既存の python 道具・テスト（`make test`）に影響しないこと。

## 非対象（YAGNI）

- CMS・管理画面（更新は YAML＋写真取り込み＋再ビルドで行う）。
- コメント・問い合わせフォーム等の動的機能（当面は外部リンク／メール）。
- 多言語化。
- 独自ドメイン（Phase B 以降。当面 github.io）。

## 注記

- OMC を public にするため、機密が無いことを最終確認する（SA鍵 `~/.config/omc/sa.json` は元から repo 外、`.gitignore` 済み）。
- city.tecoli.com の暦体（`/ideas/okumusashi-mtb/`）とは**別物**。本サイトは会の独立した公式サイトとして作る
  （city.tecoli は地域横断のカレンダー連携、本サイトは会そのものの紹介・記録）。両者から本サイトへ相互リンク可。
