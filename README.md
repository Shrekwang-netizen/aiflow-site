# AIFLOW · AI talent observatory

**Live:** https://shrekwang-netizen.github.io/aiflow-site/

An editorial site for AI talent moves, hiring and organization changes. GitHub Pages publishes the `gh-pages` branch. The repository now contains both the content source and a reproducible static generator; no framework, package install, paid API or separate application server is required.

## Source of truth

- `data/records.json`: all historical and reviewed records, explicit evidence state and review notes.
- `data/x-watchlist.json`: 18 verified public X profiles and their monitoring focus.
- `data/monitor.json`, `data/run-history.json`: actual inspection coverage and run outcomes.
- `scripts/build.py`: produces every HTML page, RSS, and random archive. Preserve existing record IDs.
- `scripts/collect_x.py`, `collect_news.py`, `collect_links.py`, `collect_legacy.py`: automated discovery; output only to `.private-inbox/` for review.
- `scripts/publish.py`, `daily.sh`, `com.aiflow.site.plist`: GitHub API publishing and the 10:00 local schedule.
- `assets/style.css`, `assets/app.js`, `assets/theme.js`: design and accessible reader controls.
- [X watchlist](docs/x-watchlist.md) and [daily publishing procedure](docs/daily-update.md).

## Build and test

```sh
python3 scripts/build.py
python3 -m unittest discover -s tests
node --check assets/app.js
node --check assets/theme.js
git diff --check
python3 -m http.server 8766 --bind 127.0.0.1
```

The site works at the GitHub Pages project prefix and in a local root. Asset versions are derived from source hashes. Tests check source eligibility, duplicate IDs, legacy article preservation, relative links and random-archive exclusions. Browser QA covers combined search/type/evidence/saved/unread filters, pagination, mobile layout, both themes and accessible controls.

## Automated collection

The daily job runs these collectors before building. They only write candidates to `.private-inbox/` (gitignored); a human or AI editor still verifies the original source and updates `data/records.json`:

- **X**: 18 accounts in `data/x-watchlist.json`, via the owner’s logged-in Chrome (AppleScript, background tab; 48h overlap, at most 40 posts/account).
- **Media RSS**: OpenAI official news, 量子位, 雷峰网, IT之家, 钛媒体, 极客公园, InfoQ 中文, TechCrunch AI / Layoffs, The Verge AI.
- **Legacy sources**: Talent.dinq.me, RSSHub (36 氪快讯 / 财新 / 华尔街见闻), 晚点 LatePost, 知乎热榜, Hacker News Algolia, Blind channels, 360 索引（脉脉）.
- **URL inbox**: WeChat public-account links without RSS go in `.private-inbox/links.txt`.

Coverage gaps and failed sources are logged, never counted as “no news”.

## Scheduled publishing

A local launchd job `com.aiflow.site` runs at **10:00 Asia/Shanghai** from `/Users/wz/aiflow-site`: collect X → media → URL inbox → legacy sources → build → publish via GitHub API → verify the live page. Keep the Mac awake, Chrome running, and the Chrome “Allow JavaScript from Apple Events” setting on. The job must run outside Desktop/Documents (macOS TCC blocks background agents there). Failures are recorded in `logs/` and the monitor page must not claim coverage that did not happen.

Only `primary` / `reported` records with `scope: talent` enter the homepage, weekly report, RSS and random archive. Historical data remain discoverable with clear status. There is no synthetic AI score or unmeasured popularity ranking. Dates reflect the original public source, not the day a record was fetched.

Do not deploy an older external generator over this branch: it would replace the design and publication rules. All routine updates should now edit the data and run this repository’s generator.

## Design references

The source hierarchy of [Techmeme](https://www.techmeme.com/) and the person-first organization of [AI Scout](https://talent.dinq.me/) informed the layout. AIFLOW uses its own warm paper / forest green visual system, typography, templates and copy; no third-party logos, article bodies or screenshots are copied into the site.
