#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X 观察名单巡检（新架构）

读 data/x-watchlist.json 里启用的公开账号，用本机 Chrome 的登录态/代理插件在
后台标签页逐个打开主页，读取可见帖子，产出：
  .private-inbox/x-<时间戳>.json   原始帖子 + 疑似人才/组织候选（gitignored）
  .private-inbox/x-<时间戳>.md     给人看的候选摘要
  data/monitor.json                实际巡检覆盖（成功/失败账号、帖子数、窗口）
  data/run-history.json            追加一条运行记录（保留最近 90 次）

原则（见 docs/daily-update.md）：
- 只读公开主页可见内容，不绕过登录/限制；
- 记录覆盖缺口，不把「没读到」写成「没有消息」；
- 不自动写 records.json、不自动判决新闻，候选留给人/AI 复核。

    python3 scripts/collect_x.py                 # 全量巡检
    python3 scripts/collect_x.py --limit 3       # 先试 3 个
    python3 scripts/collect_x.py --dry-run       # 只打印，不写任何文件
    python3 scripts/collect_x.py --handles sama,tianyi
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRIVATE = ROOT / ".private-inbox"
WATCHLIST = DATA / "x-watchlist.json"
MONITOR = DATA / "monitor.json"
HISTORY = DATA / "run-history.json"
TZ_CN = timezone(timedelta(hours=8))
X_BASE = "https://x.com"


def now_cn() -> datetime:
    return datetime.now(TZ_CN)


def iso_now() -> str:
    return now_cn().isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"! {msg}", file=sys.stderr, flush=True)


class ScanError(RuntimeError):
    pass


class TabGone(ScanError):
    pass


JS_STATE = r"""
(() => {
  const arts = document.querySelectorAll('article[data-testid="tweet"], article[role="article"]');
  const body = document.body ? document.body.innerText.slice(0, 800) : '';
  const loginBtn = !!document.querySelector('a[href="/i/flow/login"], [data-testid="loginButton"]');
  return {
    ready: document.readyState,
    url: location.href,
    title: document.title,
    tweets: arts.length,
    login: loginBtn,
    hrefs: [...arts].map(a => {
      const t = a.querySelector('time[datetime]');
      const l = t ? t.closest('a') : null;
      return l ? l.getAttribute('href') : '';
    }).slice(0, 40),
    body: body,
    err: location.href.indexOf('chrome-error://') === 0,
    notfound: /this account doesn.t exist|账号不存在|该账号不存在/i.test(body),
    empty: /hasn.t posted|0 posts|no posts|还没发布|暂无内容|暂无帖子/i.test(body)
  };
})()
"""

JS_TWEETS = r"""
(() => {
  const arts = [...document.querySelectorAll('article[data-testid="tweet"], article[role="article"]')];
  return arts.map(a => {
    const texts = [...a.querySelectorAll('[data-testid="tweetText"]')];
    const users = [...a.querySelectorAll('[data-testid="User-Name"]')];
    const times = [...a.querySelectorAll('time[datetime]')];
    const t0 = times.length ? times[0] : null;
    const link = (t0 && t0.closest('a')) || a.querySelector('a[href*="/status/"]');
    const socialEl = a.querySelector('[data-testid="socialContext"]');
    const social = socialEl ? socialEl.innerText : '';
    const metrics = {};
    ['reply', 'retweet', 'like', 'bookmark', 'analytics'].forEach(k => {
      const el = a.querySelector('[data-testid="' + k + '"]');
      if (el) metrics[k] = (el.getAttribute('aria-label') || el.innerText || '').trim();
    });
    const quoted = (users.length > 1 && texts.length > 1)
      ? { user: users[1].innerText, text: texts[1].innerText }
      : null;
    return {
      href: link ? link.getAttribute('href') : '',
      datetime: t0 ? t0.getAttribute('datetime') : '',
      text: texts.length ? texts[0].innerText : '',
      lang: (texts.length && texts[0].getAttribute('lang')) || '',
      user: users.length ? users[0].innerText : '',
      social: social,
      quoted: quoted,
      metrics: metrics,
      media: a.querySelectorAll('[data-testid="tweetPhoto"], [data-testid="tweetVideo"], [data-testid="videoPlayer"]').length,
      promoted: /promoted|广告|推广|赞助/i.test(
        (users.length ? users[0].innerText : '') + ' ' + social +
        (a.querySelector('[data-testid="placementTracking"]') ? ' promoted' : ''))
    };
  });
})()
"""


class TabGone(ScanError):
    """扫描标签页被关掉了（用户手动关闭或 Chrome 退出）。"""


class TimelineTab:
    """导航 / 等渲染 / 滚动 / 抽推文的公共逻辑；eval_js 与 navigate 由子类实现。"""

    closed = False

    def eval_js(self, expression: str, timeout: float = 30.0):
        raise NotImplementedError

    def navigate(self, url: str) -> str:
        raise NotImplementedError

    def goto(self, url: str, expect_handle: str | None = None,
             timeout: float = 45.0) -> dict:
        nav_error = self.navigate(url) or ""
        started = time.time()
        deadline = started + timeout
        last: dict = {}
        while time.time() < deadline:
            try:
                last = self.eval_js(JS_STATE) or {}
            except ScanError:
                if self.closed:
                    raise
                last = {}
            if last.get("err"):
                last["nav_error"] = nav_error or "chrome-error"
                return last
            url_now = (last.get("url") or "").lower()
            ready = last.get("ready") == "complete"
            mine = bool(expect_handle) and any(
                (h or "").lower().startswith(f"/{expect_handle.lower()}/")
                for h in (last.get("hrefs") or []))
            own_ok = (not expect_handle) or mine or (time.time() - started > 18)
            has_content = (bool(last.get("tweets")) or last.get("empty")
                           or last.get("notfound") or last.get("login"))
            right_page = (not expect_handle) or (expect_handle.lower() in url_now) or last.get("login")
            if ready and has_content and right_page and own_ok:
                last["nav_error"] = nav_error
                return last
            time.sleep(0.9)
        last["nav_error"] = nav_error
        last["timeout"] = True
        return last

    def collect(self, max_tweets: int, scrolls: int, scroll_wait: float = 1.8) -> list:
        seen: dict[str, dict] = {}
        for round_index in range(scrolls + 1):
            try:
                rows = self.eval_js(JS_TWEETS) or []
            except ScanError:
                if self.closed:
                    raise
                rows = []
            grew = 0
            for row in rows:
                m = re.search(r"/status/(\d+)", row.get("href") or "")
                key = m.group(1) if m else (row.get("href") or "")
                if key and key not in seen:
                    seen[key] = row
                    grew += 1
            if len(seen) >= max_tweets:
                break
            if round_index == scrolls:
                break
            if grew == 0 and round_index > 0:
                break
            try:
                self.eval_js(
                    "(function(){window.scrollTo(0, document.scrollingElement ? "
                    "document.scrollingElement.scrollHeight : document.body.scrollHeight); "
                    "return true;})()")
            except ScanError:
                if self.closed:
                    raise
            time.sleep(scroll_wait + random.random() * 0.6)
        return list(seen.values())

    def page_html(self) -> str:
        return self.eval_js("document.documentElement.outerHTML", timeout=60) or ""


APPLESCRIPT_JS = r"""on run argv
  set wid to (item 1 of argv) as integer
  set tid to (item 2 of argv) as integer
  set js to item 3 of argv
  tell application "Google Chrome"
    set w to first window whose id is wid
    set t to first tab of w whose id is tid
    return execute t javascript js
  end tell
end run
"""

APPLESCRIPT_OPEN = r"""on run argv
  set theUrl to item 1 of argv
  tell application "Google Chrome"
    set w to front window
    set wid to id of w
    set oldIndex to active tab index of w
    set t to make new tab at end of tabs of w with properties {URL:theUrl}
    set tid to id of t
    try
      set active tab index of w to oldIndex
    end try
    return (wid as string) & "|" & (tid as string)
  end tell
end run
"""

APPLESCRIPT_CLOSE = r"""on run argv
  set wid to (item 1 of argv) as integer
  set tid to (item 2 of argv) as integer
  tell application "Google Chrome"
    set w to first window whose id is wid
    set t to first tab of w whose id is tid
    close t
  end tell
end run
"""

APPLESCRIPT_SET_URL = r"""on run argv
  set wid to (item 1 of argv) as integer
  set tid to (item 2 of argv) as integer
  set theUrl to item 3 of argv
  tell application "Google Chrome"
    set w to first window whose id is wid
    set t to first tab of w whose id is tid
    set URL of t to theUrl
  end tell
end run
"""


class ChromeApp:
    """驱动你已经开着的 Chrome：AppleScript 控制标签页 + execute javascript 读 DOM。"""

    def __init__(self):
        if not self._running():
            raise ScanError("没检测到正在运行的 Chrome。先打开 Chrome（脚本不会自己启动它）。")
        base = Path(tempfile.gettempdir())
        self.scripts = {}
        for name, source in (("js", APPLESCRIPT_JS), ("open", APPLESCRIPT_OPEN),
                             ("close", APPLESCRIPT_CLOSE), ("set_url", APPLESCRIPT_SET_URL)):
            path = base / f"aiflow_xscan_{name}.applescript"
            path.write_text(source, encoding="utf-8")
            self.scripts[name] = path

    @staticmethod
    def _running() -> bool:
        try:
            out = subprocess.run(["ps", "-ax", "-o", "command="],
                                 capture_output=True, text=True, timeout=10).stdout
        except Exception:
            return False
        return "Google Chrome.app/Contents/MacOS/Google Chrome" in out

    def _osa(self, name: str, *args, timeout: float = 60.0) -> str:
        path = self.scripts[name]
        try:
            res = subprocess.run(["osascript", str(path), *[str(a) for a in args]],
                                 capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ScanError(f"AppleScript 超时（{name}），页面可能卡住了") from None
        if res.returncode != 0:
            err = (res.stderr or res.stdout).strip()
            low = err.lower()
            if "javascript" in low and ("关闭" in err or "disabled" in low or "not allowed" in low):
                raise ScanError(
                    "Chrome 的「允许 Apple 事件中的 JavaScript」没开："
                    "菜单栏 查看/显示 → 开发者 → 允许 Apple 事件中的 JavaScript")
            if "can’t get tab" in low or "can't get tab" in low or "invalid index" in low:
                raise TabGone(f"扫描标签页被关掉了：{err[:120]}")
            raise ScanError(f"AppleScript 执行失败：{err[:300]}")
        return res.stdout.rstrip("\n")

    def open_tab(self, url: str = "about:blank") -> "AppleTab":
        raw = self._osa("open", url).strip()
        try:
            wid, tid = (int(x) for x in raw.split("|"))
        except ValueError:
            raise ScanError(f"新建标签页失败：{raw[:200]}") from None
        return AppleTab(self, wid, tid)

    def close_tab(self, tab: "AppleTab") -> None:
        try:
            self._osa("close", tab.wid, tab.tid, timeout=15)
        except ScanError:
            pass

    def set_url(self, wid: int, tid: int, url: str) -> None:
        self._osa("set_url", wid, tid, url, timeout=30)

    def eval_js(self, wid: int, tid: int, expression: str):
        # 直接把表达式交给 Chrome 执行，再把结果 JSON 化，避免 AppleScript 转义地狱
        wrapped = f"JSON.stringify({expression})"
        raw = self._osa("js", wid, tid, wrapped)
        if raw in ("", "missing value"):
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw


class AppleTab(TimelineTab):
    """你开着的 Chrome 里的一个后台标签页。"""

    def __init__(self, app: ChromeApp, wid: int, tid: int):
        self.app = app
        self.wid = wid
        self.tid = tid

    def eval_js(self, expression: str, timeout: float = 30.0):
        try:
            return self.app.eval_js(self.wid, self.tid, expression)
        except TabGone:
            self.closed = True
            raise

    def navigate(self, url: str) -> str:
        # 标签页被关掉（用户手滑或 Chrome 清理）时自动重开一个，不让整轮扫描报废
        for attempt in range(2):
            try:
                self.app.set_url(self.wid, self.tid, url)
                return ""
            except TabGone:
                if attempt:
                    raise
                fresh = self.app.open_tab("about:blank")
                self.wid, self.tid = fresh.wid, fresh.tid
                warn("扫描标签页不见了，已自动重开一个继续")
        return ""

    def has_login(self) -> bool:
        state = self.goto(f"{X_BASE}/home")
        if state.get("err"):
            raise NetworkUnavailable(
                f"你开着的 Chrome 打不开 x.com/home（{state.get('nav_error') or 'chrome-error'}），"
                "检查一下代理插件/VPN 是否还开着")
        if state.get("timeout") and not state.get("tweets"):
            raise NetworkUnavailable("x.com/home 45 秒没响应：代理/VPN 插件可能断了")
        return not (state.get("login") and not state.get("tweets"))




# ---------------------------------------------------------------- 采集逻辑

TALENT_RE = re.compile(
    r"\b(join(?:s|ed|ing)?|leav(?:e|es|ing)|left|depart(?:s|ed|ing)?|resign(?:s|ed|ing)?|"
    r"hire(?:s|d|ing)?|layoffs?|laid off|poach(?:es|ed|ing)?|found(?:s|ed|ing)?|"
    r"appoint(?:s|ed|ing)?|promot(?:es|ed|ing)?|reorg(?:anization)?|restructur\w*|"
    r"step(?:ping)? down|head of|co-?founder|chief|CEO|CTO|CMO|COO|"
    r"joining|new role|next chapter|team of|building a team)\b"
    r"|加入|入职|离职|离开|裁员|招聘|挖角|创业|创始人|合伙人|晋升|任命|卸任|"
    r"组织调整|重组|负责人|带头人|团队扩张|扩招|岗位|简历",
    re.I,
)

PROBE = r"""
(() => {
  const q = s => document.querySelector(s);
  const nameEl = q('[data-testid="UserName"]');
  const bioEl = q('[data-testid="UserDescription"]');
  return {
    url: location.href,
    name: nameEl ? nameEl.innerText.split('\n')[0] : '',
    bio: bioEl ? bioEl.innerText.slice(0, 300) : ''
  };
})()
"""


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", (value or "").lower())


def name_matches(expected: str, actual: str) -> bool:
    a, b = normalize_name(expected), normalize_name(actual)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.62


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def scan_window(monitor: dict, hours: int) -> tuple[datetime, datetime]:
    end = now_cn()
    start = end - timedelta(hours=hours)
    last = parse_dt(monitor.get("checked_at", ""))
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=TZ_CN)
        overlap = last - timedelta(hours=48)
        # 断更太久时只补最后 7 天，避免一次拉爆
        if (end - overlap).total_seconds() > 7 * 86400:
            overlap = end - timedelta(days=7)
        start = max(start, overlap) if overlap > start else overlap
    return start, end


def collect_account(tab: "AppleTab", account: dict, start: datetime, end: datetime,
                    max_posts: int, scrolls: int) -> dict:
    handle = account["handle"]
    url = f"{X_BASE}/{handle}"
    state = tab.goto(url, expect_handle=handle, timeout=40)
    if state.get("err"):
        raise ScanError(f"打不开主页（{state.get('nav_error') or 'chrome-error'}）")
    if state.get("login") and not state.get("tweets"):
        raise ScanError("X 要求登录，登录态不可用")
    if state.get("notfound"):
        raise ScanError("账号不存在")
    if state.get("empty"):
        return {"handle": handle, "checked_at": iso_now(), "posts_read": 0, "posts": [], "candidates": []}

    final_url = state.get("url") or ""
    path_handle = final_url.rstrip("/").split("/")[-1].lower()
    if path_handle not in (handle.lower(), ""):
        raise ScanError(f"账号发生重定向：{final_url}")

    info = tab.eval_js(PROBE) or {}
    actual_name = info.get("name") or ""
    if actual_name and not name_matches(account.get("name", ""), actual_name):
        raise ScanError(f"显示名称与名单不符（期望 {account.get('name')}，实际 {actual_name}）")

    rows = tab.collect(max_tweets=max(max_posts * 2, 40), scrolls=scrolls)
    posts = []
    seen = set()
    for row in rows:
        m = re.search(r"/([^/]+)/status/(\d+)", row.get("href") or "")
        if not m or m.group(1).lower() != handle.lower():
            continue
        tweet_id = m.group(2)
        if tweet_id in seen:
            continue
        dt = parse_dt(row.get("datetime") or "")
        if dt is None or dt < start or dt > end:
            continue
        text = (row.get("text") or "").strip()
        quoted = row.get("quoted") or {}
        if not text and not (quoted.get("text") or "").strip() and not row.get("media"):
            continue
        seen.add(tweet_id)
        posts.append({
            "url": f"{X_BASE}/{handle}/status/{tweet_id}",
            "datetime": dt.isoformat(),
            "text": text[:2000],
            "lang": row.get("lang") or "",
            "quoted": {
                "user": (quoted.get("user") or "").strip()[:80],
                "text": (quoted.get("text") or "").strip()[:1000],
            } if quoted else None,
            "metrics": row.get("metrics") or {},
            "media": int(row.get("media") or 0),
        })

    posts.sort(key=lambda p: p["datetime"], reverse=True)
    posts = posts[:max_posts]
    candidates = []
    for post in posts:
        blob = post["text"] + " " + ((post.get("quoted") or {}).get("text") or "")
        if TALENT_RE.search(blob):
            candidates.append({
                "url": post["url"],
                "datetime": post["datetime"],
                "text": post["text"][:1200],
                "matched": sorted({m.group(0).lower() for m in TALENT_RE.finditer(blob)})[:6],
            })
    return {
        "handle": handle,
        "name": account.get("name", ""),
        "group": account.get("group", ""),
        "profile": info,
        "checked_at": iso_now(),
        "posts_read": len(posts),
        "posts": posts,
        "candidates": candidates,
    }


def write_outputs(accounts: list[dict], failures: list[dict], start: datetime,
                  end: datetime, dry_run: bool) -> dict:
    posts_total = sum(a["posts_read"] for a in accounts)
    candidate_total = sum(len(a["candidates"]) for a in accounts)
    stamp = now_cn().strftime("%Y-%m-%d-%H%M")
    checked = [a["handle"] for a in accounts]
    failed = [f["handle"] for f in failures]

    summary = (
        f"自动巡检 {len(accounts) + len(failures)} 个账号：成功读取 {len(accounts)} 个，"
        f"失败 {len(failures)} 个；共读到 {posts_total} 条可见帖子"
        f"（{start.strftime('%m-%d %H:%M')} 至 {end.strftime('%m-%d %H:%M')}，"
        f"每号最多 40 条），其中 {candidate_total} 条命中人才/组织关键词，已写入本地候选待复核。"
        f"公开时间线可能只展示部分帖子，不代表完整抓取。"
    )

    payload = {
        "generated_at": end.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "window": {"start": start.isoformat(timespec="seconds"),
                   "end": end.isoformat(timespec="seconds")},
        "accounts": accounts,
        "failures": failures,
        "summary": summary,
    }

    if dry_run:
        return {"summary": summary, "posts_read": posts_total,
                "candidate_total": candidate_total, "stamp": stamp}

    PRIVATE.mkdir(exist_ok=True)
    (PRIVATE / f"x-{stamp}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [f"# X 巡检候选 · {end.strftime('%Y-%m-%d %H:%M')}",
             "", f"窗口：{start.strftime('%Y-%m-%d %H:%M')} → {end.strftime('%Y-%m-%d %H:%M')}（北京时间）",
             "", summary, ""]
    for account in accounts:
        if not account["candidates"]:
            continue
        lines.append(f"## @{account['handle']} · {account['name']}（{account['posts_read']} 条 / "
                     f"{len(account['candidates'])} 条候选）")
        for cand in account["candidates"]:
            text = re.sub(r"\s+", " ", cand["text"])[:220]
            lines.append(f"- {cand['datetime'][:16].replace('T', ' ')} · {', '.join(cand['matched'])}")
            lines.append(f"  {text}")
            lines.append(f"  {cand['url']}")
        lines.append("")
    if failures:
        lines.append("## 未读到")
        for failure in failures:
            lines.append(f"- @{failure['handle']}：{failure['reason']}")
        lines.append("")
    (PRIVATE / f"x-{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    monitor = load_json(MONITOR, {})
    monitor.update({
        "checked_at": end.isoformat(timespec="seconds"),
        "mode": "daily-scan",
        "coverage": "visible-window",
        "accounts_checked": checked,
        "accounts_failed": failed,
        "posts_read": posts_total,
        "new_records": 0,
        "reviewed_records": 0,
        "summary": summary,
        "schedule": "每天 10:00 · 北京时间",
        "automation_enabled": True,
        "automation_id": "aiflow",
    })
    MONITOR.write_text(json.dumps(monitor, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    history = load_json(HISTORY, [])
    history.insert(0, {
        "checked_at": end.isoformat(timespec="seconds"),
        "mode": "daily-scan",
        "coverage": "visible-window",
        "accounts_checked": checked,
        "accounts_failed": failed,
        "posts_read": posts_total,
        "new_records": 0,
        "reviewed_records": 0,
        "summary": summary,
        "schedule": "每天 10:00 · 北京时间",
        "automation_enabled": True,
        "automation_id": "aiflow",
    })
    HISTORY.write_text(json.dumps(history[:90], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"summary": summary, "posts_read": posts_total,
            "candidate_total": candidate_total, "stamp": stamp}


def main() -> int:
    parser = argparse.ArgumentParser(description="X 观察名单巡检（只写候选与监控，不改 records）")
    parser.add_argument("--handles", default="", help="只巡检这些账号，逗号分隔")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--window-hours", type=int, default=48)
    parser.add_argument("--max-posts", type=int, default=40)
    parser.add_argument("--scrolls", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    parser.add_argument("--no-monitor", action="store_true", help="不改 monitor/run-history")
    args = parser.parse_args()

    watch = load_json(WATCHLIST, {"accounts": []})
    accounts_meta = [a for a in watch.get("accounts", []) if a.get("enabled", True)]
    if args.handles:
        wanted = {h.strip().lstrip("@").lower() for h in args.handles.split(",") if h.strip()}
        accounts_meta = [a for a in accounts_meta if a["handle"].lower() in wanted]
    if args.limit:
        accounts_meta = accounts_meta[:args.limit]
    if not accounts_meta:
        warn("没有可巡检的账号")
        return 1

    monitor = load_json(MONITOR, {})
    start, end = scan_window(monitor, args.window_hours)
    log(f"→ 巡检 {len(accounts_meta)} 个账号，窗口 {start.strftime('%m-%d %H:%M')} → {end.strftime('%m-%d %H:%M')}")

    app = ChromeApp()
    tab = app.open_tab("about:blank")
    accounts: list[dict] = []
    failures: list[dict] = []
    fatal = None
    try:
        for index, account in enumerate(accounts_meta, 1):
            handle = account["handle"]
            try:
                result = collect_account(tab, account, start, end, args.max_posts, args.scrolls)
                accounts.append(result)
                log(f"[{index}/{len(accounts_meta)}] @{handle} ✓ {result['posts_read']} 条 / "
                    f"{len(result['candidates'])} 条候选")
            except ScanError as exc:
                failures.append({"handle": handle, "reason": str(exc)[:160]})
                log(f"[{index}/{len(accounts_meta)}] @{handle} ✗ {exc}")
                if "登录" in str(exc) or "打不开" in str(exc):
                    fatal = exc
                    break
            time.sleep(0.8 + random.random() * 0.6)
    finally:
        app.close_tab(tab)

    if args.no_monitor and not args.dry_run:
        log("（--no-monitor）不更新 monitor/run-history")
        return 0
    result = write_outputs(accounts, failures, start, end, args.dry_run)
    log("")
    log(result["summary"])
    if args.dry_run:
        log(f"（dry-run）候选 {result['candidate_total']} 条，未写文件")
    else:
        log(f"→ 候选 {result['candidate_total']} 条 → .private-inbox/x-{result['stamp']}.json")
        log("→ 已更新 data/monitor.json 与 data/run-history.json")
    if fatal is not None:
        warn(f"巡检提前中止：{fatal}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
