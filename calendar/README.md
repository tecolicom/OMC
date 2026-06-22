# calendar/

Wix ブログの活動履歴 → canonical YAML → Google Calendar 投影 のパイプライン。

- `bin/cal-omc-blog-fetch` — Wix ブログ RSS クローラ (events YAML 生成)
- `bin/omc_parse.py` — 解析ロジック (テスト対象)
- `events/<year>/<MM-DD>_<uid>.yaml` — canonical イベント (`source:` 付き = クローラ管理)
- `tests/` — 単体 + ゴールデン回帰テスト

## 使い方

    python3 bin/cal-omc-blog-fetch          # RSS を取得し events/ を更新
    python3 -m pytest tests/                 # テスト

`source:` を持たない手動イベントはクローラが触らない。
