# OMC — 奥武蔵マウンテンバイク友の会 暦体

city.tecoli.com の暦体 `/ideas/okumusashi-mtb/` を管理するデータリポジトリ。

- イベントの正 (source of truth): Google Calendar `okumusashi.mtb@gmail.com`
- canonical データ: `calendar/events/<year>/<MM-DD>_<uid>.yaml`
- 公式サイト (クロール元): https://okumusashimtb.wixsite.com/omcweb

## 構成

- `idea.yaml` — 暦体メタ (city-tecoli の global-ideas.yaml 転記元)
- `calendar/` — クローラと canonical イベント (詳細は calendar/README.md)

## 設計

docs/superpowers/specs/2026-06-22-okumusashi-mtb-calendar-design.md を参照。
