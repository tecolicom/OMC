import sys, os, datetime
import datetime as _dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import omc_parse


RSS = """<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title>
<link>https://okumusashimtb.wixsite.com/omcweb/post/a</link>
<guid>guid-a</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item>
<item><title><![CDATA[6/14第13回総会のお知らせ]]></title>
<link>https://okumusashimtb.wixsite.com/omcweb/post/b</link>
<guid>guid-b</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item>
</channel></rss>"""


def test_parse_rss_extracts_items_in_order():
    items = omc_parse.parse_rss(RSS)
    assert len(items) == 2
    assert items[0]["title"] == "6/7 名栗定期作業の報告"
    assert items[0]["guid"] == "guid-a"
    assert items[0]["link"] == "https://okumusashimtb.wixsite.com/omcweb/post/a"
    assert items[0]["pub_date"] == datetime.date(2026, 6, 11)
    assert items[1]["title"] == "6/14第13回総会のお知らせ"


def test_extract_event_date_basic():
    d = omc_parse.extract_event_date("6/7 名栗定期作業の報告", _dt.date(2026, 6, 11))
    assert d == _dt.date(2026, 6, 7)


def test_extract_event_date_no_space():
    d = omc_parse.extract_event_date("1/18日高市道路清掃", _dt.date(2026, 1, 20))
    assert d == _dt.date(2026, 1, 18)


def test_extract_event_date_in_brackets():
    d = omc_parse.extract_event_date("【2/15(日)の活動報告】", _dt.date(2026, 2, 20))
    assert d == _dt.date(2026, 2, 15)


def test_extract_event_date_fullwidth_slash():
    d = omc_parse.extract_event_date("12／28 年末作業の報告", _dt.date(2027, 1, 5))
    # 12 月のイベントを 1 月に報告 → 前年補正
    assert d == _dt.date(2026, 12, 28)


def test_extract_event_date_none():
    d = omc_parse.extract_event_date("【日高市感謝状贈呈式出席の報告】", _dt.date(2026, 2, 28))
    assert d is None


def test_post_kind():
    assert omc_parse.post_kind("6/7 名栗定期作業の報告") == "report"
    assert omc_parse.post_kind("4/19子ども自転車教室を開催しました") == "report"
    assert omc_parse.post_kind("6/14第13回総会のお知らせ") == "announce"
    assert omc_parse.post_kind("4/19子ども自転車教室を開催します") == "announce"


def test_classify_activity():
    assert omc_parse.classify_activity("6/7 名栗定期作業の報告") == "定期作業"
    assert omc_parse.classify_activity("5/17飯能市里山清掃活動の報告") == "里山整備"
    assert omc_parse.classify_activity("5/31日高市ごみゼロの日活動報告") == "清掃活動"
    assert omc_parse.classify_activity("4/19子ども自転車教室を開催します") == "自転車教室"
    assert omc_parse.classify_activity("6/14第13回総会のお知らせ") == "総会"
    assert omc_parse.classify_activity("1/18日高市道路清掃") == "清掃活動"
    assert omc_parse.classify_activity("謎のイベント") == "その他"


def test_clean_summary():
    assert omc_parse.clean_summary("6/7 名栗定期作業の報告") == "名栗定期作業"
    assert omc_parse.clean_summary("6/14第13回総会のお知らせ") == "第13回総会"
    assert omc_parse.clean_summary("4/19子ども自転車教室を開催しました") == "子ども自転車教室"
    assert omc_parse.clean_summary("【2/15(日)の活動報告】") == "活動"
    assert omc_parse.clean_summary("1/18日高市道路清掃") == "日高市道路清掃"


def test_build_events_dedups_announce_and_report():
    items = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title><link>https://x/report</link>
<guid>g1</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item>
<item><title><![CDATA[6/7名栗定期作業のお知らせ]]></title><link>https://x/announce</link>
<guid>g2</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item>
<item><title><![CDATA[6/14第13回総会のお知らせ]]></title><link>https://x/soukai</link>
<guid>g3</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item>
</channel></rss>""")
    events = omc_parse.build_events(items)
    assert len(events) == 2
    e0 = events[0]
    assert e0["date"].isoformat() == "2026-06-07"
    assert e0["summary"] == "名栗定期作業"
    assert e0["category"] == "定期作業"
    assert e0["all_day"] is True
    assert {s["kind"] for s in e0["sources"]} == {"report", "announce"}
    assert events[1]["summary"] == "第13回総会"


def test_build_events_skips_dateless():
    items = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[【日高市感謝状贈呈式出席の報告】]]></title><link>https://x/k</link>
<guid>g</guid><pubDate>Sat, 28 Feb 2026 00:00:00 GMT</pubDate></item>
</channel></rss>""")
    assert omc_parse.build_events(items) == []


def test_build_events_uid_stable_regardless_of_order():
    a = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title><link>https://x/r</link>
<guid>g1</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item></channel></rss>""")
    b = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7名栗定期作業のお知らせ]]></title><link>https://x/a</link>
<guid>g2</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item></channel></rss>""")
    assert omc_parse.build_events(a)[0]["uid"] == omc_parse.build_events(b)[0]["uid"]


def test_build_events_merges_generic_report_with_typed_announce():
    # 同じ 2/15 のイベントが、型付き告知(里山整備) と 汎用報告(活動報告) に分かれている。
    # date ベース dedup で 1 件に統合され、category/summary は型付き側を採る。
    items = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[【2/15(日)の活動報告】]]></title><link>https://x/rep</link>
<guid>g1</guid><pubDate>Fri, 20 Feb 2026 00:00:00 GMT</pubDate></item>
<item><title><![CDATA[2/15里山整備活動のお知らせ]]></title><link>https://x/ann</link>
<guid>g2</guid><pubDate>Sun, 01 Feb 2026 00:00:00 GMT</pubDate></item>
</channel></rss>""")
    events = omc_parse.build_events(items)
    assert len(events) == 1
    e = events[0]
    assert e["date"].isoformat() == "2026-02-15"
    assert e["category"] == "里山整備"
    assert e["summary"] == "里山整備活動"
    assert len(e["sources"]) == 2


def test_build_events_combined_announce_does_not_create_phantom():
    # 複合告知(5/31清掃 ＆ 6/7定期作業) は 5/31 の実報告に吸収され、(5/31,定期作業) の幻を作らない。
    # 6/7 は独自の報告で別イベントになる。
    items = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[5/31日高市ごみゼロの日活動報告]]></title><link>https://x/r531</link>
<guid>g1</guid><pubDate>Wed, 03 Jun 2026 00:00:00 GMT</pubDate></item>
<item><title><![CDATA[5/31日高市清掃作業＆6/7名栗定期作業のお知らせ]]></title><link>https://x/a</link>
<guid>g2</guid><pubDate>Sat, 16 May 2026 00:00:00 GMT</pubDate></item>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title><link>https://x/r67</link>
<guid>g3</guid><pubDate>Thu, 11 Jun 2026 00:00:00 GMT</pubDate></item>
</channel></rss>""")
    events = omc_parse.build_events(items)
    dates = [e["date"].isoformat() for e in events]
    assert dates == ["2026-05-31", "2026-06-07"]
    e531 = events[0]
    assert e531["category"] == "清掃活動"
    assert e531["summary"] == "日高市ごみゼロの日活動"
    assert len(e531["sources"]) == 2  # 報告 + 複合告知
    assert events[1]["category"] == "定期作業"


def test_build_events_all_other_uses_report_summary():
    items = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[3/15(日)の新規地域の活動報告]]></title><link>https://x/r</link>
<guid>g1</guid><pubDate>Fri, 20 Mar 2026 00:00:00 GMT</pubDate></item>
<item><title><![CDATA[3/15(日) 新規活動地域の初回活動のお知らせ]]></title><link>https://x/a</link>
<guid>g2</guid><pubDate>Fri, 06 Mar 2026 00:00:00 GMT</pubDate></item>
</channel></rss>""")
    events = omc_parse.build_events(items)
    assert len(events) == 1
    assert events[0]["category"] == "その他"
    assert events[0]["summary"] == "新規地域の活動"  # report 優先


def test_classify_activity_archive_vocab():
    assert omc_parse.classify_activity("7月20日-里山道整備活動のご案内") == "里山整備"
    assert omc_parse.classify_activity("鳩山道普請の報告") == "里山整備"
    assert omc_parse.classify_activity("6月2日じてんしゃ広場定期作業のお知らせ") == "定期作業"
    assert omc_parse.classify_activity("12月14日-土-の里山整備活動＆ライドの報告") == "里山整備"
    assert omc_parse.classify_activity("新春ライドのお知らせ") == "ライド"


def test_clean_summary_archive():
    assert omc_parse.clean_summary("7月20日-里山整備活動のご案内") == "里山整備活動"
    assert omc_parse.clean_summary("桜並木の整備（２月１６日）") == "桜並木の整備"
    assert omc_parse.clean_summary("12月21日（日）の活動報告") == "活動"


def test_extract_event_date_kanji_md():
    assert omc_parse.extract_event_date("12月21日（日）の活動報告", _dt.date(2025, 12, 23)) == _dt.date(2025, 12, 21)
    assert omc_parse.extract_event_date("7月20日-里山整備活動のご案内", _dt.date(2024, 7, 10)) == _dt.date(2024, 7, 20)


def test_extract_event_date_fullwidth_kanji():
    # 全角「２月１６日」(NFKC で半角化して抽出)
    assert omc_parse.extract_event_date("桜並木の整備（２月１６日）", _dt.date(2017, 2, 1)) == _dt.date(2017, 2, 16)


def test_extract_event_date_hyphen():
    assert omc_parse.extract_event_date("9-15-里山整備活動のお知らせ", _dt.date(2024, 9, 10)) == _dt.date(2024, 9, 15)
    assert omc_parse.extract_event_date("8-4（日）名栗じてんしゃ広場定期作業のお知らせ", _dt.date(2024, 8, 1)) == _dt.date(2024, 8, 4)


def test_extract_event_date_prefers_kanji_over_other_digits():
    # 「第12回」等の数字に引っ張られず、月日を取る
    assert omc_parse.extract_event_date("第12回総会 11月3日 開催報告", _dt.date(2023, 11, 5)) == _dt.date(2023, 11, 3)


def test_extract_event_date_kanji_year_correction():
    # 12 月のイベントを 1 月に報告 → 前年
    assert omc_parse.extract_event_date("12月28日 年末作業の報告", _dt.date(2027, 1, 5)) == _dt.date(2026, 12, 28)


def test_extract_post_meta_recent():
    html = open(os.path.join(os.path.dirname(__file__), "fixtures", "post-recent.html"),
                encoding="utf-8").read()
    meta = omc_parse.extract_post_meta(html)
    assert meta["title"] == "5/31日高市ごみゼロの日活動報告"
    assert meta["pub_date"] == _dt.date(2026, 6, 3)


def test_extract_post_meta_old():
    html = open(os.path.join(os.path.dirname(__file__), "fixtures", "post-old.html"),
                encoding="utf-8").read()
    meta = omc_parse.extract_post_meta(html)
    assert meta["title"] == "桜並木の整備（２月１６日）"
    assert meta["pub_date"] == _dt.date(2017, 2, 1)


def test_extract_post_meta_none():
    assert omc_parse.extract_post_meta("<html><body>no json-ld</body></html>") is None


def test_parse_sitemap_returns_post_locs_in_order():
    xml = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://okumusashimtb.wixsite.com/omcweb/post/5-31a</loc><lastmod>2026-06-03</lastmod></url>
<url><loc>https://okumusashimtb.wixsite.com/omcweb/post/2017/02/01/b</loc><lastmod>2017-02-01</lastmod></url>
<url><loc>https://okumusashimtb.wixsite.com/omcweb/about-us</loc></url>
</urlset>"""
    locs = omc_parse.parse_sitemap(xml)
    assert locs == [
        "https://okumusashimtb.wixsite.com/omcweb/post/5-31a",
        "https://okumusashimtb.wixsite.com/omcweb/post/2017/02/01/b",
    ]


def test_event_to_yaml_dict_and_filename():
    items = omc_parse.parse_rss("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title><link>https://x/report</link>
<guid>g1</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item>
<item><title><![CDATA[6/7名栗定期作業のお知らせ]]></title><link>https://x/announce</link>
<guid>g2</guid><pubDate>Fri, 05 Jun 2026 00:49:28 GMT</pubDate></item>
</channel></rss>""")
    e = omc_parse.build_events(items)[0]
    d = omc_parse.event_to_yaml_dict(e, _dt.date(2026, 6, 22))
    assert d["summary"] == "名栗定期作業"
    assert d["date"] == "2026-06-07"
    assert d["all_day"] is True
    assert d["category"] == "定期作業"
    assert "出典: https://x/report" in d["description"]
    assert d["source"]["type"] == "omc-blog"
    assert d["source"]["fetched"] == "2026-06-22"
    assert len(d["source"]["posts"]) == 2
    assert omc_parse.event_filename(e) == "2026/06-07_%s.yaml" % e["uid"]
