# AIFLOW

Live site: https://shrekwang-netizen.github.io/aiflow-site/

GitHub Pages serves this `gh-pages` branch directly. It contains the published HTML, shared CSS/JavaScript, and the random-week data; there is no build step or package dependency.

## Preview

Run `python3 -m http.server 8766 --bind 127.0.0.1` from this directory, then open http://127.0.0.1:8766/.

Reader controls combine keyword, event type, saved and unread filters. Lists reveal 24 records at a time. Existing `aiflow-theme`, `aiflow-favs` and `aiflow-read` browser storage keys are preserved. No account or server-side tracking is used for these controls.

## Updating content

Keep `assets/app.js`, `assets/style.css`, and the early `assets/theme.js` include when regenerating pages. HTML uses relative asset paths and an asset version query string; update the version when shared assets change.

The original content generator is not in this repository. A full replacement deployment from that generator must incorporate these reader and template changes first, or it will overwrite them. The 2026-11-02 reader update is tracked in this branch for comparison and recovery.

## Verification

- `node --check assets/app.js` and `node --check assets/theme.js`
- Check local links across root pages and `item/`, `daily/`, `weekly/`, `company/`, `tags/`.
- Exercise combined filters, favorites, unread on/off, empty states, disclosure controls and loading more records.
- Check narrow mobile screens, both themes, and random-week links.
