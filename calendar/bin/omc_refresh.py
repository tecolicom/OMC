"""アーカイブ(sources/blog/*.yaml)の body だけを段落付きに安全更新するロジック。"""
from __future__ import annotations

import glob
import os
import re
import unicodedata

import yaml

import omc_parse


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


def reconcile_body(old_body: str, html: str) -> tuple[str, str]:
    new = omc_parse.extract_post_body(html)
    if _norm(new) != _norm(old_body):
        return old_body, "content-changed"
    if new == old_body:
        return old_body, "unchanged"
    return new, "updated"


def refresh_dir(cache_dir: str, fetch_fn, sleep_fn=lambda: None, limit=None) -> dict:
    summary = {"updated": 0, "unchanged": 0, "content-changed": 0, "error": 0, "files": []}
    paths = sorted(glob.glob(os.path.join(cache_dir, "*.yaml")))
    if limit:
        paths = paths[:limit]
    for path in paths:
        with open(path, encoding="utf-8") as f:
            rec = yaml.safe_load(f)
        url = (rec or {}).get("url")
        try:
            html = fetch_fn(url)
        except Exception as e:  # noqa: BLE001
            summary["error"] += 1
            summary["files"].append((path, "error", f"{type(e).__name__}"))
            continue
        new_body, status = reconcile_body(rec.get("body", ""), html)
        summary[status] += 1
        if status == "updated":
            rec["body"] = new_body
            with open(path, "w", encoding="utf-8") as f:
                f.write(omc_parse.dump_archive_yaml(rec))
        if status in ("content-changed", "error"):
            summary["files"].append((path, status, url))
        sleep_fn()
    return summary
