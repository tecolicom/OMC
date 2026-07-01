# 記事本文の段落(改行)忠実復元 設計

日付: 2026-07-01
ブランチ: website-phaseA
関連: docs/superpowers/specs/2026-06-30-omc-website-ui-refinements-design.md

## 背景

活動詳細ページで記事本文が改行なしの1段落で表示される。原因は canonical アーカイブ
`calendar/sources/blog/*.yaml` の `body` が、記事HTMLの **JSON-LD `description`**
(`omc_parse.extract_post_meta` → `_clean_body(item["description"])`) 由来で、Wix が
description を改行なし1行で提供するため。359記事中 222件が改行0。

記事HTML本体には Ricos リッチコンテンツがあり、本文は `data-hook="post-description"`
コンテナ内の `<p>` ブロックとして段落構造付きでレンダリングされている。ここから抽出すれば
忠実に復元できる(1記事で検証済み: 10段落・改行9、既存bodyと空白除去で完全一致)。

website 詳細ページは既に `whitespace-pre-line` なので、body に `\n` が入れば段落表示される。
**website 側のコード変更は不要。** 本作業は calendar パイプラインのデータ品質改善。

## スコープと非スコープ

- 対象: `calendar/sources/blog/*.yaml` の `body` フィールドのみを段落付きに更新する。
- 非対象(触らない):
  - `calendar/events/*.yaml`。website の body 供給元は archive のみ
    (`activities.ts` は `archive.get(url).body` を使用)。events の body は website からも
    Google Calendar 投影からも参照されない。events を再生成しないことで**カレンダー投影に
    影響を与えない**。
  - title / published / images / cover。これらは保持する。
  - website のコンポーネント/ページ。

## 抽出ロジック (`calendar/bin/omc_parse.py`)

新関数 `extract_post_body(html: str) -> str`:

1. `html` 中の `data-hook="post-description"` の位置を探す。無ければ後述フォールバック。
2. その位置以降を対象領域とし、`<p>...</p>` ブロックを順に抽出。
3. 各ブロックをタグ除去 (`<[^>]+>` を除去) → `html.unescape` → `unicodedata.normalize("NFKC", ...)` → 前後空白 strip。
4. 空文字、およびフッター著作権行(`Proudly created with Wix` を含む、または `©`/`(c)` で始まる行)を除外。
5. 残った段落を `\n` で連結して返す。

フォールバック(現行挙動を維持し回帰を防ぐ):
- `post-description` が見つからない、または上記で得た本文が空文字の場合は、現行どおり
  JSON-LD `description` を `_clean_body` で整形した値を返す。

`extract_post_meta` の変更:
- `body = _clean_body(item.get("description") or "")` を
  `body = extract_post_body(html)` に置き換える。
  (`extract_post_body` 内でフォールバックとして description を使うため、description が
  必要な情報は関数に html を渡すことで賄う。)

## データ再生成 (body-only リフレッシュ)

既存アーカイブの body だけを安全に更新する。full 再クロール(events 再生成)は行わない。

手段: `cal-omc-archive-fetch` に `--body-only` モードを追加する(既存フラグ・関数を再利用)。
このモードは:
1. `sources/blog/*.yaml` を列挙(引数 `--cache-dir`、既定 `sources/blog`)。
2. 各ファイルを読み、`url` を再取得(既存 `_fetch`、レート制御あり)。
3. `omc_parse.extract_post_body(html)` で新 body を得る。
4. **内容保全ガード**: 新 body と旧 body を「空白全除去 + NFKC 正規化」した文字列で比較。
   - 一致 → 旧 body を新 body に置換(= 改行の追加のみ)。ファイルを書き戻す
     (`dump_archive_yaml`、他フィールドは保持)。
   - 不一致 → **上書きしない**。「要確認(content-changed)」として記録。
   - `post-description` 無し等でフォールバック(description)になった場合、新旧が一致すれば
     実質変化なしなので書き戻し省略でよい(記録のみ)。
5. events YAML の再生成・書き出しは行わない。
6. 実行サマリを標準出力(または `--report` ファイル)に出す:
   - 更新件数(改行が付いた件数)、変化なし件数、フォールバック件数、要確認(content-changed)件数、
     取得エラー件数。要確認・エラーは url を列挙。

冪等性: 2回目の実行では、既に改行付きの body は「空白除去で一致」判定になり、かつ改行込みで
既に一致するため書き戻し不要(または同一内容の書き戻し)。ネットワーク取得は毎回発生する。

## テスト

`calendar/tests/`:
- `test_omc_parse.py` に `extract_post_body` の単体テストを追加:
  - `post-description` + 複数 `<p>` を持つ HTML → 段落が `\n` 連結で返る。
  - フッター著作権行が除外される。
  - `post-description` が無い HTML → JSON-LD description フォールバック。
  - 本文が空 → フォールバック。
  - 既存 fixture(`tests/fixtures/post-recent.html` 等)が `post-description`/`<p>` 構造を
    持つか確認し、持たなければ本文段落を含む fixture を1つ追加(実記事HTMLの本文領域を縮約したもの)。
- 既存の `extract_post_meta` 系テスト・golden(`tests/golden/`, `test_golden.py`)の body 期待値を
  新仕様に更新する(description ベースから post-description ベースへ)。fixture が description のみで
  `post-description` を持たない場合はフォールバックで現行期待値が維持されることを確認。
- `cd calendar && python -m pytest tests/ -q` が全て緑。

## 検証(実データ)

- `--body-only` 実行後のサマリを確認: 要確認(content-changed)・エラーが妥当な範囲か。
  要確認が多い場合は個別に diff を見て判断(Wix 側編集の可能性)。
- サンプル数件で `body` に改行が入り、内容が旧と一致(空白除去)することを目視。
- website を `make site-dev` で開き、詳細ページ(例 里山整備のお知らせ)が段落表示になることを確認。

## 実行順

1. spec(本書) → plan。
2. `extract_post_body` + テスト(TDD)。
3. `--body-only` モード + テスト。
4. `--body-only` 実行 → サマリ確認 → 要確認/エラーの扱いを決定。
5. website プレビューで段落表示を確認。
6. その後、既存の公開手順(ff マージ → public 化 → Pages 公開)へ。

## リスクと緩和

- **Wix 側で記事が編集され内容が変わっている**: 内容保全ガードで上書きせず要確認に回す。
  勝手に canonical を書き換えない。
- **本文抽出が一部記事で崩れる**: フォールバックで description を使い、内容一致時のみ更新するため
  崩れた本文が混入しない(不一致は要確認)。
- **ネットワーク/レート**: 既存 `_fetch` のレート制御を再利用。

## スコープ外(将来)

- events YAML の body も段落付きにする(現状未使用のため不要。将来 full 再クロール時に
  改善版 `extract_post_body` が自動適用される)。
- 本文中の生 URL のリンク化(Phase B)。
