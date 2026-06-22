import sys, os, datetime
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


import datetime as _dt


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
