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
