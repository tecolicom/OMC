import os, subprocess, sys, filecmp

HERE = os.path.dirname(__file__)
BIN = os.path.join(HERE, "..", "bin", "cal-omc-blog-fetch")
FIXTURE = os.path.join(HERE, "fixtures", "feed-sample.xml")
GOLDEN = os.path.join(HERE, "golden")


def test_golden_matches(tmp_path):
    out = tmp_path / "events"
    r = subprocess.run(
        [sys.executable, BIN, "--feed-file", FIXTURE, "--out-dir", str(out),
         "--fetched", "2026-06-22"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    expected = []
    for root, _, files in os.walk(GOLDEN):
        for fn in files:
            expected.append(os.path.relpath(os.path.join(root, fn), GOLDEN))
    assert expected, "golden が空"
    for rel in expected:
        got = os.path.join(str(out), rel)
        assert os.path.exists(got), f"未生成: {rel}"
        assert filecmp.cmp(os.path.join(GOLDEN, rel), got, shallow=False), \
            f"差分: {rel}"
