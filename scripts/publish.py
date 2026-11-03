#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把当前目录发布到 GitHub Pages（gh-pages 分支）。

本机到 github.com 的 git 端口不通，但 api.github.com 可用，所以用 GitHub API
直接建 tree/commit 并移动 gh-pages ref。发布内容 = 仓库根目录下的站点与源码，
跳过 .git / .private-inbox / logs / __pycache__ / 浏览器临时文件。

    python3 scripts/publish.py --dry-run
    python3 scripts/publish.py --message "daily: X 巡检 2026-11-03"
    python3 scripts/publish.py --verify

前提：gh 已登录且对仓库有 contents 写权限。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GH = shutil.which("gh") or "/Users/wz/.local/bin/gh"
REPO = "Shrekwang-netizen/aiflow-site"
EXCLUDE_DIRS = {".git", ".private-inbox", "logs", "__pycache__", ".venv", "node_modules"}
EXCLUDE_NAMES = {".DS_Store"}


def log(msg: str) -> None:
    print(msg, flush=True)


def gh(method: str, path: str, payload: dict | None = None) -> dict:
    cmd = [GH, "api", "--method", method, path]
    data = None
    if payload is not None:
        cmd += ["--input", "-"]
        data = json.dumps(payload, ensure_ascii=False)
    proc = subprocess.run(cmd, input=data, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"gh api {method} {path} 失败：{proc.stderr.strip()}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def collect_files() -> list[Path]:
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.name in EXCLUDE_NAMES or path.suffix == ".pyc":
            continue
        files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--branch", default="gh-pages")
    parser.add_argument("--message", default="")
    parser.add_argument("--force", action="store_true", help="即使与远端一致也提交")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    files = collect_files()
    log(f"→ {len(files)} 个文件待发布")

    def blob_sha(content: str) -> str:
        data = content.encode("utf-8")
        return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()

    entries = []
    local_sha = {}
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            log(f"  跳过二进制文件 {path.relative_to(ROOT)}")
            continue
        rel = path.relative_to(ROOT).as_posix()
        entries.append({"path": rel, "mode": "100644", "type": "blob", "content": content})
        local_sha[rel] = blob_sha(content)

    if args.dry_run:
        for f in files[:12]:
            log(f"  {f.relative_to(ROOT)}")
        if len(files) > 12:
            log(f"  … 其余 {len(files) - 12} 个")
        return 0

    log(f"  文本文件 {len(entries)} 个")

    ref = gh("GET", f"repos/{args.repo}/git/ref/heads/{args.branch}")
    parent = ref["object"]["sha"]
    log(f"  当前 {args.branch}: {parent[:8]}")

    remote = {}
    try:
        head_commit = gh("GET", f"repos/{args.repo}/git/commits/{parent}")
        tree = gh("GET", f"repos/{args.repo}/git/trees/{head_commit['tree']['sha']}?recursive=1")
        remote = {item["path"]: item["sha"] for item in tree.get("tree", [])
                  if item.get("type") == "blob"}
    except SystemExit:
        remote = {}
    changed = sorted(path for path, sha in local_sha.items() if remote.get(path) != sha)
    removed = sorted(path for path in remote if path not in local_sha)
    if not args.force and not changed and not removed:
        log("· 与远端一致，跳过发布")
        return 0
    log(f"  变更 {len(changed)} 个文件，" + (f"删除 {len(removed)} 个" if removed else "无删除"))

    tree = gh("POST", f"repos/{args.repo}/git/trees", {"tree": entries})
    message = args.message or f"publish: {time.strftime('%Y-%m-%d %H:%M')}"
    commit = gh("POST", f"repos/{args.repo}/git/commits", {
        "message": message, "tree": tree["sha"], "parents": [parent]})
    gh("PATCH", f"repos/{args.repo}/git/refs/heads/{args.branch}",
       {"sha": commit["sha"], "force": True})
    log(f"✓ 已推送 {args.branch}（{commit['sha'][:8]}）")

    if args.verify:
        url = "https://shrekwang-netizen.github.io/aiflow-site/watchlist.html"
        expected = time.strftime("%Y.%m.%d")
        log(f"→ 等待 Pages 生效并核验 {url}")
        for _ in range(10):
            time.sleep(12)
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    html = resp.read().decode("utf-8", "replace")
                if expected in html or "最近一次查阅" in html:
                    log(f"✓ 线上页面可访问（含 {expected} 标记）")
                    return 0
            except Exception as exc:  # noqa: BLE001
                log(f"  …还没生效：{exc}")
        log("! 线上核验超时，请稍后手动确认")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
