import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import omc_refresh  # noqa: E402
import yaml  # noqa: E402

PD = ('<div data-hook="post-description">'
      '<p><span>あ。</span></p><p><span>い。</span></p><p><span>う。</span></p></div>'
      '<footer><p>© 2019 by Okumusashi MTB Club. Proudly created with Wix.com</p></footer>')


def test_reconcile_body_updated_when_content_matches():
    # 旧body は同じ内容の1行、HTML は段落あり → 改行を足して更新
    new, status = omc_refresh.reconcile_body("あ。い。う。", PD)
    assert status == "updated"
    assert new == "あ。\nい。\nう。"


def test_reconcile_body_content_changed_is_not_overwritten():
    new, status = omc_refresh.reconcile_body("まったく別の本文", PD)
    assert status == "content-changed"
    assert new == "まったく別の本文"  # 旧を保持(上書きしない)


def test_reconcile_body_unchanged_when_already_equal():
    new, status = omc_refresh.reconcile_body("あ。\nい。\nう。", PD)
    assert status == "unchanged"
    assert new == "あ。\nい。\nう。"                    # 旧body(=同一)を返す


def test_refresh_dir_updates_only_body(tmp_path):
    p = tmp_path / "post-x.yaml"
    p.write_text(yaml.safe_dump(
        {"url": "https://x/post/x", "title": "T", "published": "2023-09-10",
         "body": "あ。い。う。", "images": ["https://static.wixstatic.com/media/z.jpg"]},
        allow_unicode=True, sort_keys=False), encoding="utf-8")
    summary = omc_refresh.refresh_dir(str(tmp_path), fetch_fn=lambda url: PD, sleep_fn=lambda: None)
    assert summary["updated"] == 1
    rec = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert rec["body"] == "あ。\nい。\nう。"      # 改行が入った
    assert rec["title"] == "T"                     # 他フィールドは保持
    assert rec["published"] == "2023-09-10"          # published も保持
    assert rec["images"] == ["https://static.wixstatic.com/media/z.jpg"]


def test_refresh_dir_counts_fetch_errors(tmp_path):
    p = tmp_path / "post-e.yaml"
    p.write_text(yaml.safe_dump(
        {"url": "https://x/post/e", "title": "T", "published": "2023-09-10",
         "body": "あ。い。う。"}, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def bad_fetch(url):
        raise IOError("timeout")

    summary = omc_refresh.refresh_dir(str(tmp_path), fetch_fn=bad_fetch, sleep_fn=lambda: None)
    assert summary["error"] == 1
    assert summary["updated"] == 0
    # 取得失敗時はファイルを書き換えない
    assert yaml.safe_load(p.read_text(encoding="utf-8"))["body"] == "あ。い。う。"
