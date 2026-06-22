import os, subprocess, sys, glob

BIN = os.path.join(os.path.dirname(__file__), "..", "bin", "cal-omc-blog-fetch")
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "feed-min.xml")


def _write_fixture():
    os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
    with open(FIXTURE, "w", encoding="utf-8") as f:
        f.write("""<?xml version="1.0"?><rss><channel>
<item><title><![CDATA[6/7 名栗定期作業の報告]]></title><link>https://x/r</link>
<guid>g1</guid><pubDate>Thu, 11 Jun 2026 10:44:12 GMT</pubDate></item>
</channel></rss>""")


def test_cli_writes_event_yaml(tmp_path):
    _write_fixture()
    out = tmp_path / "events"
    r = subprocess.run(
        [sys.executable, BIN, "--feed-file", FIXTURE, "--out-dir", str(out),
         "--fetched", "2026-06-22"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    files = glob.glob(str(out / "2026" / "06-07_*.yaml"))
    assert len(files) == 1
    body = open(files[0], encoding="utf-8").read()
    assert "summary: 名栗定期作業" in body
    assert "type: omc-blog" in body
