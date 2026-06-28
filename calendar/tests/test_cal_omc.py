import os, sys, importlib.util, importlib.machinery

HERE = os.path.dirname(__file__)
BIN = os.path.join(HERE, "..", "bin", "cal-omc")


def _load_cli():
    loader = importlib.machinery.SourceFileLoader("cal_omc", BIN)
    spec = importlib.util.spec_from_loader("cal_omc", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.join(HERE, "..", "bin"))
    spec.loader.exec_module(mod)
    return mod


def test_plan_events_decides_per_date():
    cli = _load_cli()
    events = [
        {"summary": "里山整備活動", "date": "2025-05-17", "uid": "u1", "category": "里山整備",
         "source": {"posts": [{"kind": "announce", "url": "https://x/a", "title": "お知らせ",
                               "published": "2025-05-08", "body": "9時集合"}]}},
        {"summary": "名栗定期作業", "date": "2025-06-01", "uid": "u2", "category": "定期作業",
         "source": {"posts": [{"kind": "report", "url": "https://x/r", "title": "報告", "published": "2025-06-02"}]}},
    ]
    # u1 の日には我々イベントが既存、u2 の日には何も無い
    def fetch_existing(date):
        if date == "2025-05-17":
            return [{"iCalUID": "omc-u1@okumusashi-mtb", "id": "e1",
                     "summary": "里山整備活動", "description": "9時集合\n\n📣 お知らせ: https://x/a"}]
        return []
    plan = cli.plan_events(events, fetch_existing)
    by_uid = {p["event"]["uid"]: p for p in plan}
    assert by_uid["u1"]["action"] == "update_ours"
    assert by_uid["u1"]["needs_update"] is False     # 同内容 → 更新不要
    assert by_uid["u2"]["action"] == "create"
