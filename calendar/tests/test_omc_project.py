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


import datetime as _dt

def test_build_event_body_allday():
    event = {
        "summary": "里山整備活動", "date": "2025-05-17", "uid": "abc123def456",
        "source": {"posts": [
            {"kind": "report", "url": "https://x/r", "title": "報告", "published": "2025-05-20"},
            {"kind": "announce", "url": "https://x/a", "title": "お知らせ", "published": "2025-05-08", "body": "9時集合"},
        ]},
    }
    b = omc_project.build_event_body(event)
    assert b["summary"] == "里山整備活動"
    assert b["start"] == {"date": "2025-05-17"}
    assert b["end"] == {"date": "2025-05-18"}     # 終日 end は翌日(排他)
    assert b["iCalUID"] == "omc-abc123def456@okumusashi-mtb"
    assert "9時集合" in b["description"]
    assert "📣 お知らせ: https://x/a" in b["description"]


def _ev(summary, uid=None):
    e = {"summary": summary, "id": "eid_" + summary, "start": {"date": "2025-05-17"}}
    if uid: e["iCalUID"] = uid
    return e

EVENT = {"summary": "里山整備活動", "date": "2025-05-17", "uid": "u1", "category": "里山整備",
         "source": {"posts": [{"kind": "announce", "url": "https://x/a", "title": "お知らせ", "published": "2025-05-08", "body": "b"}]}}


def test_decide_create_when_no_existing():
    assert omc_project.decide_action(EVENT, [])["action"] == "create"


def test_decide_update_ours():
    ours = _ev("里山整備活動", uid="omc-u1@okumusashi-mtb")
    r = omc_project.decide_action(EVENT, [ours])
    assert r["action"] == "update_ours" and r["target"] is ours


def test_decide_overwrite_single_manual_consistent():
    manual = _ev("里山整備（自治会）")          # 同系統(里山) → 矛盾しない
    r = omc_project.decide_action(EVENT, [manual])
    assert r["action"] == "overwrite_manual" and r["target"] is manual


def test_decide_skip_when_multiple_manual():
    r = omc_project.decide_action(EVENT, [_ev("A"), _ev("B")])
    assert r["action"] == "skip_review"


def test_decide_skip_when_contradicts():
    r = omc_project.decide_action(EVENT, [_ev("第10回総会")])   # category 別系統
    assert r["action"] == "skip_review"


def test_needs_update():
    body = {"summary": "里山整備活動", "description": "X"}
    assert omc_project.needs_update({"summary": "里山整備活動", "description": "X"}, body) is False
    assert omc_project.needs_update({"summary": "別", "description": "X"}, body) is True


def test_parse_gws_json_skips_prefix():
    out = "Using keyring backend: keyring\n{\"items\": [{\"id\": \"x\"}]}\n"
    assert omc_project.parse_gws_json(out)["items"][0]["id"] == "x"
    assert omc_project.parse_gws_json("[]") == []


def test_needs_update_fields_description_only():
    target = {"summary": "会のタイトル", "description": "古い"}
    body = {"summary": "我々のタイトル", "description": "古い"}
    # description のみ比較 → summary が違っても False
    assert omc_project.needs_update(target, body, fields=("description",)) is False
    # description が違えば True
    body2 = {"summary": "我々", "description": "新しい"}
    assert omc_project.needs_update(target, body2, fields=("description",)) is True
    # 既定(summary+description)は summary 差で True
    assert omc_project.needs_update(target, body) is True
