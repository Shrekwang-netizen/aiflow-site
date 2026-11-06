#!/usr/bin/env python3
"""Collect all sources, publish coverage, retain candidates for manual review."""
from __future__ import annotations
import argparse
import fcntl
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from publish import gh
from schedule_config import SCHEDULE

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.private-inbox'
TZ = ZoneInfo('Asia/Shanghai')


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    temporary.replace(path)


def collection_days(now, previous):
    last = datetime.fromisoformat(previous['checked_at']) if previous.get('checked_at') else now
    if last.tzinfo is None:
        last = last.replace(tzinfo=TZ)
    return max(4, math.ceil((now - last).total_seconds() / 86400) + 2)


def commands(days):
    return [
        ('x', [sys.executable, 'scripts/collect_x.py']),
        ('news', [sys.executable, 'scripts/collect_news.py', '--days', str(days)]),
        ('links', [sys.executable, 'scripts/collect_links.py']),
        ('legacy', [sys.executable, 'scripts/collect_legacy.py', '--days', str(max(7, days)),
                    '--sources', 'dinq,rss,rsshub,latepost,zhihu,hn,blind,buzz']),
    ]


def summarize_source(name, payload, returncode, warnings):
    row = {'source': name, 'status': 'partial' if returncode or warnings else 'read',
           'exit_code': returncode, 'warnings': warnings, 'candidates': 0}
    if payload is None:
        row['status'] = 'empty' if name == 'links' and returncode == 0 else 'failed'
        return row
    if name == 'x':
        row['candidates'] = sum(len(a.get('candidates', [])) for a in payload.get('accounts', []))
        row['accounts_read'] = len(payload.get('accounts', []))
        row['failures'] = payload.get('failures', [])
        row['status'] = 'partial'
    else:
        row['candidates'] = len(payload.get('items', []))
        row['failures'] = payload.get('failures', [])
        row['details'] = payload.get('coverage', [])
        if row['failures'] or any(c.get('error') or c.get('warnings') for c in row['details']):
            row['status'] = 'partial'
    return row


def build_and_publish(head, now):
    for command in ([sys.executable, 'scripts/build.py'],
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                    ['node', '--check', 'assets/app.js'], ['node', '--check', 'assets/theme.js'],
                    [sys.executable, 'scripts/publish.py', '--expected-head', head,
                     '--message', f'daily: 多源巡检 {now:%Y-%m-%d}（候选待核）', '--verify']):
        subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    now = datetime.now(TZ)
    previous = load(ROOT / 'data/monitor.json', {})
    planned = commands(collection_days(now, previous))
    if args.dry_run:
        print(SCHEDULE)
        print('Weekend:', now.weekday() >= 5)
        for name, command in planned:
            print(name, command)
        print('Review: manual; build and tests must pass before publication.')
        return 0
    if now.weekday() >= 5:
        print('周末不运行；下个工作日补扫。')
        return 0
    PRIVATE.mkdir(exist_ok=True)
    with (PRIVATE / 'daily.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('已有扫描在运行，跳过重复启动。')
            return 0
        head = gh('GET', 'repos/Shrekwang-netizen/aiflow-site/git/ref/heads/gh-pages')['object']['sha']
        published = PRIVATE / 'published-head'
        if published.exists() and published.read_text().strip() != head:
            raise RuntimeError('远端有其他更新，需先同步本地文件后再发布。')
        coverage = []
        x_payload = None
        for name, command in planned:
            started = datetime.now(TZ).timestamp()
            print('→', name, flush=True)
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, timeout=1800)
                output, code = result.stdout, result.returncode
            except subprocess.TimeoutExpired as exc:
                output = exc.stdout or b''
                if isinstance(output, bytes):
                    output = output.decode('utf-8', 'replace')
                output += '\n! 采集超时，覆盖不完整'
                code = 124
            print(output, flush=True)
            files = sorted((p for p in PRIVATE.glob(f'{name}-20*.json')
                            if p.stat().st_mtime >= started), key=lambda p: p.stat().st_mtime)
            payload = load(files[-1], None) if files else None
            warnings = [line.strip()[:300] for line in output.splitlines()
                        if line.strip().startswith(('!', '✗'))]
            coverage.append(summarize_source(name, payload, code, warnings))
            if name == 'x':
                x_payload = payload
        monitor = load(ROOT / 'data/monitor.json', {})
        if x_payload is None:
            accounts = load(ROOT / 'data/x-watchlist.json', {})['accounts']
            monitor.update(accounts_checked=[], accounts_failed=[a['handle'] for a in accounts if a.get('enabled', True)], posts_read=0)
        total = sum(c['candidates'] for c in coverage)
        gaps = [c['source'] for c in coverage if c['status'] in ('partial', 'failed')]
        monitor.update(checked_at=now.isoformat(timespec='seconds'), mode='scheduled-scan',
                       schedule=SCHEDULE, automation_enabled=True, editorial_mode='manual',
                       source_coverage=coverage, new_records=0, reviewed_records=0,
                       review_status='pending' if total else 'no-candidates',
                       summary=f'已依次运行 X、媒体、手动链接、DINQ/RSSHub/HN/Blind 等采集，共 {total} 条候选（跨源未去重），待人工核查；本轮未新增新闻。'
                               + (f'有限窗口或访问缺口：{", ".join(gaps)}。' if gaps else '')
                               + '来源读取成功不代表完整覆盖。')
        write(ROOT / 'data/monitor.json', monitor)
        history = load(ROOT / 'data/run-history.json', [])
        if x_payload and history and history[0].get('checked_at') == x_payload.get('generated_at'):
            history.pop(0)
        history.insert(0, monitor.copy())
        write(ROOT / 'data/run-history.json', history[:90])
        build_and_publish(head, now)
        print('巡检状态已发布；新候选仍需核查后入库。', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
