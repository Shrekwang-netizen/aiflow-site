# AIFLOW · AI talent observatory

**Live:** https://shrekwang-netizen.github.io/aiflow-site/

An editorial site for AI talent moves, hiring and organization changes. GitHub Pages publishes the `gh-pages` branch. The repository now contains both the content source and a reproducible static generator; no framework, package install, paid API or separate application server is required.

## Source of truth

- `data/records.json`: all historical and reviewed records, explicit evidence state and review notes.
- `data/x-watchlist.json`: 18 verified public X profiles and their monitoring focus.
- `data/monitor.json`, `data/run-history.json`: actual inspection coverage and run outcomes.
- `scripts/build.py`: produces every HTML page, RSS, and random archive. Preserve existing record IDs.
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

## Scheduled publishing

The local Codex heartbeat **AIFLOW 每日人才巡检** (`aiflow`) is active daily at **10:00 Asia/Shanghai**, attached to the owner’s existing task. It reads `docs/daily-update.md`, checks public X profiles and concrete sources, updates reviewed records, rebuilds/tests, pushes `gh-pages`, and verifies the deployment. Keep the computer on and Codex running. Access failures must be reported as incomplete coverage, not silently counted as successful checks.

Only `primary` / `reported` records with `scope: talent` enter the homepage, weekly report, RSS and random archive. Historical data remain discoverable with clear status. There is no synthetic AI score or unmeasured popularity ranking. Dates reflect the original public source, not the day a record was fetched.

Do not deploy an older external generator over this branch: it would replace the design and publication rules. All routine updates should now edit the data and run this repository’s generator.

## Design references

The source hierarchy of [Techmeme](https://www.techmeme.com/) and the person-first organization of [AI Scout](https://talent.dinq.me/) informed the layout. AIFLOW uses its own warm paper / forest green visual system, typography, templates and copy; no third-party logos, article bodies or screenshots are copied into the site.
