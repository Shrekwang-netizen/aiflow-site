#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIFLOW 采集器：把「机器能自动拿到」的候选线索收进 data/inbox.json

    python3 scripts/refresh.py                  # 全部源
    python3 scripts/refresh.py --source rss     # 只跑 RSS
    python3 scripts/refresh.py --source wechat  # 只跑公众号（搜狗微信搜索）
    python3 scripts/refresh.py --list           # 看 inbox 里有什么

可用源（2026-10 实测）
----------------------
自动：IT之家 / 钛媒体 / 极客公园 / 量子位 / 雷峰网 / InfoQ / TechCrunch / The Verge（RSS）
      36 氪快讯（RSSHub）、晚点首页（SSR）、知乎热榜（JSON）、搜狗微信（公众号搜索）
人工：脉脉、微博、小红书、LinkedIn、36 氪主站（WAF）、机器之心（已收缩）

设计原则
--------
采集器只产出「候选」（status=candidate），不直接进站。站上每条记录都必须
经过一次人工/AI 复核：确认日期、当事方、去向、信度，并补一句话推荐理由。
"""

from __future__ import annotations

import argparse
import html as htmllib
import http.cookiejar
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INBOX = DATA / "inbox.json"
ITEMS = DATA / "items.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 人事关键词：标题/正文命中即收
KEYWORDS = [
    "离职", "辞职", "卸任", "出走", "离开", "加入", "加盟", "入职", "跳槽", "转投",
    "挖角", "挖来", "被挖", "裁员", "缩编", "解散", "重组", "汇报线",
    "组织调整", "内部信", "全员信", "创业", "期权", "薪酬", "欠薪", "返岗", "回流",
    "晋升", "任命", "接管",
    "depart", "resign", "quit", "leave", "join", "hire", "poach", "layoff", "reorg",
    "restructur", "stepp", "down", "fired",
]

# 公司名 → slug
COMPANY_ALIASES = {
    "minimax": "minimax", "稀宇": "minimax", "海螺": "minimax",
    "stepfun": "stepfun", "阶跃": "stepfun",
    "zhipu": "zhipu", "智谱": "zhipu", "z.ai": "zhipu", "glm": "zhipu",
    "moonshot": "moonshot", "月之暗面": "moonshot", "kimi": "moonshot",
    "qwen": "alibaba-qwen", "通义": "alibaba-qwen", "阿里达摩院": "alibaba-qwen",
    "阿里云": "alibabacloud", "alibaba cloud": "alibabacloud",
    "tencent": "tencent", "腾讯": "tencent", "混元": "tencent", "元宝": "tencent",
    "bytedance": "bytedance", "字节": "bytedance", "seed": "bytedance", "豆包": "bytedance",
    "xiaomi": "xiaomi", "小米": "xiaomi",
    "baidu": "baidu", "百度": "baidu", "文心": "baidu",
    "deepseek": "deepseek", "深度求索": "deepseek",
    "sensetime": "sensetime", "商汤": "sensetime",
    "openbmb": "openbmb", "面壁": "openbmb", "minicpm": "openbmb",
    "lingyiwanwu": "lingyiwanwu", "零一万物": "lingyiwanwu",
    "iflytek": "iflytek", "科大讯飞": "iflytek", "讯飞": "iflytek",
    "kunlun": "kunlun", "昆仑万维": "kunlun", "天工": "kunlun",
    "agibot": "agibot", "智元": "agibot",
    "unitree": "unitree", "宇树": "unitree",
    "huawei": "huawei", "华为": "huawei", "盘古": "huawei",
    "ant group": "ant", "蚂蚁": "ant", "百灵": "ant",
    "meituan": "meituan", "美团": "meituan", "longcat": "meituan",
    "openai": "openai", "anthropic": "anthropic", "claude": "anthropic",
    "xai": "xai", "grok": "xai", "spacexai": "xai", "spacexsi": "xai",
    "deepmind": "google-deepmind", "google": "google-deepmind", "gemini": "google-deepmind",
    "meta": "meta", "superintelligence": "meta", "llama": "meta",
    "microsoft": "microsoft", "微软": "microsoft", "copilot": "microsoft",
    "nvidia": "nvidia", "英伟达": "nvidia",
    "mistral": "mistral", "thinking machines": "thinking-machines",
    "perplexity": "perplexity", "cursor": "cursor", "anysphere": "cursor",
    "cohere": "cohere", "character.ai": "character-ai", "scale ai": "scale-ai",
    "hugging face": "huggingface", "huggingface": "huggingface",
    "amazon": "amazon", "aws": "amazon", "apple": "apple", "苹果": "apple",
}

FEEDS = [
    ("量子位", "https://www.qbitai.com/feed"),
    ("雷峰网", "https://www.leiphone.com/feed"),
    ("IT之家", "https://www.ithome.com/rss/"),
    ("钛媒体", "https://www.tmtpost.com/rss.xml"),
    ("极客公园", "https://www.geekpark.net/rss"),
    ("InfoQ 中文", "https://www.infoq.cn/feed"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("Semafor Tech", "https://www.semafor.com/rss/technology.xml"),
    ("The Register AI", "https://www.theregister.com/software/ai/headlines.atom"),
    ("TechCrunch Layoffs", "https://techcrunch.com/tag/layoffs/feed/"),
    ("TechCrunch OpenAI", "https://techcrunch.com/tag/openai/feed/"),
    ("TechCrunch Anthropic", "https://techcrunch.com/tag/anthropic/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

RSSHUB_BASES = [
    "https://rsshub.rssforever.com",
    "https://hub.slarker.me",
    "https://rsshub.liumingye.cn",
]
RSSHUB_ROUTES = [
    ("36 氪快讯", "/36kr/newsflashes"),
    ("财新", "/caixin/latest"),
    ("华尔街见闻快讯", "/wallstreetcn/live/global"),
]

# 搜狗微信（已停用：按用户要求不再使用，仅保留代码备查）
WECHAT_QUERIES = [
    "AI 离职", "大模型 裁员", "AI 团队 组织调整", "字节 离职",
    "Seed 离职", "Kimi 离职", "智谱 离职", "MiniMax 离职",
    "阿里 通义 离职", "腾讯 混元 离职", "小米 大模型 挖人", "AI 研究员 加入",
    "OpenAI 离职", "Anthropic 离职", "研究员 离职 创业", "AI 公司 裁员",
    "脉脉 爆料 大厂", "员工 爆料 AI", "内部员工 透露 离职",
]

# 360 搜索：作为脉脉 / 微博 / 36 氪的「公开索引层」
# 用法：360 搜 site:xxx → 解析跳转 → 打开发布页（脉脉/36氪文章页免登录可读）
BUZZ_QUERIES = [
    ("site:maimai.cn 字节 离职", "脉脉"),
    ("site:maimai.cn 腾讯 离职", "脉脉"),
    ("site:maimai.cn 阿里 离职", "脉脉"),
    ("site:maimai.cn 百度 离职", "脉脉"),
    ("site:maimai.cn 小米 离职", "脉脉"),
    ("site:maimai.cn 大模型 离职", "脉脉"),
    ("site:weibo.com 离职 AI 大厂", "微博"),
    ("site:36kr.com 离职 AI", "36 氪"),
]

BLIND_CHANNELS = ["layoffs", "openai", "anthropic", "microsoft", "meta", "google", "nvidia", "amazon"]
BLIND_BASE = "https://www.teamblind.com"

HN_QUERIES = ["AI layoffs", "OpenAI hires", "Anthropic hires", "AI startup layoffs", "tech layoffs"]

DINQ_URL = "https://talent.dinq.me/?range=7d"
LATEPOST_URL = "https://www.latepost.com/"
ZHIHU_HOT_URL = "https://api.zhihu.com/topstory/hot-lists/total?limit=50&desktop=true"


# ---------------------------------------------------------------- HTTP

def fetch(url: str, timeout: int = 25, referer: str | None = None) -> str:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
        raw = resp.read()
    for enc in ("utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def text_of(fragment: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


# ---------------------------------------------------------------- 通用 RSS

def parse_feed(xml_text: str) -> list[dict]:
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)
    root = ET.fromstring(clean.encode("utf-8"))
    entries = []
    for node in root.iter():
        tag = node.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = pub = desc = ""
        for child in node:
            ct = child.tag.split("}")[-1]
            if ct == "title" and child.text:
                title = child.text.strip()
            elif ct == "link":
                link = (child.text or "").strip() or child.attrib.get("href", "")
            elif ct in ("pubDate", "published", "updated") and child.text:
                pub = child.text.strip()
            elif ct in ("description", "summary", "content") and child.text:
                desc = child.text.strip()
        if title:
            entries.append({"title": text_of(title), "url": link, "pub": pub, "desc": text_of(desc)})
    return entries


def parse_dt(value: str) -> str:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except Exception:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    return m.group(0) if m else date.today().isoformat()


NOISE_RE = re.compile(r"ETF|收评|午评|早评|涨停|跌停|沪指|深成指|创业板指|成交额|下跌个股|北向资金")


def is_noise(text: str) -> bool:
    """行情/盘面类误命中：'创业板'会命中'创业'，必须挡掉。"""
    return bool(NOISE_RE.search(text)) or "创业板" in text


def hit_keyword(*texts: str) -> str | None:
    blob = " ".join(t for t in texts if t).lower().replace("创业板", "")
    for kw in KEYWORDS:
        if kw in blob:
            return kw
    return None


def candidate(origin: str, title: str, url: str, dt: str, *, summary: str = "",
              company: str | None = None, kind: str = "rumor", extra: dict | None = None) -> dict:
    rec = {
        "status": "candidate",
        "origin": origin,
        "date": dt,
        "type": kind,
        "company": company or "other",
        "to_company": None,
        "person": {"name": "", "role": ""},
        "title": title[:80],
        "summary": summary[:160],
        "quote": title[:80],
        "confidence": "rumor",
        "source": {"name": origin, "url": url},
        "tags": ["待复核"],
    }
    if extra:
        rec.update(extra)
    return rec


# ---------------------------------------------------------------- dinq

def parse_dinq(html: str) -> list[dict]:
    rows = []
    chunks = html.split('<li class="cursor-pointer border-t')[1:]
    for ch in chunks:
        m_date = re.search(r'font-mono[^"]*text-\[13px\][^"]*">([\d-]{10})<', ch)
        m_name = re.search(r'truncate text-\[15px\] font-semibold">([^<]+)<', ch)
        if not (m_date and m_name):
            continue
        area = re.search(r'text-\[12px\] text-muted"><span class="truncate">([^<]+)<', ch)
        role = re.search(r'line-clamp-2 break-words leading-snug">([^<]+)<', ch)
        orgs = re.findall(r'truncate text-\[14px\](?: font-semibold)?\s*">([^<]+)<', ch)
        links = re.findall(r'href="(https://x\.com/[^"]+)"', ch)
        note = re.search(r'rounded bg-fg/\[0\.06\][^>]*>([^<]+)<', ch)
        rows.append({
            "date": m_date.group(1),
            "person": text_of(m_name.group(1)),
            "area": text_of(area.group(1)) if area else "",
            "role": text_of(role.group(1)) if role else "",
            "orgs": [text_of(o) for o in orgs],
            "links": links,
            "note": text_of(note.group(1)) if note else "",
        })
    return rows


def company_from(text: str) -> str | None:
    low = text.lower()
    for alias, slug in COMPANY_ALIASES.items():
        if alias in low:
            return slug
    return None


def cand_from_dinq(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        orgs = r["orgs"]
        if len(orgs) < 2:
            continue
        frm, to = orgs[-2], orgs[-1]
        c_from, c_to = company_from(frm), company_from(to)
        if not c_from and not c_to:
            continue
        if not c_from:
            title = f"{r['person']} 加入 {to}"
        elif not c_to:
            title = f"{r['person']} 离开 {frm}"
        else:
            title = f"{r['person']} 离开 {frm} 加入 {to}"
        out.append({
            "status": "candidate",
            "origin": "talent.dinq.me",
            "date": r["date"],
            "type": "join" if (c_to and not c_from) else "departure",
            "company": c_from or c_to,
            "to_company": c_to if c_from else None,
            "person": {"name": r["person"], "role": r["role"]},
            "title": title,
            "summary": f"{r['person']}（{r['area']}）此前在 {frm} 任 {r['role']}，"
                       f"现加入 {to}。信息来源为本人公开更新（{r['note'] or 'self-announced'}）。",
            "quote": f"{r['person']}: {frm} → {to}",
            "confidence": "reported",
            "source": {"name": "Talent.dinq.me", "url": DINQ_URL},
            "extra_sources": [{"name": "X", "url": l} for l in r["links"][:2]],
            "tags": ["海外人员流动"],
        })
    return out


# ---------------------------------------------------------------- RSS / RSSHub

def cand_from_feed(name: str, url: str) -> tuple[list[dict], int]:
    xml_text = fetch(url)
    entries = parse_feed(xml_text)
    out = []
    for e in entries:
        pieces = [p.strip() for p in re.split(r"[；;|｜]", e["title"]) if p.strip()]
        for piece in pieces:
            if is_noise(piece):
                continue
            kw = hit_keyword(piece)
            if not kw:
                continue
            out.append(candidate(
                name, piece, e["url"], parse_dt(e["pub"]),
                summary=f"来自 {name} 的候选线索，命中关键词「{kw}」，需核实当事方与去向。",
            ))
    return out, len(entries)


def cand_from_rss() -> list[dict]:
    out = []
    for name, url in FEEDS:
        try:
            got, total = cand_from_feed(name, url)
            print(f"  · {name}: {total} 条 → 命中 {len(got)}")
            out += got
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {name} 拉取失败：{exc}", file=sys.stderr)
    return out


def cand_from_rsshub() -> list[dict]:
    out = []
    for name, route in RSSHUB_ROUTES:
        for base in RSSHUB_BASES:
            try:
                got, total = cand_from_feed(name, base + route)
                print(f"  · {name}（{base.split('//')[1]}）: {total} 条 → 命中 {len(got)}")
                out += got
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {name} @ {base} 失败：{exc}", file=sys.stderr)
    return out


# ---------------------------------------------------------------- 晚点

def cand_from_latepost() -> list[dict]:
    h = fetch(LATEPOST_URL)
    links = re.findall(r'href="(/news/dj_detail\?id=\d+)"[^>]*>(.*?)</a>', h, re.S)
    out = []
    for href, raw_title in links:
        title = re.sub(r"\s+", " ", text_of(raw_title)).strip()
        if len(title) < 8 or not hit_keyword(title):
            continue
        out.append(candidate(
            "晚点 LatePost", title, "https://www.latepost.com" + href, date.today().isoformat(),
            summary="晚点首页候选：命中人事关键词，需打开原文核实。",
        ))
    print(f"  · 晚点首页：{len(links)} 条 → 命中 {len(out)}")
    return out


# ---------------------------------------------------------------- 知乎热榜

def cand_from_zhihu() -> list[dict]:
    data = json.loads(fetch(ZHIHU_HOT_URL))
    rows = data.get("data") or []
    out = []
    for row in rows:
        t = row.get("target") or {}
        title = (t.get("title") or "").strip()
        if not title or not hit_keyword(title):
            continue
        if not any(k in title.lower() for k in ("ai", "人工智能", "大模型", "模型", "机器人", "智能体")):
            continue
        out.append(candidate(
            "知乎热榜", title, t.get("url") or "https://www.zhihu.com/hot",
            date.today().isoformat(),
            summary="知乎热榜里与 AI 相关、且带人事关键词的讨论，作为舆情信号。",
            kind="sentiment",
        ))
    print(f"  · 知乎热榜：{len(rows)} 条 → 命中 {len(out)}")
    return out


# ---------------------------------------------------------------- 公众号（搜狗微信）

class SogouWechat:
    BASE = "https://weixin.sogou.com"

    def __init__(self) -> None:
        cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        self.opener.addheaders = [("User-Agent", UA)]

    def _get(self, url: str, referer: str | None = None) -> str:
        headers = {"User-Agent": UA}
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers)
        with self.opener.open(req, timeout=25) as resp:
            return resp.read().decode("utf-8", "replace")

    def search(self, query: str) -> list[dict]:
        url = (f"{self.BASE}/weixin?type=2&query={urllib.parse.quote(query)}"
               f"&ie=utf8&s_from=input&_sug_=n&_sug_type_=")
        h = self._get(url)
        if "antispider" in h or "请输入验证码" in h or "访问过于频繁" in h:
            raise RuntimeError("触发搜狗验证码/频率限制")
        rows = []
        blocks = re.split(r'<li id="sogou_vr_11002601_box_', h)[1:]
        for block in blocks:
            m_title = re.search(r'id="sogou_vr_11002601_title_\d+"[^>]*>(.*?)</a>', block, re.S)
            m_link = re.search(r'href="(/link\?url=[^"]+)"[^>]*id="sogou_vr_11002601_title', block, re.S)
            m_acc = re.search(r'<span class="all-time-y2">([^<]+)</span>', block)
            m_ts = re.search(r"timeConvert\('(\d{10})'\)", block)
            m_sum = re.search(r'class="txt-info"[^>]*>(.*?)</p>', block, re.S)
            if not (m_title and m_link):
                continue
            title = text_of(re.sub(r"<!--.*?-->", "", m_title.group(1)))
            rows.append({
                "title": title,
                "link": htmllib.unescape(m_link.group(1)).replace(" ", "%20"),
                "account": text_of(m_acc.group(1)) if m_acc else "",
                "ts": m_ts.group(1) if m_ts else "",
                "summary": text_of(re.sub(r"<!--.*?-->", "", m_sum.group(1)))[:120] if m_sum else "",
                "referer": url,
            })
        return rows

    def resolve(self, link: str, referer: str) -> str | None:
        try:
            resp = self._get(self.BASE + link, referer=referer)
        except Exception:  # noqa: BLE001
            return None
        frags = re.findall(r"url \+= '([^']+)'", resp)
        if frags:
            return "".join(frags)
        m = re.search(r"https?://mp\.weixin\.qq\.com/s\?[^'\"<>\s]+", resp)
        return m.group(0) if m else None


def cand_from_wechat(limit_queries: int = 1, resolve_n: int = 4, cursor: int = 0) -> list[dict]:
    """搜狗微信对频率很敏感：默认一次只跑 1 个关键词，靠 cursor 轮换。"""
    client = SogouWechat()
    out = []
    queries = [WECHAT_QUERIES[(cursor + i) % len(WECHAT_QUERIES)] for i in range(limit_queries)]
    for idx, q in enumerate(queries):
        if idx:
            time.sleep(8)
        try:
            rows = client.search(q)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 搜狗微信「{q}」失败：{exc}", file=sys.stderr)
            break
        hits = [r for r in rows if not is_noise(r["title"]) and hit_keyword(r["title"], r["summary"])]
        print(f"  · 搜狗微信「{q}」: {len(rows)} 条 → 命中 {len(hits)}")
        for r in hits[:resolve_n]:
            if r["ts"] and (date.today() - datetime.fromtimestamp(int(r["ts"])).date()).days > 60:
                continue
            real = client.resolve(r["link"], r["referer"])
            url = real or (client.BASE + r["link"])
            dt = datetime.fromtimestamp(int(r["ts"])).date().isoformat() if r["ts"] else date.today().isoformat()
            kw = hit_keyword(r["title"], r["summary"]) or ""
            rec = candidate(
                r["account"] or "微信公众号", r["title"], url, dt,
                summary=(r["summary"] or f"公众号「{r['account']}」文章，命中关键词「{kw}」，需打开原文核实。"),
            )
            rec["tags"] = ["公众号"]
            rec["via"] = "搜狗微信"
            out.append(rec)
            time.sleep(1.5)
        time.sleep(2.0)
    return out


# ---------------------------------------------------------------- 360 索引层（脉脉 / 微博 / 36 氪）

def resolve_so_link(link: str) -> str | None:
    try:
        page = fetch(link, referer="https://www.so.com/")
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r'window\.location\.replace\("([^"]+)"', page) or re.search(r"URL='([^']+)'", page)
    return m.group(1) if m else None


def parse_maimai_article(url: str) -> dict:
    h = fetch(url)
    m = re.search(r"<title>(.*?)</title>", h, re.S) or re.search(r'property="og:title" content="([^"]+)"', h)
    title = text_of(m.group(1)).replace(" - 脉脉", "").strip() if m else ""
    if not title or title.lower() == "add-friend":
        m = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
        title = text_of(m.group(1)).strip() if m else title
    t = re.sub(r"<script.*?</script>", "", h, flags=re.S)
    t = re.sub(r"<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = htmllib.unescape(t)
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    dt = ""
    author = ""
    mj = re.search(r'"time":"(\d{4}-\d{2}-\d{2})', h)
    if mj:
        dt = mj.group(1)
    for i, line in enumerate(lines):
        if dt and author:
            break
        m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:\s*·\s*(.*))?$", line)
        m1 = re.match(r"^(\d{2})-(\d{2})(?:\s*·\s*(.*))?$", line)
        if m2:
            dt = dt or f"{m2.group(1)}-{int(m2.group(2)):02d}-{int(m2.group(3)):02d}"
            author = lines[i - 1] if i >= 1 else ""
            break
        if m1 and i > 0 and len(lines[i - 1]) < 30:
            mm, dd = int(m1.group(1)), int(m1.group(2))
            year = date.today().year if mm <= date.today().month else date.today().year - 1
            dt = dt or f"{year}-{mm:02d}-{dd:02d}"
            author = lines[i - 1]
            break
        m3 = re.match(r"^(\d{2})-(\d{2})-(\d{2})(?:\s*·.*)?$", line)
        if m3 and i > 0 and len(lines[i - 1]) < 30:
            dt = dt or f"20{m3.group(1)}-{m3.group(2)}-{m3.group(3)}"
            author = lines[i - 1]
            break
    body = [l for l in lines if len(l) > 24 and l not in (title,)][:4]
    summary = " ".join(body)[:150] or "脉脉文章，需打开原文核实。"
    return {"title": title, "date": dt, "author": author, "summary": summary}


def cand_from_buzz(limit_queries: int = 2, cursor: int = 0) -> list[dict]:
    out: list[dict] = []
    queries = [BUZZ_QUERIES[(cursor + i) % len(BUZZ_QUERIES)] for i in range(limit_queries)]
    for idx, (q, label) in enumerate(queries):
        if idx:
            time.sleep(4)
        try:
            page = fetch("https://www.so.com/s?q=" + urllib.parse.quote(q))
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 360「{q}」失败：{exc}", file=sys.stderr)
            continue
        blocks = re.findall(r'<li class="res-list"(.*?)</li>', page, re.S)
        hits = 0
        for b in blocks:
            mt = re.search(r"<h3[^>]*>(.*?)</h3>", b, re.S)
            mu = re.search(r'href="([^"]+)"', b)
            if not (mt and mu):
                continue
            title = text_of(re.sub(r"<!--.*?-->", "", mt.group(1)))
            if is_noise(title) or not hit_keyword(title):
                continue
            if re.search(r"请教|请问|提问|怎么|如何|吗？|\?|？$", title) or len(title) < 12:
                continue
            real = resolve_so_link(htmllib.unescape(mu.group(1)))
            if not real:
                continue
            dt = date.today().isoformat()
            summary = ""
            author = ""
            if label == "脉脉":
                try:
                    info = parse_maimai_article(real)
                    title = info["title"] or title
                    dt = info["date"] or date.today().isoformat()
                    author = info["author"]
                    summary = info["summary"]
                except Exception:  # noqa: BLE001
                    pass
                if not summary:
                    summary = "脉脉文章，需打开原文核实。"
            elif label == "微博":
                title = re.sub(r"^#?[^#]*#\s*", "", title).strip()
                title = re.sub(r"\s*-\s*微博$", "", title).strip()
                title = re.sub(r"^来自", "", title)
                summary = "微博博文（登录后可见全文），标题即爆料信息。"
            rec = candidate(label, title, real, dt, summary=summary,
                            extra={"tags": [label, "待复核"], "author": author})
            rec["confidence"] = "rumor"
            hits += 1
            out.append(rec)
        print(f"  · 360「{q}」: {len(blocks)} 条 → 命中 {hits}")
        time.sleep(2)
    return out


# ---------------------------------------------------------------- Hacker News（Algolia）

def cand_from_hn(days: int = 7) -> list[dict]:
    import time as _time
    out: list[dict] = []
    since = int(_time.time()) - days * 86400
    for q in HN_QUERIES:
        url = ("https://hn.algolia.com/api/v1/search_by_date?query=" + urllib.parse.quote(q)
               + "&tags=story&hitsPerPage=20&numericFilters=created_at_i%3E" + str(since))
        try:
            data = json.loads(fetch(url))
        except Exception as exc:  # noqa: BLE001
            print(f"  ! HN「{q}」失败：{exc}", file=sys.stderr)
            continue
        hits = data.get("hits") or []
        kept = 0
        for h in hits:
            title = (h.get("title") or "").strip()
            if not title:
                continue
            blob = title.lower()
            if not re.search(r"ai|openai|anthropic|deepmind|meta|google|microsoft|nvidia|xai|claude|gpt|gemini|layoff|laid off|hire|quit|resign", blob):
                continue
            if not re.search(r"layoff|laid off|hire|hiring|quit|resign|depart|leave|job|staff|worker|team", blob):
                continue
            dt = date.fromtimestamp(h.get("created_at_i") or 0).isoformat()
            link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
            kind = "layoff" if re.search(r"layoff|laid off", blob) else "sentiment"
            out.append({
                "status": "candidate",
                "origin": "Hacker News",
                "date": dt,
                "type": kind,
                "company": "other",
                "to_company": None,
                "person": {"name": "", "role": ""},
                "title": title[:90],
                "summary": f"HN 讨论（{h.get('points', 0)} points, {h.get('num_comments', 0)} comments）：{title}",
                "quote": title[:80],
                "confidence": "rumor",
                "source": {"name": "Hacker News", "url": link},
                "tags": ["海外", "HN"],
            })
            kept += 1
        print(f"  · HN「{q}」: {len(hits)} 条 → 命中 {kept}")
        time.sleep(1.5)
    return out


# ---------------------------------------------------------------- Blind（海外职场匿名社区）

def cand_from_blind(limit_channels: int = 3, posts_per_channel: int = 4, cursor: int = 0) -> list[dict]:
    out: list[dict] = []
    chans = [BLIND_CHANNELS[(cursor + i) % len(BLIND_CHANNELS)] for i in range(limit_channels)]
    for chan in chans:
        try:
            page = fetch(f"{BLIND_BASE}/channels/{chan}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! Blind/{chan} 拉取失败：{exc}", file=sys.stderr)
            continue
        links = list(dict.fromkeys(re.findall(r'href="(/post/[^"]+)"', page)))[:posts_per_channel]
        print(f"  · Blind/{chan}: {len(links)} 个帖子")
        for link in links:
            try:
                post = fetch(BLIND_BASE + link)
            except Exception:  # noqa: BLE001
                continue
            m_title = re.search(r"<title>(.*?)</title>", post, re.S)
            title = text_of(m_title.group(1)).replace(" | Blind", "").strip() if m_title else ""
            m_desc = re.search(r'<meta name="description" content="([^"]*)"', post, re.S)
            body = htmllib.unescape(m_desc.group(1)).replace("\n", " ").strip() if m_desc else ""
            if not title or len(title) < 8:
                continue
            blob = (title + " " + body).lower()
            if re.search(r"wife|husband|toddler|dating|commute|landlord|rent\b", blob):
                continue
            ai_company_chan = chan in ("openai", "anthropic", "google", "meta", "microsoft", "nvidia", "amazon")
            if not ai_company_chan and not re.search(r"openai|anthropic|deepmind|google|\bmeta\b|microsoft|nvidia|amazon|aws|xai|grok|claude|gpt|copilot|gemini|layoff|laid off|buyout|severance|\bpip\b", blob):
                continue
            kind = "layoff" if re.search(r"layoff|laid off|buyout|severance|\bpip\b", blob) else "sentiment"
            out.append({
                "status": "candidate",
                "origin": "Blind",
                "date": date.today().isoformat(),
                "type": kind,
                "company": "other",
                "to_company": None,
                "person": {"name": "", "role": ""},
                "title": title[:90],
                "summary": (body[:150] or "Blind 匿名帖，需打开原帖核实。"),
                "quote": body[:80],
                "confidence": "rumor",
                "source": {"name": f"Blind · {chan}", "url": BLIND_BASE + link},
                "tags": ["海外职场", "Blind", chan],
            })
            time.sleep(1.2)
        time.sleep(1.5)
    return out


# ---------------------------------------------------------------- 合并

def norm_key(rec: dict) -> str:
    raw = re.sub(r"\s+", "", (rec.get("title") or "")) + "|" + (rec.get("person", {}).get("name") or "")
    return raw.lower()


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["all", "dinq", "rss", "rsshub", "wechat", "latepost", "zhihu", "buzz", "blind", "hn"],
                    default="all")
    ap.add_argument("--list", action="store_true", help="打印 inbox 现有候选")
    ap.add_argument("--wechat-queries", type=int, default=1, help="每次跑几个公众号关键词（默认 1，避免验证码）")
    ap.add_argument("--buzz-queries", type=int, default=2, help="每次跑几个 360 索引关键词（默认 2）")
    ap.add_argument("--blind-channels", type=int, default=3, help="每次跑几个 Blind 频道（默认 3，轮换）")
    args = ap.parse_args()

    box = load_json(INBOX, {"updated": "", "candidates": []})
    cands = box.get("candidates", [])

    if args.list:
        for c in cands:
            print(f'{c.get("date")} [{c.get("origin")}] {c.get("title")}  {c.get("source", {}).get("url", "")[:80]}')
        print(f"\n共 {len(cands)} 条候选")
        return

    existing = {norm_key(c) for c in cands}
    existing |= {norm_key(i) for i in load_json(ITEMS, {"items": []}).get("items", [])}
    fresh: list[dict] = []

    if args.source in ("all", "dinq"):
        print("→ talent.dinq.me")
        try:
            got = cand_from_dinq(parse_dinq(fetch(DINQ_URL)))
            print(f"  · 解析 → {len(got)} 条可用")
            fresh += got
        except Exception as exc:  # noqa: BLE001
            print(f"  ! dinq 失败：{exc}", file=sys.stderr)

    if args.source in ("all", "rss"):
        print("→ RSS")
        fresh += cand_from_rss()

    if args.source in ("all", "rsshub"):
        print("→ RSSHub")
        fresh += cand_from_rsshub()

    if args.source in ("all", "latepost"):
        print("→ 晚点")
        try:
            fresh += cand_from_latepost()
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 晚点失败：{exc}", file=sys.stderr)

    if args.source in ("all", "zhihu"):
        print("→ 知乎热榜")
        try:
            fresh += cand_from_zhihu()
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 知乎失败：{exc}", file=sys.stderr)

    if args.source in ("all", "buzz"):
        print("→ 360 索引（脉脉 / 微博 / 36 氪）")
        state = box.setdefault("buzz", {"cursor": 0})
        fresh += cand_from_buzz(limit_queries=args.buzz_queries, cursor=state.get("cursor", 0))
        state["cursor"] = (state.get("cursor", 0) + args.buzz_queries) % len(BUZZ_QUERIES)

    if args.source in ("all", "hn"):
        print("→ Hacker News（layoffs / hires）")
        fresh += cand_from_hn()

    if args.source in ("all", "blind"):
        print("→ Blind（海外职场匿名社区）")
        state = box.setdefault("blind", {"cursor": 0})
        fresh += cand_from_blind(limit_channels=args.blind_channels, cursor=state.get("cursor", 0))
        state["cursor"] = (state.get("cursor", 0) + args.blind_channels) % len(BLIND_CHANNELS)

    if args.source in ("all", "wechat"):
        print("→ 公众号（搜狗微信）")
        state = box.setdefault("wechat", {"cursor": 0})
        fresh += cand_from_wechat(limit_queries=args.wechat_queries, cursor=state.get("cursor", 0))
        state["cursor"] = (state.get("cursor", 0) + args.wechat_queries) % len(WECHAT_QUERIES)

    added = 0
    for c in fresh:
        k = norm_key(c)
        if k in existing:
            continue
        existing.add(k)
        cands.append(c)
        added += 1

    box["updated"] = date.today().isoformat()
    box["candidates"] = cands
    INBOX.write_text(json.dumps(box, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 新增 {added} 条候选，inbox 共 {len(cands)} 条 → {INBOX}")
    print("  下一步：逐条核实后写进 research/*.jsonl，或直接补进 scripts/curate.py 的 EXTRA_ITEMS")


if __name__ == "__main__":
    main()
