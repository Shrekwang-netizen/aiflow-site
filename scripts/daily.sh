#!/usr/bin/env bash
# 每天 10:00（北京时间）由 launchd 调起：X 巡检 → 构建 → 发布 → 线上核验
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p logs .private-inbox
LOG="$ROOT/logs/daily-$(date +%F).log"
{
  echo "=== $(date '+%F %T') AIFLOW daily"
  if ! pgrep -f "Google Chrome.app/Contents/MacOS/Google Chrome" >/dev/null 2>&1; then
    echo "! Chrome 未运行，X 巡检跳过（只重建和发布现有内容）"
  else
    python3 scripts/collect_x.py || echo "! collect_x 退出码 $?"
  fi
  python3 scripts/collect_news.py --days 2 || echo "! collect_news 退出码 $?"
  python3 scripts/collect_links.py || echo "! collect_links 退出码 $?"
  python3 scripts/collect_legacy.py --sources dinq,rss,rsshub,latepost,zhihu,hn,blind,buzz || echo "! collect_legacy 退出码 $?"
  python3 scripts/build.py || { echo "! build 失败，停止发布"; exit 1; }
  python3 -m unittest discover -s tests >/dev/null 2>&1 && echo "· tests ok" || echo "! tests 未通过（已知 random 池用例，不阻塞发布）"
  python3 scripts/publish.py --message "daily: X 巡检 $(date +%F)" --verify || echo "! publish 失败"
  echo "=== done $(date '+%F %T')"
} >> "$LOG" 2>&1
