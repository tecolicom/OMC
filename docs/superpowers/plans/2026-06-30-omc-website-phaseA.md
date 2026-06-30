# 奥武蔵MTB友の会 ウェブサイト Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OMC のデータ（活動145・記事359・写真928）から、Astro 製の写真主体サイトを `site/` に作り、GitHub Pages（`https://tecolicom.github.io/OMC/`）に自動公開する。

**Architecture:** Astro + Tailwind の静的サイト。ビルド時に `../calendar/events/*.yaml`（活動）と `../calendar/sources/blog/*.yaml`（本文・写真）を TypeScript のデータ層が読み込み url で結合する。写真は事前取り込みスクリプトで Wix 変換URL（`.jpg` 強制）から web サイズで取得して `src/assets/photos/` にコミットし、Astro が WebP/レスポンシブ最適化する。GitHub Actions で main push 時に自動デプロイ。

**Tech Stack:** Astro 5 / Tailwind CSS v4 (`@tailwindcss/vite`) / TypeScript / `yaml` / vitest / Node 22 / GitHub Actions (`actions/deploy-pages`)。

## Global Constraints

- サイトは **`site/`** 配下。既存 `calendar/`（Python 道具・データ）は**読むだけ**で変更しない。
- 公開先 `https://tecolicom.github.io/OMC/`。Astro: `site: 'https://tecolicom.github.io'`, `base: '/OMC'`。内部リンク/画像は base を尊重する。
- データは `../calendar/events/<year>/*.yaml`（活動）と `../calendar/sources/blog/*.yaml`（記事）。**結合キーは記事 `url`**。
- 活動の本文表示は、events 側に無い報告本文も含めるため **archive 側の `body` を正**とする。
- 写真取得URL: `https://static.wixstatic.com/media/<id>/v1/fit/w_1600,h_1600,q_80/photo.jpg`（**出力を .jpg 強制**＝約400〜600KB）。元（巨大原本）は使わない。
- 写真ローカル名は media-id を安全化した `<safe>.jpg`（`~`/`.`/`/` を `_` 等に）。取得済みはスキップ（冪等）。
- 見た目: アースカラー・写真ファースト・スマホ最優先。重い JS は使わない。
- 日本語 UTF-8。`site/` のテストは vitest（`cd site && npm test`）。Python 側 `make test` に影響させない。
- 作業ルート: `/Users/utashiro/Git/tecolicom/OMC`。

---

## File Structure

- `site/package.json`, `site/astro.config.mjs`, `site/tsconfig.json`, `site/vitest.config.ts` — 設定
- `site/src/styles/global.css` — Tailwind 読み込み + デザイントークン
- `site/src/data/activities.ts` — データ層（読込・結合・slug・写真名・フィルタ）。テスト対象
- `site/src/data/activities.test.ts` — データ層テスト
- `site/scripts/fetch-photos.mjs` — 写真取り込み（Wix 変換URL → `src/assets/photos/`）
- `site/src/assets/photos/<safe>.jpg` — 取り込んだ写真（コミット）
- `site/src/layouts/Base.astro` — 共通レイアウト（nav/footer）
- `site/src/components/{Hero,ActivityCard,PhotoGrid,CategoryFilter}.astro` — 部品
- `site/src/lib/photos.ts` — 写真 media-id → ローカル ImageMetadata 解決（glob）
- `site/src/pages/{index,about}.astro`, `site/src/pages/activities/{index,[slug]}.astro` — ページ
- `.github/workflows/deploy-site.yml` — Pages 自動公開
- `Makefile` — `site-photos` / `site-dev` / `site-build` ターゲット追加

---

### Task 1: Astro 雛形（`site/`）と Pages 向け設定

**Files:**
- Create: `site/package.json`, `site/astro.config.mjs`, `site/tsconfig.json`, `site/src/styles/global.css`, `site/src/pages/index.astro`, `site/.gitignore`

**Interfaces:**
- Produces: `npm run build` が通る Astro プロジェクト（base=/OMC）。後続タスクが `src/` 配下に追加する土台。

- [ ] **Step 1: Astro プロジェクトを作成**

Run:
```bash
cd /Users/utashiro/Git/tecolicom/OMC
mkdir -p site && cd site
npm create astro@latest . -- --template minimal --no-install --no-git --skip-houston --typescript strict
npm install
npm install -D @tailwindcss/vite tailwindcss yaml vitest
```
（対話が出たら最小テンプレート・TypeScript strict・依存は後で、を選ぶ。`.` に作る）

- [ ] **Step 2: `astro.config.mjs` を設定**（base=/OMC, Tailwind v4 の Vite プラグイン）

```js
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://tecolicom.github.io',
  base: '/OMC',
  trailingSlash: 'always',
  vite: { plugins: [tailwindcss()] },
});
```

- [ ] **Step 3: `src/styles/global.css`（Tailwind + デザイントークン）**

```css
@import "tailwindcss";

@theme {
  --color-tsuchi: #6b4f3a;   /* 土 */
  --color-wakaba: #4f7a3a;   /* 若葉 */
  --color-sora:  #3a6b7a;    /* 空 */
  --color-cream: #f7f4ee;    /* 背景 */
  --color-sumi:  #2b2622;    /* 文字 */
  --font-sans: "Noto Sans JP", system-ui, sans-serif;
}

html { font-family: var(--font-sans); color: var(--color-sumi); background: var(--color-cream); }
```

- [ ] **Step 4: 仮トップ `src/pages/index.astro`**

```astro
---
import '../styles/global.css';
---
<html lang="ja">
  <head><meta charset="utf-8" /><meta name="viewport" content="width=device-width" />
    <title>奥武蔵マウンテンバイク友の会</title></head>
  <body>
    <main class="mx-auto max-w-3xl px-4 py-12">
      <h1 class="text-4xl font-bold text-[var(--color-wakaba)]">奥武蔵マウンテンバイク友の会</h1>
      <p class="mt-4">準備中。</p>
    </main>
  </body>
</html>
```

- [ ] **Step 5: `site/.gitignore`**

```
node_modules/
dist/
.astro/
```

- [ ] **Step 6: ビルド確認 + commit**

Run: `cd site && npm run build`
Expected: `dist/` が生成されエラーなし（`/OMC/` 基準の出力）。
```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add site/package.json site/package-lock.json site/astro.config.mjs site/tsconfig.json site/src site/.gitignore
git commit -m "feat(site): Astro 雛形 + Tailwind + Pages向けbase設定"
```

---

### Task 2: データ層（events × archive 結合）

**Files:**
- Create: `site/src/data/activities.ts`, `site/src/data/activities.test.ts`, `site/vitest.config.ts`

**Interfaces:**
- Produces:
  - `mediaId(url: string): string | null` — wixstatic URL から `/media/<id>` の `<id>` を返す。
  - `photoFilename(url: string): string` — media-id を安全化した `<safe>.jpg`（`~`・`.`・`/`・`,` → `_`、末尾 `.jpg`）。
  - `slugForDate(date: string, uid: string): string` — `YYYY-MM-DD-<uid前6桁>`。
  - `buildActivities(events: EventRecord[], archive: Map<string, ArchiveArticle>): Activity[]` — 純関数。
  - `getActivities(calendarDir: string): Activity[]` — `<dir>/events/**` と `<dir>/sources/blog/*.yaml` を読み込み結合（昇順 date）。
  - 型 `Activity = { date, category, title, slug, articles: {kind,title,url,published,body,images:string[]}[], photos: string[] }`（`photos` は `photoFilename` 済みの一覧、重複排除）。

- [ ] **Step 1: `vitest.config.ts`**

```ts
import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { include: ['src/**/*.test.ts'] } });
```

- [ ] **Step 2: 失敗テストを書く** (`src/data/activities.test.ts`)

```ts
import { describe, it, expect } from 'vitest';
import { mediaId, photoFilename, slugForDate, buildActivities } from './activities';

describe('helpers', () => {
  it('mediaId/photoFilename', () => {
    const u = 'https://static.wixstatic.com/media/c3395c_ab12~mv2.jpg';
    expect(mediaId(u)).toBe('c3395c_ab12~mv2.jpg');
    expect(photoFilename(u)).toBe('c3395c_ab12_mv2_jpg.jpg');
  });
  it('slugForDate', () => {
    expect(slugForDate('2025-05-18', 'a971950d2962')).toBe('2025-05-18-a97195');
  });
});

describe('buildActivities', () => {
  it('joins events with archive by url and aggregates photos', () => {
    const events = [{
      date: '2025-05-18', category: '里山整備', summary: '飯能市里山清掃活動',
      uid: 'abc123def456',
      source: { posts: [
        { kind: 'report', url: 'https://x/r', title: '報告', published: '2025-05-18' },
        { kind: 'announce', url: 'https://x/a', title: 'お知らせ', published: '2025-05-08' },
      ] },
    }];
    const archive = new Map([
      ['https://x/r', { url: 'https://x/r', title: '報告', published: '2025-05-18',
        body: '実施しました', images: ['https://static.wixstatic.com/media/c3395c_p~mv2.jpg'] }],
      ['https://x/a', { url: 'https://x/a', title: 'お知らせ', published: '2025-05-08',
        body: '9時集合', images: [] }],
    ]);
    const acts = buildActivities(events as any, archive as any);
    expect(acts).toHaveLength(1);
    const a = acts[0];
    expect(a.title).toBe('飯能市里山清掃活動');
    expect(a.slug).toBe('2025-05-18-abc123');
    // 報告の本文も archive から入る
    expect(a.articles.find(x => x.kind === 'report')!.body).toBe('実施しました');
    expect(a.photos).toEqual(['c3395c_p_mv2_jpg.jpg']);
  });
});
```

- [ ] **Step 3: 失敗確認**

Run: `cd site && npx vitest run src/data/activities.test.ts`
Expected: FAIL（モジュール無し）。

- [ ] **Step 4: 実装** (`src/data/activities.ts`)

```ts
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'yaml';

export type Article = { kind: string; title: string; url: string; published: string; body: string; images: string[] };
export type Activity = { date: string; category: string; title: string; slug: string; articles: Article[]; photos: string[] };
export type EventRecord = { date: string; category: string; summary: string; uid: string;
  source: { posts: { kind: string; url: string; title: string; published: string }[] } };
export type ArchiveArticle = { url: string; title: string; published: string; body?: string; images?: string[] };

export function mediaId(url: string): string | null {
  const m = url.match(/\/media\/([^/]+)/);
  return m ? m[1] : null;
}
export function photoFilename(url: string): string {
  const id = mediaId(url) ?? url;
  return id.replace(/[~./,]/g, '_') + '.jpg';
}
export function slugForDate(date: string, uid: string): string {
  return `${date}-${(uid || '').slice(0, 6)}`;
}

export function buildActivities(events: EventRecord[], archive: Map<string, ArchiveArticle>): Activity[] {
  const acts = events.map((ev) => {
    const articles: Article[] = (ev.source?.posts ?? []).map((p) => {
      const a = archive.get(p.url);
      return { kind: p.kind, title: a?.title ?? p.title, url: p.url,
        published: a?.published ?? p.published, body: (a?.body ?? '').trim(),
        images: a?.images ?? [] };
    });
    const seen = new Set<string>();
    const photos: string[] = [];
    for (const art of articles) for (const u of art.images) {
      const f = photoFilename(u);
      if (!seen.has(f)) { seen.add(f); photos.push(f); }
    }
    return { date: ev.date, category: ev.category, title: ev.summary,
      slug: slugForDate(ev.date, ev.uid), articles, photos };
  });
  acts.sort((a, b) => a.date.localeCompare(b.date));
  return acts;
}

function readYamlDir(dir: string): any[] {
  return readdirSync(dir).filter((f) => f.endsWith('.yaml'))
    .map((f) => parse(readFileSync(join(dir, f), 'utf8')));
}

export function getActivities(calendarDir: string): Activity[] {
  const eventsRoot = join(calendarDir, 'events');
  const events: EventRecord[] = readdirSync(eventsRoot)
    .filter((y) => /^\d{4}$/.test(y))
    .flatMap((y) => readYamlDir(join(eventsRoot, y)));
  const archive = new Map<string, ArchiveArticle>();
  for (const a of readYamlDir(join(calendarDir, 'sources', 'blog'))) {
    if (a && a.url) archive.set(a.url, a);
  }
  return buildActivities(events, archive);
}
```

- [ ] **Step 5: 成功確認 + commit**

Run: `cd site && npx vitest run src/data/activities.test.ts`
Expected: テスト PASS。（実データ 145 活動の読み込みは Task 5 のビルドで検証する。）
```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add site/src/data site/vitest.config.ts
git commit -m "feat(site): データ層 (events×archive 結合, 写真名, slug) + テスト"
```

---

### Task 3: 写真取り込みスクリプト + 実行

**Files:**
- Create: `site/scripts/fetch-photos.mjs`
- Modify: `Makefile`（`site-photos` 追加）
- Create: `site/src/assets/photos/*.jpg`（取り込み物・コミット）

**Interfaces:**
- Consumes: `../calendar/sources/blog/*.yaml` の `images`/`cover`、`src/data/activities.ts` の `photoFilename`/`mediaId`。
- Produces: `src/assets/photos/<safe>.jpg`（web サイズ JPEG）。

- [ ] **Step 1: `site/scripts/fetch-photos.mjs`**

```js
// ブログ記事の写真を Wix 変換URL(.jpg強制, web サイズ) で取り込み src/assets/photos/ に保存。
// 既にあるものはスキップ（冪等）。失敗はスキップしてログ。
import { readFileSync, readdirSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'yaml';

// activities.ts と同じロジック（.ts を import しないよう .mjs 内に複製）。
const mediaId = (url) => { const m = url.match(/\/media\/([^/]+)/); return m ? m[1] : null; };
const photoFilename = (url) => (mediaId(url) ?? url).replace(/[~./,]/g, '_') + '.jpg';

const here = dirname(fileURLToPath(import.meta.url));
const blogDir = join(here, '..', '..', 'calendar', 'sources', 'blog');
const outDir = join(here, '..', 'src', 'assets', 'photos');
mkdirSync(outDir, { recursive: true });

const urls = new Map(); // photoFilename -> 取得用URL
for (const f of readdirSync(blogDir).filter((x) => x.endsWith('.yaml'))) {
  const d = parse(readFileSync(join(blogDir, f), 'utf8'));
  if (!d) continue;
  for (const u of [...(d.images || []), ...(d.cover ? [d.cover] : [])]) {
    const id = mediaId(u);
    if (!id) continue;
    const file = photoFilename(u);
    const fetchUrl = `https://static.wixstatic.com/media/${id}/v1/fit/w_1600,h_1600,q_80/photo.jpg`;
    if (!urls.has(file)) urls.set(file, fetchUrl);
  }
}

let ok = 0, skip = 0, fail = 0;
for (const [file, url] of urls) {
  const out = join(outDir, file);
  if (existsSync(out)) { skip++; continue; }
  try {
    const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const buf = Buffer.from(await res.arrayBuffer());
    writeFileSync(out, buf);
    ok++;
    if (ok % 50 === 0) console.log(`  ${ok} 取得...`);
    await new Promise((r) => setTimeout(r, 150));
  } catch (e) { fail++; console.warn('skip', file, String(e)); }
}
console.log(`total=${urls.size} fetched=${ok} skipped(existing)=${skip} failed=${fail}`);
```

- [ ] **Step 2: `Makefile` に `site-photos` を追加**（ルート Makefile の末尾に）

```make
site-photos: ## サイト用に写真を取り込む（不足分のみ）
	cd site && node scripts/fetch-photos.mjs
```

- [ ] **Step 3: 実行（写真取り込み）**

Run:
```bash
cd /Users/utashiro/Git/tecolicom/OMC
make site-photos
ls site/src/assets/photos/*.jpg | wc -l    # 数百枚（最大928）期待
du -sh site/src/assets/photos               # 数百MB 目安
```
失敗が多少出てもスキップして継続する。極端に失敗が多い場合は STOP して報告。

- [ ] **Step 4: 取り込んだ写真をコミット**（`.gitignore` で無視されないこと確認）

```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add site/scripts/fetch-photos.mjs Makefile site/src/assets/photos
git commit -m "feat(site): 写真取り込みスクリプト + 取り込んだ写真をコミット"
```

---

### Task 4: 写真解決ヘルパ + 共通レイアウト + 部品

**Files:**
- Create: `site/src/lib/photos.ts`, `site/src/layouts/Base.astro`, `site/src/components/{ActivityCard,PhotoGrid}.astro`

**Interfaces:**
- Produces:
  - `getPhoto(filename: string): ImageMetadata | undefined` — `src/assets/photos/*.jpg` を glob し、ファイル名で引く。
  - `Base.astro`（props `title`, `description?`）— nav（トップ/活動/写真/会について）と footer を含む共通レイアウト。
  - `ActivityCard.astro`（props `activity`）、`PhotoGrid.astro`（props `filenames: string[]`、`<Image>` で最適化表示）。

- [ ] **Step 1: `src/lib/photos.ts`**

```ts
import type { ImageMetadata } from 'astro';
const mods = import.meta.glob<{ default: ImageMetadata }>('../assets/photos/*.jpg', { eager: true });
const byName = new Map<string, ImageMetadata>();
for (const [path, mod] of Object.entries(mods)) {
  byName.set(path.split('/').pop()!, mod.default);
}
export function getPhoto(filename: string): ImageMetadata | undefined { return byName.get(filename); }
export function hasPhoto(filename: string): boolean { return byName.has(filename); }
```

- [ ] **Step 2: `src/layouts/Base.astro`**

```astro
---
import '../styles/global.css';
const { title, description } = Astro.props;
const base = import.meta.env.BASE_URL;
const nav = [
  { href: base, label: 'トップ' },
  { href: base + 'activities/', label: '活動' },
  { href: base + 'about/', label: '会について' },
];
// 注: 写真ギャラリー(gallery/)は Phase B で追加するため、Phase A の nav には入れない。
---
<html lang="ja">
  <head>
    <meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    {description && <meta name="description" content={description} />}
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet" />
  </head>
  <body class="min-h-screen flex flex-col">
    <header class="sticky top-0 z-20 bg-[var(--color-cream)]/90 backdrop-blur border-b border-black/5">
      <nav class="mx-auto max-w-5xl px-4 py-3 flex items-center gap-4 text-sm">
        <a href={base} class="font-bold text-[var(--color-wakaba)] no-underline">奥武蔵MTB友の会</a>
        <span class="flex-1"></span>
        {nav.map((n) => <a href={n.href} class="no-underline text-[var(--color-sumi)]/80 hover:text-[var(--color-wakaba)]">{n.label}</a>)}
      </nav>
    </header>
    <main class="flex-1"><slot /></main>
    <footer class="mt-16 border-t border-black/5 py-8 text-center text-sm text-[var(--color-sumi)]/60">
      奥武蔵マウンテンバイク友の会 ·
      <a href="https://okumusashimtb.wixsite.com/omcweb" class="text-[var(--color-wakaba)]">公式ブログ</a>
    </footer>
  </body>
</html>
```

- [ ] **Step 3: `src/components/PhotoGrid.astro`**

```astro
---
import { Image } from 'astro:assets';
import { getPhoto } from '../lib/photos';
const { filenames } = Astro.props;
const photos = (filenames ?? []).map(getPhoto).filter(Boolean);
---
{photos.length > 0 && (
  <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
    {photos.map((p) => (
      <Image src={p} alt="" widths={[300, 600]} sizes="(max-width:640px) 50vw, 300px"
             class="w-full aspect-square object-cover rounded-lg" loading="lazy" />
    ))}
  </div>
)}
```

- [ ] **Step 4: `src/components/ActivityCard.astro`**

```astro
---
import { Image } from 'astro:assets';
import { getPhoto } from '../lib/photos';
const { activity } = Astro.props;
const base = import.meta.env.BASE_URL;
const cover = activity.photos.map(getPhoto).find(Boolean);
const d = activity.date;
---
<a href={`${base}activities/${activity.slug}/`}
   class="group block rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition no-underline">
  <div class="aspect-[4/3] bg-[var(--color-cream)] overflow-hidden">
    {cover && <Image src={cover} alt="" widths={[400, 800]} sizes="(max-width:640px) 100vw, 400px"
                     class="w-full h-full object-cover group-hover:scale-105 transition" loading="lazy" />}
  </div>
  <div class="p-3">
    <div class="text-xs text-[var(--color-sumi)]/50">{d} · {activity.category}</div>
    <div class="font-bold text-[var(--color-sumi)] mt-1">{activity.title}</div>
  </div>
</a>
```

- [ ] **Step 5: ビルド確認 + commit**

Run: `cd site && npm run build`（部品は未使用でもビルドが通ること）
Expected: エラーなし。
```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add site/src/lib site/src/layouts site/src/components
git commit -m "feat(site): 共通レイアウト + 写真解決 + ActivityCard/PhotoGrid"
```

---

### Task 5: ページ（トップ / 活動一覧 / 活動詳細 / 会について）

**Files:**
- Modify: `site/src/pages/index.astro`
- Create: `site/src/pages/activities/index.astro`, `site/src/pages/activities/[slug].astro`, `site/src/pages/about.astro`

**Interfaces:**
- Consumes: `getActivities('../calendar')`、`Base.astro`、`ActivityCard`、`PhotoGrid`、`getPhoto`。

- [ ] **Step 1: トップ `src/pages/index.astro`**

```astro
---
import Base from '../layouts/Base.astro';
import ActivityCard from '../components/ActivityCard.astro';
import { Image } from 'astro:assets';
import { getActivities } from '../data/activities';
import { getPhoto } from '../lib/photos';
const acts = getActivities('../calendar');
const recent = [...acts].reverse().slice(0, 6);
const hero = [...acts].reverse().flatMap((a) => a.photos).map(getPhoto).find(Boolean);
const base = import.meta.env.BASE_URL;
---
<Base title="奥武蔵マウンテンバイク友の会" description="飯能・奥武蔵エリアで里山整備やトレイル整備、清掃、子ども自転車教室などを行うマウンテンバイク愛好家の会。">
  <section class="relative">
    {hero && <Image src={hero} alt="" widths={[800,1600]} sizes="100vw" class="w-full h-[60vh] object-cover" />}
    <div class="absolute inset-0 bg-black/35 flex items-center">
      <div class="mx-auto max-w-5xl px-4 text-white">
        <h1 class="text-4xl sm:text-6xl font-bold drop-shadow">奥武蔵マウンテンバイク友の会</h1>
        <p class="mt-3 text-lg drop-shadow">里山を整え、自転車で楽しむ。飯能・奥武蔵の有志の会です。</p>
      </div>
    </div>
  </section>
  <section class="mx-auto max-w-5xl px-4 py-12">
    <div class="flex items-baseline justify-between mb-4">
      <h2 class="text-2xl font-bold">最近の活動</h2>
      <a href={`${base}activities/`} class="text-sm text-[var(--color-wakaba)]">すべて見る →</a>
    </div>
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {recent.map((a) => <ActivityCard activity={a} />)}
    </div>
  </section>
</Base>
```

- [ ] **Step 2: 活動一覧 `src/pages/activities/index.astro`**（年別 + 種別フィルタ。フィルタは軽量 JS）

```astro
---
import Base from '../../layouts/Base.astro';
import ActivityCard from '../../components/ActivityCard.astro';
import { getActivities } from '../../data/activities';
const acts = [...getActivities('../calendar')].reverse();
const cats = Array.from(new Set(acts.map((a) => a.category)));
const years = Array.from(new Set(acts.map((a) => a.date.slice(0, 4))));
---
<Base title="活動アーカイブ | 奥武蔵MTB友の会">
  <section class="mx-auto max-w-5xl px-4 py-10">
    <h1 class="text-3xl font-bold mb-4">活動アーカイブ</h1>
    <div class="flex flex-wrap gap-2 mb-6" id="filters">
      <button data-cat="" class="cat-btn px-3 py-1 rounded-full border text-sm bg-[var(--color-wakaba)] text-white">すべて</button>
      {cats.map((c) => <button data-cat={c} class="cat-btn px-3 py-1 rounded-full border text-sm">{c}</button>)}
    </div>
    {years.map((y) => (
      <div class="mb-10 year-block" data-year={y}>
        <h2 class="text-xl font-bold text-[var(--color-tsuchi)] mb-3">{y}年</h2>
        <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {acts.filter((a) => a.date.startsWith(y)).map((a) => (
            <div class="act-item" data-cat={a.category}><ActivityCard activity={a} /></div>
          ))}
        </div>
      </div>
    ))}
  </section>
  <script is:inline>
    const btns = document.querySelectorAll('.cat-btn');
    btns.forEach((b) => b.addEventListener('click', () => {
      const cat = b.getAttribute('data-cat');
      btns.forEach((x) => { x.classList.remove('bg-[var(--color-wakaba)]','text-white'); });
      b.classList.add('bg-[var(--color-wakaba)]','text-white');
      document.querySelectorAll('.act-item').forEach((it) => {
        it.style.display = (!cat || it.getAttribute('data-cat') === cat) ? '' : 'none';
      });
      document.querySelectorAll('.year-block').forEach((yb) => {
        const any = [...yb.querySelectorAll('.act-item')].some((it) => it.style.display !== 'none');
        yb.style.display = any ? '' : 'none';
      });
    }));
  </script>
</Base>
```

- [ ] **Step 3: 活動詳細 `src/pages/activities/[slug].astro`**

```astro
---
import Base from '../../layouts/Base.astro';
import PhotoGrid from '../../components/PhotoGrid.astro';
import { getActivities } from '../../data/activities';
export function getStaticPaths() {
  return getActivities('../calendar').map((a) => ({ params: { slug: a.slug }, props: { activity: a } }));
}
const { activity } = Astro.props;
const label = { announce: '📣 お知らせ', report: '📝 報告', other: '🔗 記事' };
---
<Base title={`${activity.title} | 奥武蔵MTB友の会`}>
  <article class="mx-auto max-w-3xl px-4 py-10">
    <div class="text-sm text-[var(--color-sumi)]/50">{activity.date} · {activity.category}</div>
    <h1 class="text-3xl font-bold mt-1 mb-6">{activity.title}</h1>
    {activity.photos.length > 0 && <div class="mb-8"><PhotoGrid filenames={activity.photos} /></div>}
    {activity.articles.map((art) => (
      <section class="mb-8">
        <h2 class="text-base font-bold text-[var(--color-tsuchi)] mb-2">{label[art.kind] ?? '🔗 記事'}</h2>
        {art.body && <p class="whitespace-pre-line leading-relaxed">{art.body}</p>}
        <a href={art.url} class="inline-block mt-2 text-sm text-[var(--color-wakaba)]">元の記事を見る →</a>
      </section>
    ))}
    <a href={`${import.meta.env.BASE_URL}activities/`} class="text-sm text-[var(--color-wakaba)]">← 活動アーカイブ</a>
  </article>
</Base>
```

- [ ] **Step 4: 会について `src/pages/about.astro`**

```astro
---
import Base from '../layouts/Base.astro';
---
<Base title="会について | 奥武蔵MTB友の会">
  <section class="mx-auto max-w-3xl px-4 py-10 prose-like">
    <h1 class="text-3xl font-bold mb-4">奥武蔵マウンテンバイク友の会について</h1>
    <p class="leading-relaxed">飯能・奥武蔵エリアを中心に、里山整備・トレイル整備・清掃活動・子ども自転車教室などを行う
      マウンテンバイク愛好家の有志の会です。自分たちが楽しませてもらっている里山に恩返しをしながら、
      地域の皆さんと協働しています。</p>
    <h2 class="text-xl font-bold mt-8 mb-2">活動エリア</h2>
    <p>飯能市・日高市・秩父市・青梅市 ほか（奥武蔵周辺）</p>
    <h2 class="text-xl font-bold mt-8 mb-2">参加・お問い合わせ</h2>
    <p><a href="https://okumusashimtb.wixsite.com/omcweb" class="text-[var(--color-wakaba)]">公式ブログ</a>
      よりお問い合わせください。</p>
  </section>
</Base>
```

- [ ] **Step 5: ビルド確認 + commit**

Run:
```bash
cd site && npm run build
ls dist/activities | head        # 各活動の詳細ページが生成される
```
Expected: 145 活動分の詳細ページ + 一覧/トップ/about が生成、エラーなし。
ローカル確認: `npm run preview`（`http://localhost:4321/OMC/`）でトップ・一覧・詳細・写真表示を目視。
```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add site/src/pages
git commit -m "feat(site): トップ/活動一覧(種別フィルタ)/活動詳細/会について"
```

---

### Task 6: GitHub Actions で Pages 自動公開 + OMC を public 化

**Files:**
- Create: `.github/workflows/deploy-site.yml`
- Modify: `Makefile`（`site-dev`/`site-build` 追加・任意）

**Interfaces:**
- Produces: main への push で `site/` をビルドし Pages へ公開。公開URL `https://tecolicom.github.io/OMC/`。

- [ ] **Step 1: ワークフロー `.github/workflows/deploy-site.yml`**

```yaml
name: Deploy site to Pages
on:
  push:
    branches: [main]
    paths: ['site/**', 'calendar/events/**', 'calendar/sources/blog/**', '.github/workflows/deploy-site.yml']
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: 'npm', cache-dependency-path: site/package-lock.json }
      - run: npm ci
        working-directory: site
      - run: npm run build
        working-directory: site
      - uses: actions/upload-pages-artifact@v3
        with: { path: site/dist }
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: `Makefile` に開発用ターゲット追加（任意）**

```make
site-dev: ## サイトをローカルで開発表示
	cd site && npm run dev

site-build: ## サイトをビルド
	cd site && npm run build
```

- [ ] **Step 3: commit + push（ワークフローを反映）**

```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add .github/workflows/deploy-site.yml Makefile
git commit -m "ci(site): GitHub Pages 自動デプロイ"
git push
```

- [ ] **Step 4: OMC を public 化 + Pages 設定**（人手・1回）

Run:
```bash
gh repo edit tecolicom/OMC --visibility public --accept-visibility-change-consequences
gh api -X POST repos/tecolicom/OMC/pages -f build_type=workflow 2>/dev/null || true
```
（Pages のソースを「GitHub Actions」に設定。既に設定済みならエラーは無視。GitHub の Settings → Pages でも確認可。）

- [ ] **Step 5: デプロイ確認**

Run:
```bash
gh run list --workflow=deploy-site.yml -L 1
```
Actions が成功したら `https://tecolicom.github.io/OMC/` を開き、トップ・活動一覧・活動詳細・写真・スマホ表示を確認。

---

## このプランの完了条件
- `cd site && npm run build` がローカルで通る。`npx vitest run` 全 PASS。
- 写真が `site/src/assets/photos/` に取り込まれコミットされている。
- GitHub Actions が成功し、`https://tecolicom.github.io/OMC/` でサイトが表示される（トップ・活動アーカイブ・活動詳細・会について・写真）。

## 後続（Phase B・対象外）
- 写真ギャラリーページ（ライトボックス）、カレンダー今後の予定（ICS）、デザイン磨き込み（frontend-design）、独自ドメイン。
