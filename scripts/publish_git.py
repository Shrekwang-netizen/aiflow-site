#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 git over SSH 发布 gh-pages（不需要 GitHub token）。

和 publish.py 的发布内容一致：站点与源码，跳过 .git / .private-inbox / logs /
__pycache__ / 浏览器临时文件。差别只在传输方式：

  publish.py     gh api 建 tree/commit，需要 gh 已登录
  publish_git.py 克隆 gh-pages 到 .private-inbox/publish-work，rsync 后 git push

一次性准备：把 ~/.ssh/id_ed25519.pub 加到 GitHub 账号的 SSH keys。

    python3 scripts/publish_git.py --dry-run
    python3 scripts/publish_git.py --message "daily: X 巡检 2026-11-20"
    python3 scripts/publish_git.py --message "..." --verify
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "Shrekwang-netizen/aiflow-site"
WORK = ROOT / ".private-inbox" / "publish-work"
REMOTE = f"git@github.com:{REPO}.git"
SITE = f"https://shrekwang-netizen.github.io/{REPO.split('/')[1]}/"
HEAD_FILE = ROOT / ".private-inbox" / "published-head"
EXCLUDES = [".git/", ".private-inbox/", "logs/", "__pycache__/", ".venv/",
            "node_modules/", ".DS_Store", "*.pyc"]


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise SystemExit(f"命令失败：{' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc


def sync_work(readonly: bool = False) -> None:
    """准备一份干净的 gh-pages 工作副本（dry-run 时用 HTTPS，无需 SSH 权限）。"""
    url = f"https://github.com/{REPO}.git" if readonly else REMOTE
    if not (WORK / ".git").exists():
        WORK.parent.mkdir(parents=True, exist_ok=True)
        log(f"→ 克隆 gh-pages 到 {WORK}")
        run(["git", "clone", "--depth", "1", "-b", "gh-pages", url, str(WORK)])
    elif not readonly:
        run(["git", "remote", "set-url", "origin", REMOTE], cwd=WORK)
        run(["git", "fetch", "--depth", "1", "origin", "gh-pages"], cwd=WORK)
        run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=WORK)


def mirror() -> None:
    """把本地生成物同步到工作副本；远端多余的生成页会被删除（与 publish.py 一致）。"""
    cmd = ["rsync", "-a", "--delete", "--itemize-changes"]
    for pattern in EXCLUDES:
        cmd += ["--exclude", pattern]
    cmd += [str(ROOT) + "/", str(WORK) + "/"]
    proc = run(cmd)
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    log(f"→ rsync 变更 {len(changed)} 项")
    for line in changed[:12]:
        log(f"   {line}")
    if len(changed) > 12:
        log(f"   …另有 {len(changed) - 12} 项")


def commit(message: str) -> str | None:
    run(["git", "add", "-A"], cwd=WORK)
    status = run(["git", "status", "--porcelain"], cwd=WORK).stdout.strip()
    if not status:
        return None
    run(["git", "-c", "user.name=aiflow-bot", "-c", "user.email=aiflow@localhost",
         "commit", "-m", message], cwd=WORK)
    return run(["git", "rev-parse", "HEAD"], cwd=WORK).stdout.strip()


def push() -> None:
    run(["git", "push", "origin", "gh-pages"], cwd=WORK)


def head() -> str:
    out = run(["git", "ls-remote", REMOTE, "refs/heads/gh-pages"]).stdout.strip()
    return out.split()[0] if out else ""


def api(path: str) -> dict:
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{path}",
                                 headers={"Accept": "application/vnd.github+json",
                                          "User-Agent": "aiflow-publish"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read())


def verify(sha: str, marker: str = "") -> bool:
    log(f"→ 核验 Pages 构建 {sha[:8]}")
    for _ in range(20):
        try:
            builds = api("/pages/builds?per_page=5")
            latest = builds[0] if isinstance(builds, list) and builds else {}
            if latest.get("status") == "built" and latest.get("commit", "").startswith(sha[:8]):
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(10)
    for _ in range(12):
        try:
            with urllib.request.urlopen(SITE + "index.html", timeout=25) as resp:
                html = resp.read().decode("utf-8", "replace")
            if not marker or marker in html:
                log("✓ 线上首页可访问" + (f"（含 {marker}）" if marker else ""))
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(10)
    log("! 线上核验超时，稍后再看 Pages 状态")
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", default="content: update site")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--marker", default="", help="核验时要求首页出现的文字")
    args = parser.parse_args()

    sync_work(readonly=args.dry_run)
    mirror()
    if args.dry_run:
        run(["git", "add", "-A"], cwd=WORK)
        diff = run(["git", "status", "--porcelain"], cwd=WORK).stdout.strip()
        log(f"（dry-run）待提交 {len(diff.splitlines()) if diff else 0} 个文件改动")
        return 0

    sha = commit(args.message)
    if sha is None:
        log("本地与远端一致，无需发布")
        return 0
    push()
    published = head()
    HEAD_FILE.write_text(published + "\n")
    log(f"✓ 已推送 gh-pages（{published[:8]}）")
    if args.verify:
        verify(published, args.marker)
    return 0


if __name__ == "__main__":
    sys.exit(main())
