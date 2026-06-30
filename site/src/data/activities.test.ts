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
