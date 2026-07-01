import { describe, it, expect } from 'vitest';
import { mediaId, photoFilename, buildActivities } from './activities';

describe('helpers', () => {
  it('mediaId/photoFilename', () => {
    const u = 'https://static.wixstatic.com/media/c3395c_ab12~mv2.jpg';
    expect(mediaId(u)).toBe('c3395c_ab12~mv2.jpg');
    expect(photoFilename(u)).toBe('c3395c_ab12_mv2_jpg.jpg');
  });
});

describe('buildActivities', () => {
  it('joins events with archive by url and aggregates photos', () => {
    const events = [{
      date: '2025-05-18', category: '里山整備', summary: '飯能市里山清掃活動',
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
    expect(a.slug).toBe('2025-05-18');
    // 報告の本文も archive から入る
    expect(a.articles.find(x => x.kind === 'report')!.body).toBe('実施しました');
    expect(a.photos).toEqual(['c3395c_p_mv2_jpg.jpg']);
  });

  it('sorts articles by published ascending and derives per-article photos', () => {
    const events = [{
      date: '2024-05-26', category: '清掃活動', summary: '日高市ごみゼロの日清掃作業',
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

  it('gives date-only slugs and disambiguates same-day events with a numeric suffix', () => {
    const mk = (date: string, summary: string) => ({
      date, category: 'イベント', summary, source: { posts: [] as any[] },
    });
    // 入力順を日付でシャッフルしても、昇順整列後に採番されることを確認
    const events = [mk('2024-06-02', 'A'), mk('2024-05-26', 'C'), mk('2024-06-02', 'B')];
    const acts = buildActivities(events as any, new Map() as any);
    expect(acts.map(a => a.date)).toEqual(['2024-05-26', '2024-06-02', '2024-06-02']);
    // 単独日はそのまま、同日は2件目以降に -2 を付与
    expect(acts.map(a => a.slug)).toEqual(['2024-05-26', '2024-06-02', '2024-06-02-2']);
  });
});
