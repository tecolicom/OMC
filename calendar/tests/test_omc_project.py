import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import omc_project


def test_build_description_announce_body_and_links():
    posts = [
        {"kind": "report", "url": "https://x/r", "title": "5/17里山整備の報告", "published": "2025-05-20"},
        {"kind": "announce", "url": "https://x/a", "title": "5/17里山整備のお知らせ",
         "published": "2025-05-08", "body": "9時集合です。"},
    ]
    d = omc_project.build_description(posts)
    assert d.startswith("9時集合です。")          # お知らせ本文（report 本文は出さない）
    assert "📣 お知らせ: https://x/a" in d
    assert "📝 報告: https://x/r" in d


def test_build_description_marks_cancel_and_truncates():
    posts = [
        {"kind": "announce", "url": "https://x/c", "title": "5/17活動中止のお知らせ",
         "published": "2025-05-16", "body": "あ" * 1500},
    ]
    d = omc_project.build_description(posts, limit=1000)
    assert "…（続きはリンク先で）" in d
    assert "⚠️ 中止: https://x/c" in d


def test_build_description_report_only_no_body():
    posts = [{"kind": "report", "url": "https://x/r", "title": "里山整備の報告",
              "published": "2025-05-20", "body": "本文は出さない"}]
    d = omc_project.build_description(posts)
    assert "本文は出さない" not in d
    assert d.strip().startswith("📝 報告:")
