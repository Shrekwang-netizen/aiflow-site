#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按远端编辑规范检查 records.json 的写法，只报告不修改。

规范（见 docs/daily-update.md）：
  摘要 60–140 字；标题 ≤ 32 字；tags 2–3 个方向词；
  sources 用「媒体 · 记者/栏目」；checked 记录必须有 review_note。
加上 --strict 时，违规会以非零状态退出。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    strict = "--strict" in sys.argv
    records = json.loads((ROOT / "data/records.json").read_text())
    problems: list[str] = []
    for r in records:
        rid = r["id"]
        n = len(r["summary"])
        if n > 140:
            problems.append(f"{rid}: 摘要 {n} 字（>140）")
        elif n < 40:
            problems.append(f"{rid}: 摘要 {n} 字（<40，可能信息不足）")
        if len(r["title"]) > 32:
            problems.append(f"{rid}: 标题 {len(r['title'])} 字（>32）")
        if len(r["tags"]) > 3:
            problems.append(f"{rid}: tags {len(r['tags'])} 个（>3）")
        if r["status"] in ("primary", "reported") and not (r.get("review_note") or "").strip():
            problems.append(f"{rid}: checked 记录缺 review_note")
        for s in r["sources"]:
            if len(s["name"]) > 28:
                problems.append(f"{rid}: 来源名过长「{s['name']}」")
    total = len(records)
    print(f"检查 {total} 条记录，发现 {len(problems)} 处与规范不符")
    for line in problems:
        print("  ·", line)
    return 1 if (strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
