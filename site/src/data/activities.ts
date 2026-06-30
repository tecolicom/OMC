import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'yaml';

export type Article = { kind: string; title: string; url: string; published: string; body: string; images: string[]; photos: string[] };
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
