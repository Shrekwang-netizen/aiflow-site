#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旧架构采集源接入（新架构）

复用 scripts/legacy_sources.py 里已经验证过的采集函数：
DINQ / RSS / RSSHub / LatePost / 知乎热榜 / Hacker News / Blind / 360 索引。
只把候选写进 .private-inbox/legacy-<时间戳>.json 与 .md，不写 records.json、
不自动上站；公开引用前仍需回原文核对（规则见 docs/daily-update.md）。

    python3 scripts/collect_legacy.py
    python3 scripts/collect_legacy.py --sources dinq,rss,hn
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = ROOT / ".private-inbox"
TZ_CN = timezone(timedelta(hours=8))


def log(msg: str) -> None:
    print(msg, flush=True)


def load_legacy():
    path = ROOT / "scripts" / "legacy_sources.py"
    spec = importlib.util.spec_from_file_location("legacy_sources", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # 把旧脚本的写盘点改到 .private-inbox，避免污染新架构
    module.DATA = PRIVATE
    module.INBOX = PRIVATE / "legacy-inbox.json"
    module.ITEMS = PRIVATE / "legacy-items.json"
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="dinq,rss,rsshub,latepost,zhihu,hn,blind,buzz")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--blind-channels", type=int, default=3)
    parser.add_argument("--buzz-queries", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    wanted = [s.strip() for s in args.sources.split(",") if s.strip()]

    PRIVATE.mkdir(exist_ok=True)
    m = load_legacy()
    items: list[dict] = []
    coverage = []

    runners = {
        "dinq": lambda: m.cand_from_dinq(m.parse_dinq(m.fetch(m.DINQ_URL))),
        "rss": m.cand_from_rss,
        "rsshub": m.cand_from_rsshub,
        "latepost": m.cand_from_latepost,
        "zhihu": m.cand_from_zhihu,
        "hn": lambda: m.cand_from_hn(days=args.days),
        "blind": lambda: m.cand_from_blind(limit_channels=args.blind_channels, cursor=0),
        "buzz": lambda: m.cand_from_buzz(limit_queries=args.buzz_queries, cursor=0),
    }

    for name in wanted:
        fn = runners.get(name)
        if fn is None:
            continue
        started = time.time()
        try:
            got = fn() or []
            items.extend(got)
            coverage.append({"source": name, "count": len(got), "error": None,
                             "seconds": round(time.time() - started, 1)})
            log(f"✓ {name}: {len(got)} 条候选（{round(time.time() - started, 1)}s）")
        except Exception as exc:  # noqa: BLE001
            coverage.append({"source": name, "count": 0, "error": str(exc)[:160],
                             "seconds": round(time.time() - started, 1)})
            log(f"✗ {name}: {exc}")

    # 只保留 7 天内（没有日期的保留）
    cutoff = (datetime.now(TZ_CN) - timedelta(days=args.days)).date().isoformat()
    items = [it for it in items if not it.get("date") or (it.get("date") or "") >= cutoff]

    # 去重（URL + 标题）
    seen, unique = set(), []
    for it in items:
        url = ((it.get("source") or {}).get("url") or "").strip()
        if it.get("origin") == "talent.dinq.me":
            key = f"{it.get('date')}|{it.get('title')}|{(it.get('person') or {}).get('name')}"
        else:
            key = url or (it.get("title") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(it)

    stamp = datetime.now(TZ_CN).strftime("%Y-%m-%d-%H%M")
    log(f"\n共 {len(unique)} 条候选（去重后），来源 {len(coverage)} 个")
    for c in unique[:12]:
        log(f"  · {c.get('date')} [{c.get('origin')}] {c.get('title','')[:70]}")

    if args.dry_run:
        return 0
    payload = {"generated_at": datetime.now(TZ_CN).isoformat(timespec="seconds"),
               "coverage": coverage, "items": unique}
    (PRIVATE / f"legacy-{stamp}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# 旧采集源候选 · {stamp}", ""]
    for c in coverage:
        lines.append(f"- {c['source']}: {c['count']} 条" + (f"（失败：{c['error']}）" if c["error"] else ""))
    lines.append("")
    for it in unique:
        lines += [f"## [{it.get('origin')}] {it.get('title','')}",
                  f"{it.get('date')} · {((it.get('source') or {}).get('url') or '')}",
                  (it.get("summary") or "")[:300], ""]
    (PRIVATE / f"legacy-{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"→ .private-inbox/legacy-{stamp}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
