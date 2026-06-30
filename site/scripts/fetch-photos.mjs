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
