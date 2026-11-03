#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
链接收件箱（新架构）

微信公众号等没有公开 RSS 的独家消息，由人把链接丢进：
  .private-inbox/links.txt     （一行一个 URL，# 开头是注释）

本脚本抓取标题、发布时间和正文，写成：
  .private-inbox/links-<时间戳>.json / .md

只做「把链接变成可读候选」，不写 records.json、不自动上站。

    python3 scripts/collect_links.py
    python3 scripts/collect_links.py --dry-run
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / ".private-inbox"
LINKS = PRIVATE / "links.txt"
TZ_CN = timezone(timedelta(hours=8))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def strip_html(value: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", value or "", flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmllib.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def extract(url: str, page: str) -> dict:
    result = {"url": url, "title": "", "published": "", "text": ""}
    m = re.search(r'var msg_title = "([^"]*)"', page)
    if not m:
        m = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    if not m:
        m = re.search(r"<title>(.*?)</title>", page, re.S | re.I)
    if m:
        result["title"] = htmllib.unescape(m.group(1)).strip()[:200]

    m = re.search(r'var create_time = "(\d{9,})"', page)
    if m:
        result["published"] = datetime.fromtimestamp(int(m.group(1)), TZ_CN).isoformat()
    else:
        m = re.search(r'property="article:published_time" content="([^"]*)"', page)
        if m:
            result["published"] = m.group(1)

    m = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*(?:<script|<div id="js_pc_qr_code")', page, re.S)
    if not m:
        m = re.search(r"<article[^>]*>(.*?)</article>", page, re.S | re.I)
    if not m:
        m = re.search(r"<body[^>]*>(.*?)</body>", page, re.S | re.I)
    if m:
        result["text"] = strip_html(m.group(1))[:4000]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    PRIVATE.mkdir(exist_ok=True)
    if not LINKS.exists():
        LINKS.write_text(
            "# 一行一个链接，脚本会抓标题/时间/正文，产出本地候选。\n"
            "# 例：\n"
            "# https://mp.weixin.qq.com/s/xxxxxxxx\n", encoding="utf-8")
    urls = []
    for line in LINKS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line.startswith("http") and line not in urls:
            urls.append(line)
    if not urls:
        log("链接收件箱为空（.private-inbox/links.txt）")
        return 0

    items, failures = [], []
    for url in urls:
        try:
            page = fetch(url)
            item = extract(url, page)
            if not item["title"]:
                item["title"] = url
            items.append(item)
            log(f"✓ {item['title'][:60]}")
        except Exception as exc:  # noqa: BLE001
            failures.append({"url": url, "reason": str(exc)[:120]})
            log(f"✗ {url}：{exc}")

    stamp = datetime.now(TZ_CN).strftime("%Y-%m-%d-%H%M")
    if args.dry_run:
        return 0
    payload = {"generated_at": datetime.now(TZ_CN).isoformat(timespec="seconds"),
               "items": items, "failures": failures}
    (PRIVATE / f"links-{stamp}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# 链接候选 · {stamp}", ""]
    for item in items:
        lines += [f"## {item['title']}", f"{item['published'] or '时间未知'}", item["url"], "",
                  item["text"][:800], ""]
    if failures:
        lines += ["## 抓取失败"] + [f"- {f['url']}：{f['reason']}" for f in failures]
    (PRIVATE / f"links-{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"→ .private-inbox/links-{stamp}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
