# AIFLOW daily editorial run

The owner has requested daily review of the public X accounts in `data/x-watchlist.json` and automatic publication of suitable AI talent news to the existing public GitHub Pages site. Work only in `/Users/shrek/Documents/Codex/aiflow-site`, repository `Shrekwang-netizen/aiflow-site`, branch `gh-pages`. This authorizes normal content updates and deployment; it does not authorize sending messages, following accounts, paying for services, changing account permissions, or publishing private information.

## Read and collect

1. Confirm the worktree is clean. Fetch origin and fast-forward `gh-pages`; if local edits or divergent changes exist, preserve them and report the blocker. Never force-push or discard changes.
2. Read `data/records.json`, `data/x-watchlist.json`, `data/monitor.json`, and recent `data/run-history.json`. Use Asia/Shanghai for the run clock; preserve source timestamps independently.
3. Use available supported browser tools to open each enabled account's public profile. Confirm identity again if redirected or renamed. Read original posts using visible page text, never hidden application state or unofficial authenticated scraping. Open relevant posts to read full text, date and canonical `/status/` link. Use web search for discovery and official organization pages or original media reports for corroboration.
4. Cover the interval since the last successful account check, with a 48-hour overlap. On the first run, use 48 hours. A longer outage needs a catch-up window. Read pinned posts by their actual date. Scroll until the requested window is covered or a documented limit/access restriction is reached. Aim for at most 40 recent posts per account; record a `partial` result if the cutoff does not reach the start of the window. Never label a five-post sample as full coverage.
5. If X is unavailable or requires login, do not bypass restrictions or invent access. Search publicly indexed specific posts and corroborating official announcements. Count accounts without readable recent timelines as incomplete. Do not infer absence of news from failed access. Repeated account-wide failure is actionable and should be surfaced to the owner.

## Decide what belongs

- In scope: identified AI researchers, engineers, product or business leaders joining/leaving teams, founding an AI company, explicit team hiring, verified layoffs, organization and reporting-line changes.
- Out of scope: model releases, benchmarks, financing alone, ordinary interviews/events, anonymous sentiment, vague speculation, and personal-life posts.
- A concrete source must support the person, organization, event, and date. Preserve the distinction between publication date and occurrence date. Never invent employer, role, salary, motivation or destination.
- `primary`: read a specific public post or announcement from the person/organization; set `reviewed_at`, `review_note`, and a specific canonical source URL. `reported`: read the original media report and attribute it explicitly. One article is not “multiple reports.”
- Only `primary` or `reported` records with `scope: talent` enter the home page, weekly pages, random archive and RSS. Scores and unmeasured popularity are not editorial evidence.
- Legacy `unreviewed` and `lead` records stay marked until individually rechecked. New unverified/reputationally sensitive rumors do not get automatically published; retain only local notes in `.private-inbox/` if needed, which is gitignored. Do not include private notes or raw full-post copies in a public commit.
- Deduplicate by canonical source URL and by person/company/event. Expand an existing record when a second source describes the same move. Record a correction note for changed claims. Avoid deleting or renaming existing article IDs and URLs.
- Write concise Chinese summaries, normally 60–140 Chinese characters. Paraphrase; do not copy full posts or copyrighted articles. Name the reporting source and preserve uncertainty. No unsupported “why this matters” speculation.

## Build and publish

1. Update `data/records.json` for qualified stories. Do not rewrite site design during a routine run.
2. Update `data/monitor.json` with the actual timezone-aware `checked_at`, the checked/failed account lists, window/cutoff details per account, item counts, and a factual Chinese summary. Keep `automation_enabled: true` while this task is active. Append a compact run to `data/run-history.json`, retaining the latest 90 runs. No new qualifying news is a valid result; the status page may still be updated, without inventing a new article.
3. Run `python3 scripts/build.py`, `python3 -m unittest discover -s tests`, `node --check assets/app.js`, and `git diff --check`. The generator updates all article, archive, company, tag, RSS and random-archive views. Review the staged diff for unrelated changes and unexpected removals.
4. Commit only the intended source data and generated output, then push normally to `origin gh-pages`. The user has authorized publication. Do not push `.private-inbox/`, browser data, credentials or local tools. If the remote moved, rebase only a clean committed task change and rebuild/retest; stop on conflicting content rather than overwriting it.
5. Verify the GitHub Pages deployment for the pushed SHA succeeds. Fetch the actual live new article and monitor page to confirm the expected text. Record/report publishing failure accurately; never say “updated” merely because a commit exists.
6. Notify the owner concisely only when there are meaningful new stories, a correction, deployment failure, or an access issue that needs action. Stay quiet when there is no meaningful change. Link the site and primary sources when reporting additions.

## Runtime

This is a local Codex scheduled task, not an always-on server. The computer must be on, Codex must be running, and GitHub/network/browser access must remain available. No X API token, paid feed, or unattended login setup is assumed.
