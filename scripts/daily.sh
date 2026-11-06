#!/usr/bin/env bash
# 周一至周五 09:30：多源采集 → 构建检查 → 发布巡检状态；候选人工核查。
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export TZ=Asia/Shanghai
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p logs .private-inbox
if [[ "${1:-}" == "--dry-run" ]]; then
  exec python3 scripts/daily.py --dry-run
fi
exec python3 -u scripts/daily.py >> "logs/daily-$(date +%F).log" 2>&1
