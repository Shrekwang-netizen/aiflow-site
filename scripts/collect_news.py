#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文/英文 AI 媒体 RSS 采集（新架构）

把公开 RSS 里命中「人事 / 组织」关键词的条目收成候选，写：
  .private-inbox/news-<时间戳>.json / .md   （gitignored，供人/AI 复核）

只做发现，不写 records.json、不自动上站。公开报道需要回原文核对后才进入
data/records.json（见 docs/daily-update.md）。

    python3 scripts/collect_news.py
    python3 scripts/collect_news.py --days 3 --dry-run
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / ".private-inbox"
TZ_CN = timezone(timedelta(hours=8))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

FEEDS = [
    ("OpenAI 官方", "https://openai.com/news/rss.xml"),
    ("量子位", "https://www.qbitai.com/feed"),
    ("雷峰网", "https://www.leiphone.com/feed"),
    ("IT之家", "https://www.ithome.com/rss/"),
    ("钛媒体", "https://www.tmtpost.com/rss.xml"),
    ("极客公园", "https://www.geekpark.net/rss"),
    ("InfoQ 中文", "https://www.infoq.cn/feed"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("TechCrunch Layoffs", "https://techcrunch.com/tag/layoffs/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("Semafor Tech", "https://www.semafor.com/rss/technology.xml"),
]

TALENT_TITLE_RE = re.compile(
    r"离职|辞职|卸任|出走|加入|加盟|入职|跳槽|转投|挖角|挖来|被挖|裁员|缩编|"
    r"解散|重组|组织调整|内部信|全员信|晋升|任命|接管|接任|出任|招聘|扩招|招人|"
    r"\b(depart\w*|resign\w*|quit|leav\w*|join\w*|hir(?:e|es|ed|ing)|poach\w*|layoff\w*|"
    r"laid off|reorg\w*|restructur\w*|step(?:ping)? down|appoint\w*|promot\w*|found\w*)\b",
    re.I,
)


AI_RE = re.compile(
    r"AI|人工智能|大模型|模型|算法|芯片|算力|机器人|具身|智能驾驶|自动驾驶|"
    r"DeepSeek|OpenAI|Anthropic|ChatGPT|Claude|Gemini|Grok|Qwen|Kimi|GLM|MiniMax|"
    r"字节|阿里|腾讯|百度|美团|月之暗面|智谱|商汤|英伟达|NVIDIA|微软|谷歌|Meta|xAI|OpenAI",
    re.I,
)
NOISE_RE = re.compile(r"早报|晚报|日报|周报|快讯|盘点|汇总|直播|发布会|评测|上手|优惠|促销|summit|agenda|conference|webinar|podcast|register|ticket|meetup", re.I)
GENERAL_SOURCES = {"IT之家", "钛媒体"}


def log(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"! {msg}", file=sys.stderr, flush=True)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (403, 429):
            raise
        # 有些站点挡 Python TLS 指纹，退回 curl
        proc = subprocess.run(["curl", "-sL", "--compressed", "--max-time", "30",
                               "-A", UA, url], capture_output=True)
        if proc.returncode != 0 or not proc.stdout:
            raise
        return proc.stdout


def strip_html(value: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", value or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmllib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_feed(raw: bytes):
    root = ET.fromstring(raw)
    items = []
    # RSS 2.0
    for node in root.iter("item"):
        items.append({
            "title": (node.findtext("title") or "").strip(),
            "link": (node.findtext("link") or "").strip(),
            "date": node.findtext("pubDate") or node.findtext("{http://purl.org/dc/elements/1.1/}date") or "",
            "summary": strip_html(node.findtext("description") or ""),
        })
    # Atom
    ns = "{http://www.w3.org/2005/Atom}"
    for node in root.iter(f"{ns}entry"):
        link = node.find(f"{ns}link")
        href = link.get("href") if link is not None else ""
        items.append({
            "title": (node.findtext(f"{ns}title") or "").strip(),
            "link": href.strip(),
            "date": node.findtext(f"{ns}updated") or node.findtext(f"{ns}published") or "",
            "summary": strip_html(node.findtext(f"{ns}summary") or node.findtext(f"{ns}content") or ""),
        })
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    found = []
    failures = []
    for name, url in FEEDS:
        try:
            items = parse_feed(fetch(url))
        except Exception as exc:  # noqa: BLE001
            failures.append({"source": name, "url": url, "reason": str(exc)[:120]})
            log(f"✗ {name}: {exc}")
            continue
        picked = 0
        for item in items:
            dt = parse_date(item["date"])
            if dt is not None and dt < cutoff:
                continue
            title = item["title"]
            blob = title + " " + item["summary"]
            if not TALENT_TITLE_RE.search(title) or NOISE_RE.search(title):
                continue
            if name in GENERAL_SOURCES and not AI_RE.search(blob):
                continue
            if not item["link"]:
                continue
            found.append({
                "source": name,
                "title": item["title"][:160],
                "url": item["link"],
                "published": dt.astimezone(TZ_CN).isoformat() if dt else "",
                "summary": item["summary"][:400],
                "matched": sorted({m.group(0).lower() for m in TALENT_TITLE_RE.finditer(title)})[:5],
            })
            picked += 1
        log(f"✓ {name}: {len(items)} 条，命中 {picked}")
        time.sleep(0.4)

    # 去重
    seen = set()
    unique = []
    for row in found:
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        unique.append(row)
    unique.sort(key=lambda r: r["published"] or "", reverse=True)

    stamp = datetime.now(TZ_CN).strftime("%Y-%m-%d-%H%M")
    log(f"\n共命中 {len(unique)} 条（{args.days} 天内），失败源 {len(failures)} 个")
    for row in unique[:20]:
        log(f"  · {row['published'][:16].replace('T', ' ')} [{row['source']}] {row['title'][:70]}")

    if args.dry_run:
        return 0
    PRIVATE.mkdir(exist_ok=True)
    payload = {"generated_at": datetime.now(TZ_CN).isoformat(timespec="seconds"),
               "days": args.days, "feeds": len(FEEDS), "failures": failures,
               "items": unique}
    (PRIVATE / f"news-{stamp}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# 媒体候选 · {stamp}", "", f"{args.days} 天窗口，命中 {len(unique)} 条；失败源 {len(failures)} 个。", ""]
    for row in unique:
        lines.append(f"- [{row['source']}] {row['title']}")
        lines.append(f"  {row['published'][:16].replace('T', ' ')} · {', '.join(row['matched'])}")
        lines.append(f"  {row['url']}")
    if failures:
        lines += ["", "## 失败源"] + [f"- {f['source']}: {f['reason']}" for f in failures]
    (PRIVATE / f"news-{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"→ .private-inbox/news-{stamp}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
