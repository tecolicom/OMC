import os, subprocess, sys, glob, yaml

HERE = os.path.dirname(__file__)
BIN = os.path.join(HERE, "..", "bin", "cal-omc-archive-fetch")
SITEMAP = os.path.join(HERE, "fixtures", "sitemap-sample.xml")
POST_URL = "https://okumusashimtb.wixsite.com/omcweb/post/sample-a"


def _slug(url):
    sys.path.insert(0, os.path.join(HERE, "..", "bin"))
    import omc_parse
    return omc_parse.slugify_post_url(url)


def test_archive_cli_uses_yaml_cache_and_carries_body(tmp_path):
    cache = tmp_path / "cache"; cache.mkdir()
    rec = {
        "url": POST_URL,
        "title": "5/31日高市ごみゼロの日活動報告",
        "published": "2026-06-03",
        "body": "早朝より作業しました。",
        "images": ["https://static.wixstatic.com/media/c3395c_p.jpg"],
    }
    (cache / f"{_slug(POST_URL)}.yaml").write_text(
        yaml.safe_dump(rec, allow_unicode=True, sort_keys=False), encoding="utf-8")
    out = tmp_path / "events"
    r = subprocess.run(
        [sys.executable, BIN, "--sitemap-file", SITEMAP, "--cache-dir", str(cache),
         "--out-dir", str(out), "--review-file", str(tmp_path / "rev.txt"),
         "--fetched", "2026-06-22"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    files = glob.glob(str(out / "2026" / "05-31_*.yaml"))
    assert len(files) == 1
    d = yaml.safe_load(open(files[0], encoding="utf-8"))
    post = d["source"]["posts"][0]
    assert post["kind"] == "report"
    assert "body" not in post                       # 報告は本文なし
    assert post["images"] == ["https://static.wixstatic.com/media/c3395c_p.jpg"]
    assert d["source"]["crawler"] == "cal-omc-archive-fetch"
