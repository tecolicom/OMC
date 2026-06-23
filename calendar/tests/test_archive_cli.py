import os, subprocess, sys, glob, hashlib

HERE = os.path.dirname(__file__)
BIN = os.path.join(HERE, "..", "bin", "cal-omc-archive-fetch")
SITEMAP = os.path.join(HERE, "fixtures", "sitemap-sample.xml")
POST_URL = "https://okumusashimtb.wixsite.com/omcweb/post/sample-a"
LDJSON = ('<script type="application/ld+json">'
          '{"@type":"BlogPosting","headline":"5/31日高市ごみゼロの日活動報告",'
          '"datePublished":"2026-06-03T02:08:16.709Z"}</script>')


def test_archive_cli_uses_cache_and_writes_event(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    key = hashlib.sha1(POST_URL.encode("utf-8")).hexdigest()
    (cache / f"{key}.html").write_text(LDJSON, encoding="utf-8")
    out = tmp_path / "events"
    review = tmp_path / "review.txt"
    r = subprocess.run(
        [sys.executable, BIN, "--sitemap-file", SITEMAP, "--cache-dir", str(cache),
         "--out-dir", str(out), "--review-file", str(review), "--fetched", "2026-06-22"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    files = glob.glob(str(out / "2026" / "05-31_*.yaml"))
    assert len(files) == 1
    body = open(files[0], encoding="utf-8").read()
    assert "summary: 日高市ごみゼロの日活動" in body
    assert "type: omc-blog" in body
