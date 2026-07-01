# OMC 維持作業用 Makefile
#
# 使い方:  make help        … できる操作の一覧
#          make update      … ブログから活動記録を更新
#          make calendar    … カレンダー反映の確認(書き込まない)
#          make calendar-apply … カレンダーへ実際に反映
#
# よくある流れ:  make update  →  make calendar(確認)  →  make calendar-apply

PY  := python3
CAL := calendar
FETCHED := $(shell date +%F)

# 年を絞りたいとき:  make calendar-apply YEAR=2025
YEAR ?=
YEAR_OPT := $(if $(YEAR),--year $(YEAR),)

.DEFAULT_GOAL := help
.PHONY: help update fetch dedupe body-refresh calendar calendar-apply test push site-photos site-dev site-build

help: ## できる操作の一覧を表示
	@echo "OMC でできる操作:"
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  make %-16s %s\n", $$1, $$2}'
	@echo ""
	@echo "  年を絞る例:  make calendar-apply YEAR=2025"

update: fetch dedupe ## ブログ全記事から活動記録を更新(+写真の整理)

fetch: ## ブログ全記事を取り込んで活動記録を作る
	cd $(CAL) && $(PY) bin/cal-omc-archive-fetch --fetched $(FETCHED)

body-refresh: ## 既存アーカイブの本文を段落付きに更新(body のみ, events は不変)
	cd $(CAL) && $(PY) bin/cal-omc-body-refresh $(if $(LIMIT),--limit $(LIMIT),)

dedupe: ## 記事の写真から全ページ共通のサムネ(会と無関係)を除く
	cd $(CAL) && $(PY) bin/dedupe-chrome-images sources/blog

calendar: ## Google カレンダーへの反映内容を確認(書き込まない / dry-run)
	cd $(CAL) && $(PY) bin/cal-omc --events-dir events $(YEAR_OPT)

calendar-apply: ## Google カレンダーへ実際に反映する
	cd $(CAL) && $(PY) bin/cal-omc --events-dir events $(YEAR_OPT) --apply

test: ## 動作テストを実行
	cd $(CAL) && $(PY) -m pytest tests/ -q

push: ## 変更を GitHub に送る(コミットは別途 git commit)
	git push

site-photos: ## サイト用に写真を取り込む(不足分のみ)
	cd site && node scripts/fetch-photos.mjs

site-dev: ## サイトをローカルで開発表示
	cd site && npm run dev

site-build: ## サイトをビルド
	cd site && npm run build
