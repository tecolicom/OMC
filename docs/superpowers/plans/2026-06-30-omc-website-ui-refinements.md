# OMC サイト UI 改善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 写真なしイベントに OMC ロゴのデフォルトカバーを付け、詳細ページで記事ごとに写真を分離表示し、記事を時系列順に並べる。

**Architecture:** データ層 `activities.ts` で記事を published 昇順にソートし記事ごとの写真リストを生成、`ActivityCard` がカバー写真欠落時にロゴへフォールバック、`[slug].astro` が各記事セクション内に写真を出す。

**Tech Stack:** Astro 7, Tailwind v4, vitest, Node 22.22.2 (nodenv)

## Global Constraints

- Node は nodenv 管理、`.node-version` = 22.22.2（Astro 7 は ≥22.12 必須）。
- base path は `/OMC`（`astro.config.mjs` 設定済み、変更しない）。
- 画像は Astro `astro:assets` の `Image` で最適化する（WebP 化）。
- テスト実行: `cd site && npx vitest run`。
- 写真ファイル名変換は既存 `photoFilename(url)` を使う（`/media/<id>` 抽出 → `[~./,]` を `_` に置換 + `.jpg`）。
- 作業ブランチ: website-phaseA。コミットは小刻みに。

---

### Task 1: データ層 — 記事の時系列ソート + 記事ごとの写真リスト

**Files:**
- Modify: `site/src/data/activities.ts`
- Test: `site/src/data/activities.test.ts`

**Interfaces:**
- Consumes: 既存 `photoFilename(url: string): string`、`buildActivities(events, archive): Activity[]`
- Produces:
  - `Article` 型に `photos: string[]` を追加（記事の `images` を `photoFilename` 変換し記事内で重複排除した順序付きリスト）。
  - `buildActivities` の各 `Activity.articles` は `published` 昇順（安定ソート）。
  - `Activity.photos`（横断 dedup・カバー判定用）は従来どおり。ソート後の記事順で走査して生成する。

- [ ] **Step 1: 失敗するテストを書く**

`site/src/data/activities.test.ts` の `describe('buildActivities', ...)` 内、既存 `it(...)` の後に追記:

```ts
  it('sorts articles by published ascending and derives per-article photos', () => {
    const events = [{
      date: '2024-05-26', category: '清掃活動', summary: '日高市ごみゼロの日清掃作業',
      uid: 'a1b2c3d4e5f6',
      source: { posts: [
        { kind: 'report', url: 'https://x/r', title: '報告', published: '2024-05-29' },
        { kind: 'announce', url: 'https://x/a', title: 'お知らせ', published: '2024-05-13' },
      ] },
    }];
    const archive = new Map([
      ['https://x/r', { url: 'https://x/r', title: '報告', published: '2024-05-29',
        body: '実施', images: [
          'https://static.wixstatic.com/media/c3395c_p1~mv2.jpg',
          'https://static.wixstatic.com/media/c3395c_p1~mv2.jpg', // 重複
          'https://static.wixstatic.com/media/c3395c_p2~mv2.jpg',
        ] }],
      ['https://x/a', { url: 'https://x/a', title: 'お知らせ', published: '2024-05-13',
        body: '集合', images: [] }],
    ]);
    const a = buildActivities(events as any, archive as any)[0];
    // 時系列昇順: お知らせ(05-13) → 報告(05-29)
    expect(a.articles.map(x => x.kind)).toEqual(['announce', 'report']);
    // 記事ごとの写真(記事内で重複排除)
    expect(a.articles[0].photos).toEqual([]);
    expect(a.articles[1].photos).toEqual(['c3395c_p1_mv2_jpg.jpg', 'c3395c_p2_mv2_jpg.jpg']);
    // 横断 dedup は維持
    expect(a.photos).toEqual(['c3395c_p1_mv2_jpg.jpg', 'c3395c_p2_mv2_jpg.jpg']);
  });
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `cd site && npx vitest run`
Expected: 新テストが FAIL（`a.articles[0].photos` が undefined / 並び順が報告先）。

- [ ] **Step 3: 実装する**

`site/src/data/activities.ts` の `Article` 型に `photos` を追加:

```ts
export type Article = { kind: string; title: string; url: string; published: string; body: string; images: string[]; photos: string[] };
```

`buildActivities` の記事生成〜返却部分を以下に置き換える:

```ts
export function buildActivities(events: EventRecord[], archive: Map<string, ArchiveArticle>): Activity[] {
  const acts = events.map((ev) => {
    const articles: Article[] = (ev.source?.posts ?? []).map((p) => {
      const a = archive.get(p.url);
      const images = a?.images ?? [];
      const seenA = new Set<string>();
      const photos: string[] = [];
      for (const u of images) {
        const f = photoFilename(u);
        if (!seenA.has(f)) { seenA.add(f); photos.push(f); }
      }
      return { kind: p.kind, title: a?.title ?? p.title, url: p.url,
        published: a?.published ?? p.published, body: (a?.body ?? '').trim(),
        images, photos };
    });
    articles.sort((x, y) => x.published.localeCompare(y.published));
    const seen = new Set<string>();
    const photos: string[] = [];
    for (const art of articles) for (const f of art.photos) {
      if (!seen.has(f)) { seen.add(f); photos.push(f); }
    }
    return { date: ev.date, category: ev.category, title: ev.summary,
      slug: slugForDate(ev.date, ev.uid), articles, photos };
  });
  acts.sort((a, b) => a.date.localeCompare(b.date));
  return acts;
}
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `cd site && npx vitest run`
Expected: PASS（全テスト pass、既存テストも維持）。

- [ ] **Step 5: コミット**

```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add site/src/data/activities.ts site/src/data/activities.test.ts
git commit -m "feat(site): 記事を時系列(published昇順)整列 + 記事ごとの写真リスト"
```

---

### Task 2: OMC ロゴ取り込み + 活動カードのデフォルトカバー

**Files:**
- Create: `site/src/assets/omc-logo.jpg`
- Modify: `site/src/components/ActivityCard.astro`

**Interfaces:**
- Consumes: `Activity.photos`（Task 1）、`getPhoto(filename)` (`site/src/lib/photos.ts`)
- Produces: なし（表示のみ）

- [ ] **Step 1: ロゴ素材を取り込む**

```bash
cd /Users/utashiro/Git/tecolicom/OMC
curl -s -A "Mozilla/5.0" -o site/src/assets/omc-logo.jpg \
  "https://static.wixstatic.com/media/c3395c_58a6ea367ffd42b98475ed2951dcfbe0.jpg"
file site/src/assets/omc-logo.jpg
```

Expected: `JPEG image data ... 269x271`。

- [ ] **Step 2: ActivityCard を修正する**

`site/src/components/ActivityCard.astro` を以下に置き換える:

```astro
---
import { Image } from 'astro:assets';
import { getPhoto } from '../lib/photos';
import omcLogo from '../assets/omc-logo.jpg';
const { activity } = Astro.props;
const base = import.meta.env.BASE_URL;
const cover = activity.photos.map(getPhoto).find(Boolean);
const d = activity.date;
---
<a href={`${base}activities/${activity.slug}/`}
   class="group block rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition no-underline">
  <div class="aspect-[4/3] bg-[var(--color-cream)] overflow-hidden">
    {cover
      ? <Image src={cover} alt="" widths={[400, 800]} sizes="(max-width:640px) 100vw, 400px"
               class="w-full h-full object-cover group-hover:scale-105 transition" loading="lazy" />
      : <Image src={omcLogo} alt="奥武蔵MTB友の会" widths={[200, 269]} sizes="200px"
               class="w-full h-full object-contain p-6" loading="lazy" />}
  </div>
  <div class="p-3">
    <div class="text-xs text-[var(--color-sumi)]/50">{d} · {activity.category}</div>
    <div class="font-bold text-[var(--color-sumi)] mt-1">{activity.title}</div>
  </div>
</a>
```

- [ ] **Step 3: ビルドして成功を確認**

Run: `cd site && npm run build`
Expected: ビルド成功（エラーなし、全ページ生成）。

- [ ] **Step 4: 写真なしカードにロゴが出ることを確認**

Run: `cd /Users/utashiro/Git/tecolicom/OMC && grep -rl 'omc-logo' site/dist/activities/index.html`
Expected: `site/dist/activities/index.html`（ロゴ由来の最適化画像参照が一覧に含まれる）。
補足: dev プレビュー（`make site-dev` → http://localhost:4321/OMC/activities/）で写真なしイベントのカードにロゴが中央表示されることを目視。

- [ ] **Step 5: コミット**

```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add site/src/assets/omc-logo.jpg site/src/components/ActivityCard.astro
git commit -m "feat(site): 写真なしイベントのカバーに OMC ロゴ(object-contain)"
```

---

### Task 3: 詳細ページ — 記事セクション内に写真を分離表示

**Files:**
- Modify: `site/src/pages/activities/[slug].astro`

**Interfaces:**
- Consumes: `Activity.articles`（各 `art.photos`、Task 1）、`PhotoGrid`（`filenames` prop）
- Produces: なし（表示のみ）

- [ ] **Step 1: [slug].astro を修正する**

`site/src/pages/activities/[slug].astro` を以下に置き換える（上部合体グリッドを削除し、各記事セクション内に「写真 → 本文 → 元記事リンク」）:

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
    {activity.articles.map((art) => (
      <section class="mb-8">
        <h2 class="text-base font-bold text-[var(--color-tsuchi)] mb-2">{label[art.kind] ?? '🔗 記事'}</h2>
        {art.photos.length > 0 && <div class="mb-3"><PhotoGrid filenames={art.photos} /></div>}
        {art.body && <p class="whitespace-pre-line leading-relaxed">{art.body}</p>}
        <a href={art.url} class="inline-block mt-2 text-sm text-[var(--color-wakaba)]">元の記事を見る →</a>
      </section>
    ))}
    <a href={`${import.meta.env.BASE_URL}activities/`} class="text-sm text-[var(--color-wakaba)]">← 活動アーカイブ</a>
  </article>
</Base>
```

- [ ] **Step 2: ビルドして成功を確認**

Run: `cd site && npm run build`
Expected: ビルド成功（全 145 活動詳細ページ生成）。

- [ ] **Step 3: 写真が記事別・時系列で出ることを確認**

dev プレビュー（`make site-dev`）で複数記事のある活動を開き、以下を目視:
- お知らせ → 報告 の順に並ぶ（例: http://localhost:4321/OMC/activities/2024-05-26-... ）。
- 各セクション内に「写真 → 本文」の順で、その記事の写真だけが出る。

- [ ] **Step 4: コミット**

```bash
cd /Users/utashiro/Git/tecolicom/OMC
git add "site/src/pages/activities/[slug].astro"
git commit -m "feat(site): 詳細ページで写真を記事別に分離表示(写真→本文)"
```

---

## Self-Review

- **Spec coverage:** (1) デフォルトカバー=Task 2、(2) 写真の記事別分離=Task 3、(3) 時系列整列=Task 1、テスト=Task 1 + 各ビルド確認。全要件にタスクあり。
- **Placeholder scan:** プレースホルダなし（全コード掲載）。
- **Type consistency:** `Article.photos: string[]` を Task 1 で定義し Task 3 で `art.photos` 使用。`PhotoGrid` の `filenames` prop は既存。`getPhoto`/`photoFilename` は既存シグネチャ。一致を確認。
