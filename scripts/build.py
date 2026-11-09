#!/usr/bin/env python3
"""Build the complete AIFLOW publication from reviewed, versioned source data."""
from pathlib import Path
from html import escape
from urllib.parse import quote, urlsplit
from datetime import datetime, date, timedelta
from collections import Counter
import json, hashlib, re
from schedule_config import SCHEDULE

ROOT=Path(__file__).resolve().parents[1]
BASE='https://shrekwang-netizen.github.io/aiflow-site/'
TYPES={'join':'加入','departure':'离开','hiring':'招聘','reorg':'组织调整','layoff':'裁员','deal':'并购交易','governance':'治理风波','policy':'政策选举','rumor':'传闻','sentiment':'从业者观察','opinion':'观点'}
STATUS={'primary':'本人／官方公开','reported':'媒体报道 · 原文已读','unreviewed':'历史记录 · 待复核','lead':'线索 · 未证实'}
CHECKED={'primary','reported'}
def load(name): return json.loads((ROOT/'data'/name).read_text())
def h(s): return escape(str(s),quote=True)
def eligible(r): return r['status'] in CHECKED and r['scope']=='talent' and r['type'] not in ('rumor','opinion','sentiment')
def validate(records):
    ids=set(); allowed=set(STATUS)
    for r in records:
        assert re.fullmatch(r'[a-z0-9][a-z0-9-]*',r['id']), 'Invalid id'
        assert r['id'] not in ids, 'Duplicate id'; ids.add(r['id'])
        date.fromisoformat(r['date']); assert r['type'] in TYPES
        assert r['status'] in allowed and r['scope'] in ('talent','context')
        assert r['title'].strip() and r['summary'].strip()
        for source in r['sources']:
            u=urlsplit(source['url']); assert u.scheme in ('https','http') and u.netloc, 'Source must be an HTTP(S) URL'
        if r['status'] in CHECKED:
            assert r.get('reviewed_at') and r.get('review_note') and r['sources'], 'Reviewed record requires evidence'
            date.fromisoformat(r['reviewed_at'])
            for s in r['sources']:
                u=urlsplit(s['url']); assert u.scheme=='https', 'Reviewed source must use HTTPS'
                assert not (u.hostname in ('x.com','twitter.com') and not re.fullmatch(r'/[^/]+/status/\d+',u.path)), 'X evidence must be a specific post'
                assert u.hostname!='talent.dinq.me', 'Aggregation alone cannot verify a record'
        assert not (r['status'] in CHECKED and r['type']=='rumor'), 'Unverified rumors cannot be published as checked'

def build():
    records=sorted(load('records.json'),key=lambda r:(r['date'],r['id']),reverse=True);validate(records)
    accounts=[a for a in load('x-watchlist.json')['accounts'] if a['enabled']]
    monitor=load('monitor.json'); paths=load('legacy-paths.json'); checked=[r for r in records if eligible(r)]
    stamp=datetime.fromisoformat(monitor['checked_at']); date_label=stamp.strftime('%Y.%m.%d'); checked_label=stamp.strftime('%m.%d %H:%M')
    version=hashlib.sha256(b''.join((ROOT/'assets'/x).read_bytes() for x in ('style.css','app.js','theme.js'))).hexdigest()[:10]
    manifest=[]
    def link(path,label,cls=''): return f'<a class="{cls}" href="{h(path)}">{label}</a>'
    def external(url,label): return f'<a href="{h(url)}" target="_blank" rel="noopener noreferrer">{h(label)} <span aria-hidden="true">↗</span></a>'
    logo='<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M4 24 15 8l7 16 6-9"/><circle cx="4" cy="24" r="2"/><circle cx="15" cy="8" r="2"/><circle cx="22" cy="24" r="2"/></svg>'
    def shell(path,title,body,active='home',description='关注 AI 人才、团队与组织的变化。保留具体来源，区分已核对报道与待核线索。'):
        prefix='../' if '/' in path else ''
        nav=''.join(f'<a href="{prefix}{url}"'+(' aria-current="page"' if key==active else '')+f'>{label}</a>' for key,url,label in [('home','index.html','要闻'),('rumors','rumors.html','小道消息'),('watch','watchlist.html','X 观察名单'),('random','random.html','随机周报')])
        theme=''.join(f'<button type="button" data-set-theme="{m}" aria-label="{label}" title="{label}" aria-pressed="false">{glyph}</button>' for m,label,glyph in [('light','浅色','☀'),('auto','跟随系统','◐'),('dark','深色','☾')])
        html=f'''<!doctype html><html lang="zh-CN" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{h(title)} · AIFLOW</title><meta name="description" content="{h(description)}"><meta property="og:title" content="{h(title)} · AIFLOW"><meta property="og:description" content="{h(description)}"><meta property="og:type" content="website"><meta property="og:locale" content="zh_CN"><link rel="canonical" href="{BASE}{quote(path)}"><meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'"><meta name="referrer" content="strict-origin-when-cross-origin"><meta name="theme-color" content="#f5f3ec"><link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml"><link rel="alternate" type="application/rss+xml" title="AIFLOW 人才要闻" href="{prefix}feed.xml"><script src="{prefix}assets/theme.js?v={version}"></script><link rel="stylesheet" href="{prefix}assets/style.css?v={version}"></head><body>
<a class="skip" href="#main">跳到正文</a><div class="site-wrap"><header class="masthead"><a class="brand" href="{prefix}index.html" aria-label="AIFLOW 首页">{logo}<span>aiflow<span class="brand-dot">.</span></span></a><span class="brand-caption">AI TALENT<br>OBSERVATORY</span><div class="masthead-right"><a class="saved-link" href="{prefix}all.html?saved=1">我的收藏 <span aria-hidden="true">↗</span></a><div class="theme-switch" role="group" aria-label="配色">{theme}</div></div></header><div class="navline"><nav aria-label="主导航">{nav}</nav><a class="method-link" href="{prefix}about.html">关于与方法 ↗</a></div><main id="main">{body}</main><footer><div><a class="footer-brand" href="{prefix}index.html">aiflow.</a><p>追踪 AI 圈的人与权力流向，保留事实的来处。</p></div><div class="footer-links"><a href="{prefix}all.html">全部记录</a><a href="{prefix}watchlist.html">X 观察名单</a><a href="{prefix}about.html">编辑方法</a><a href="{prefix}feed.xml">RSS</a><a href="{prefix}random.html">随机回顾</a><a href="https://github.com/Shrekwang-netizen/aiflow-site/issues">提交更正 ↗</a></div><p class="footer-note">个人维护 · 日期以原始报道为准<br>最近巡检 {h(date_label)} · 北京时间</p></footer></div><script src="{prefix}assets/app.js?v={version}"></script></body></html>'''
        target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(html+'\n');manifest.append(path)
    def badges(r): return f'<span class="event-type">{TYPES[r["type"]]}</span><span class="confidence {r["status"]}">{STATUS[r["status"]]}</span>'
    def card(r,prefix='',hidden=False):
        co=r['companies'][0]
        return f'''<div class="feed-item"{' hidden' if hidden else ''} data-id="{h(r['id'])}" data-type="{r['type']}" data-quality="{r['status']}"><article class="card"><div class="card-top"><div class="chips">{badges(r)}</div><button type="button" class="save-btn" data-fav="{h(r['id'])}" aria-label="收藏" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4Z"/></svg></button></div><h3><a href="{prefix}item/{h(r['id'])}.html">{h(r['title'])}</a></h3><p class="card-sum">{h(r['summary'])}</p><div class="card-bottom"><a class="company-label" href="{prefix}company/{h(co['slug'])}.html">{h(co['name'])}</a><time datetime="{r['date']}">{r['date'].replace('-','.')}</time><span>{len(r['sources'])} 个来源</span></div><div class="source-inline">{external(r['sources'][0]['url'],r['sources'][0]['name']) if r['sources'] else '暂缺具体来源'}</div></article></div>'''
    def search(filters=True, default_quality='all'):
        buttons=''.join(f'<button type="button" data-filter-type="{k}" aria-pressed="false">{v}</button>' for k,v in [('all','全部类型')]+list(TYPES.items())) if filters else ''
        checked=' selected' if default_quality=='checked' else ''
        return f'<div class="toolbar"><label class="search"><span aria-hidden="true">⌕</span><input type="search" data-search aria-label="搜索记录" placeholder="搜索人物、公司、关键词"><kbd>⌘ K</kbd></label><label class="quality-label">来源状态<select data-quality-filter data-default-quality="{default_quality}" aria-label="来源状态"><option value="all">全部状态</option><option value="checked"{checked}>已核对</option><option value="primary">本人／官方公开</option><option value="reported">已读媒体报道</option><option value="unreviewed">历史待复核</option><option value="lead">未证实线索</option></select></label></div><div class="type-filters">{buttons}</div>'
    def feed(rows,prefix='',feature=False,hide_unchecked=False):
        if not rows:return '<div class="empty">这个栏目还没有记录。<a href="'+prefix+'all.html">浏览全部记录 →</a></div>'
        cards=''.join(card(r,prefix,hidden=hide_unchecked and r['status'] not in CHECKED) for r in rows)
        return f'<div class="feed {"feature-feed" if feature else ""}" data-feed>'+cards+'</div><p class="empty" data-empty hidden>没有符合条件的记录。</p>'
    def heading(title,sub,eyebrow='THE PEOPLE BEHIND AI'):
        return f'<header class="page-head"><p class="eyebrow">{eyebrow}</p><h1>{h(title)}</h1><p class="page-sub">{sub}</p></header>'
    def monitor_panel():
        enabled=monitor.get('automation_enabled',False)
        return f'''<aside class="monitor-panel"><div class="panel-kicker"><span class="status-dot"></span> X 观察站</div><p class="monitor-count">{len(accounts)}<span> 个公开账号</span></p><p>研究者、实验室、报道者。<br>把信息追溯到具体原帖。</p><dl><div><dt>最近巡检</dt><dd>{checked_label}</dd></div><div><dt>更新安排</dt><dd>{h(monitor.get('schedule', SCHEDULE)) if enabled else '正在配置'}</dd></div></dl><a href="watchlist.html">查看名单与覆盖情况 <span>↗</span></a></aside>'''
    recent_cut=(stamp.date()-timedelta(days=14)).isoformat()
    quality=[r for r in records if r['status']=='lead' and r['type']=='rumor' and r['scope']=='talent' and r['date']>=recent_cut][:2]
    home=f'''<section class="hero"><div><p class="eyebrow">THE PEOPLE BEHIND AI <span>独立人才观察</span></p><h1>技术向前，<br>人才流动。</h1><p class="hero-copy">谁加入了新团队，谁选择了下一站。<br>关注 AI 行业里的人，也关注他们正在改变的组织。</p><a class="text-link" href="all.html">查看全部记录 <span>↗</span></a></div>{monitor_panel()}</section><section class="section-intro"><div><p class="eyebrow">EDITOR’S DESK</p><h2>近期要闻</h2></div><p>已核对具体原文的人才记录，另附少量待核实线索，均标注信度。<br>按报道日期排序，不用热度代替事实。</p></section>{feed(sorted(checked[:9]+quality,key=lambda r:r['date'],reverse=True),feature=True)}'''
    history=[r for r in records if r['status']=='unreviewed' and r['scope']=='talent'][:5]
    home+='<section class="archive-preview"><div class="section-intro"><div><p class="eyebrow">FROM THE ARCHIVE</p><h2>历史资料</h2></div><a href="all.html?quality=unreviewed">查看全部 →</a></div><p class="section-note">以下来自原站收录，尚未完成本轮原文复核，不作为已确认要闻。</p>'
    home+=''.join(f'<a class="archive-row" href="item/{r["id"]}.html"><time>{r["date"][5:].replace("-",".")}</time><span>{h(r["title"])}</span><b>待复核 ↗</b></a>' for r in history)+'</section>'
    shell('index.html','AI 人才观察',home)
    archive_head=heading('全部记录','默认展示已核对记录（本人／官方公开、媒体原文已读）。用「来源状态」可切换到历史待复核与未证实线索；收藏和未读记录只保存在当前浏览器。','THE ARCHIVE')
    shell('all.html','全部记录',archive_head+search(default_quality='checked')+feed(records,hide_unchecked=True),'all')
    leads=[r for r in records if r['status']=='lead']
    shell('rumors.html','小道消息',heading('小道消息，先不下结论。','传闻、聚合页与缺少具体原文的历史记录放在这里。补齐证据后，再决定是否进入要闻。','THE REVIEW QUEUE')+search()+feed(leads),'rumors')
    watch=heading('从这些人，听见行业。','这是一份公开账号观察名单，不是背书或排名。优先阅读一手发言，再用官方公告和原始报道交叉核对。','THE WATCHLIST')
    watch+=f'<div class="watch-summary"><b>{len(accounts)} 个账号</b><span>{h(monitor.get("schedule", SCHEDULE))}</span><a href="docs/x-watchlist.md">下载文字版名单 ↗</a></div>'
    for group in dict.fromkeys(a['group'] for a in accounts):
        watch+=f'<section class="watch-group"><h2>{h(group)}</h2><div class="watch-grid">'
        for a in accounts:
            if a['group']!=group:continue
            watch+=f'<a class="watch-card" href="{a["url"]}" target="_blank" rel="noopener noreferrer"><span class="watch-initial">{h(a["name"][0])}</span><div><h3>{h(a["name"])}</h3><p class="handle">@{a["handle"]}</p><p>{h(a["focus"])}</p></div><span class="out-arrow">↗</span></a>'
        watch+='</div></section>'
    watch+=f'<section class="coverage"><p class="eyebrow">LAST CHECK · {date_label}</p><h2>最近一次查阅</h2><p>{h(monitor["summary"])}</p><p>成功读取 {len(monitor["accounts_checked"])} 个账号，未能读取 {len(monitor["accounts_failed"])} 个。公开时间线可能只展示部分帖子；访问受限时会保留缺口，不把“没读到”写成“没有消息”。</p><p>新内容须附具体原帖或报道、公开日期、人物与团队，并经过来源核对。没有合格新消息时，全部记录保持不变，只更新巡检记录。</p><a href="about.html">了解编辑标准 →</a></section>'
    if monitor.get('source_coverage'):
        labels={'x':'X 观察名单','news':'媒体 RSS','links':'手动链接','legacy':'DINQ 与其他信息源'}
        states={'read':'已读取有限窗口','partial':'部分读取／存在缺口','failed':'读取失败','empty':'无待处理链接'}
        watch+='<section class="coverage"><h2>本轮信息源覆盖</h2><p>采集结果先进入待核候选；试运行阶段由人工核查后更新新闻。</p><ul>'
        for row in monitor['source_coverage']:
            watch+=f'<li>{h(labels.get(row["source"],row["source"]))}：{h(states.get(row["status"],row["status"]))}，{row.get("candidates",0)} 条候选'
            details=row.get('details',[])
            if details:
                watch+='；'+h('、'.join(f'{d["source"]} {d.get("count",0)} 条'+('（有失败）' if d.get('error') else '') for d in details))
            if row.get('warnings'):
                watch+='；'+h('；'.join(row['warnings']))
            watch+='</li>'
        watch+='</ul></section>'
    shell('watchlist.html','X 观察名单',watch,'watch')
    about=heading('把来源，放在结论前面。','AIFLOW 是个人维护的 AI 人才、组织与治理观察站。','OUR EDITORIAL NOTES')+'''<div class="prose"><h2>我们收录什么</h2><p>一、人才流动：研究人员与管理者的加入、离开、创业，团队招聘、裁员与组织调整。</p><p>二、会改变人事与权力格局的重大事件：并购交易（含团队并入、收购后创始人去向）、治理风波（董事会调查、罢免、不当行为、监管处罚）、政策与选举（AI 相关的监管、出口管制、听证、政治任命）。判断标准是它是否会牵动谁在什么位置上；只影响产品、估值或跑分、不改变人员与权力结构的新闻仍不进入要闻。</p><p>不收录：纯模型发布、跑分、产品评测与观点，以及不涉及团队安排的单轮融资数字。有保留价值的观察留在全部记录。</p><h2>四种来源状态</h2><dl class="standards"><div><dt>本人／官方公开</dt><dd>已阅读当事人或机构的具体原文。只概括原文明确说明的信息，不推断薪酬、离职原因或未披露职务。</dd></div><div><dt>媒体报道 · 原文已读</dt><dd>已阅读相关报道，摘要注明报道方。报道不等同于公司或本人确认；单一媒体不会被标成“多家报道”。</dd></div><div><dt>历史记录 · 待复核</dt><dd>保留原站历史收录，尚未逐条重新核对。原来的 AI 分数、无依据热度与确认标签不再展示。</dd></div><div><dt>线索 · 未证实</dt><dd>匿名帖、传闻、搜索页、聚合首页或缺少具体原文的条目。不会进入要闻、RSS 和随机回顾。</dd></div></dl><h2>日期与更正</h2><p>列表日期是来源公开或报道的日期，不一定是实际入职、离职的日期。巡检时间与报道时间分别记录，旧闻不会因为重新抓取而变成今天的新消息。</p><h2>每日查阅怎么进行</h2><p>按 X 观察名单读取近期公开帖子，优先覆盖距离上次查阅以来的内容，并回看至少 48 小时；同时扫描中英文 AI 媒体 RSS，既收人事关键词，也收并购、治理与政策选举类标题，再逐条回原文核对。新线索核对原文、去重后才发布。无法读取、无法确定日期或只找到搜索摘要时，保留为待核线索，不自动升级为要闻。</p><p>任务运行于维护者的本地 Codex 环境，需要电脑与应用保持运行。公开页面、网络和登录状态会影响覆盖度；观察名单页记录最近一次实际查阅情况，不承诺全量实时覆盖。</p><h2>关于收藏和阅读记录</h2><p>这些偏好仅保存于当前浏览器，不需要账号，也不会跨设备同步。清理浏览器数据会重置记录。</p><h2>补充或纠正信息</h2><p>发现错误，请<a href="https://github.com/Shrekwang-netizen/aiflow-site/issues">提交更正</a>，附记录链接与公开依据。我们会保留更正说明，更新或撤下不再成立的表述。</p></div>'''
    shell('about.html','关于与编辑方法',about,'about')
    for r in records:
        prefix='../'; co=r['companies'][0]
        body=f'<div class="article-layout"><article class="article-main"><a class="back" href="../all.html">← 返回全部记录</a><div class="article-meta">{badges(r)}<time>{r["date"]}</time></div><h1>{h(r["title"])}</h1><p class="article-lede">{h(r["summary"])}</p><section class="evidence-note"><h2>来源核对说明</h2><p>{h(r["review_note"])}</p><p class="muted">'+(f'核对日期：{r["reviewed_at"]}' if r.get('reviewed_at') else '这条历史记录尚未完成原文复核。')+'</p></section><section class="source-section"><h2>回到原始来源</h2>'
        body+=''.join(f'<div class="source-item">{external(s["url"],s["name"])}<span>{h(urlsplit(s["url"]).hostname)}</span></div>' for s in r['sources']) or '<p>暂缺来源链接，等待补充。</p>'
        body+=f'</section></article><aside class="article-aside"><p class="eyebrow">RECORD DETAILS</p><dl><dt>相关团队</dt><dd><a href="../company/{co["slug"]}.html">{h(co["name"])}</a></dd><dt>事件类型</dt><dd>{TYPES[r["type"]]}</dd><dt>来源公开日期</dt><dd>{r["date"]}</dd></dl><button type="button" class="save-text" data-fav="{r["id"]}" aria-pressed="false">收藏这条记录</button><div class="tag-row">'+''.join(f'<a href="../tags/{quote(t)}.html">{h(t)}</a>' for t in r['tags'])+'</div><a class="correction" href="https://github.com/Shrekwang-netizen/aiflow-site/issues">提供补充或更正 ↗</a></aside></div>'
        shell('item/'+r['id']+'.html',r['title'],body,'all',r['summary'])
    company_map={c['slug']:c['name'] for r in records for c in r['companies']}
    for slug in set(paths['company'])|set(company_map):
        selected=[r for r in records if any(c['slug']==slug for c in r['companies'])]
        shell('company/'+slug+'.html',company_map.get(slug,slug),heading(company_map.get(slug,slug),'团队相关历史与新记录，核验状态逐条标注。')+search()+feed(selected,'../'),'all')
    all_tags=set(paths['tags'])|{t for r in records for t in r['tags']}
    for tag in all_tags:shell('tags/'+tag+'.html',tag,heading(tag,'与这个主题相关的记录。')+search()+feed([r for r in records if tag in r['tags']],'../'),'all')
    for day in set(paths['daily'])|{r['date'] for r in records}:
        shell('daily/'+day+'.html',day+' 日报',heading(day,'按来源公开日期归档，核验状态逐条标注。')+feed([r for r in records if r['date']==day],'../'),'all')
    weeks=set(paths['weekly'])|{date.fromisoformat(r['date']).strftime('%G-W%V') for r in records}
    weeklinks=''
    for week in sorted(weeks,reverse=True):
        selected=[r for r in records if date.fromisoformat(r['date']).strftime('%G-W%V')==week]
        published=[r for r in selected if eligible(r)]
        weeklinks+=f'<a class="archive-row" href="weekly/{week}.html"><time>{week}</time><span>{len(published)} 条已核对人才记录</span><b>查看 →</b></a>'
        shell('weekly/'+week+'.html',week+' 周报',heading(week+' 周报',f'本周 {len(published)} 条已核对人才记录。未核对内容可在全部记录里查阅。')+feed(published,'../'),'weekly')
    shell('weekly.html','往期周报',heading('每一周，留一个切片。','按 ISO 周归档，只展示已核对的人才记录。','THE WEEKLY ARCHIVE')+'<div class="week-archive">'+weeklinks+'</div>','weekly')
    shell('companies.html','团队索引',heading('团队索引','按公司与研究团队查阅历史记录。')+'<div class="index-grid">'+''.join(link('company/'+k+'.html',h(v)+' ↗') for k,v in sorted(company_map.items()))+'</div>','all')
    shell('tags.html','主题索引',heading('主题索引','从一个关键词开始。')+'<div class="tag-row">'+''.join(link('tags/'+quote(t)+'.html',h(t)) for t in sorted(all_tags))+'</div>','all')
    random_body = heading('抽一条','从最近 7 天的人才记录里随机抽一条。点按钮或按空格，再抽一签。','A MOMENT IN THE ARCHIVE')
    random_body += ('<div class="lottery" data-rr>'
                    '<p class="lottery-kicker"><span data-rr-count>正在装签</span><span class="lottery-tally" data-rr-tally hidden></span></p>'
                    '<p class="lottery-line" id="rr-line" aria-live="polite">正在抽…</p>'
                    '<p class="lottery-source" id="rr-source"></p>'
                    '<div class="lottery-actions"><button class="primary-button" type="button" data-rr-roll disabled><span data-rr-label>正在加载</span></button>'
                    '<span class="lottery-hint">按空格再抽一次</span></div></div>')
    shell('random.html','随机周报',random_body,'random')
    shell('404.html','页面未找到',heading('这条路暂时没有消息。','<a href="'+BASE+'">返回 AIFLOW 首页 →</a>'),'home')
    (ROOT/'assets/data/random.json').write_text(json.dumps([{'id':r['id'],'date':r['date'],'title':r['title'],'summary':r['summary'],'type':TYPES[r['type']],'company':r['companies'][0]['name'],'url':'item/'+r['id']+'.html','conf':STATUS[r['status']]} for r in records if r['scope']=='talent' and r['date']>=(stamp.date()-timedelta(days=7)).isoformat()],ensure_ascii=False)+'\n')
    rss='<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>AIFLOW 人才要闻</title><link>'+BASE+'</link><description>只收录已核对原文的 AI 人才与组织记录。</description>'
    for r in checked[:30]:rss+=f'<item><title>{h(r["title"])}</title><link>{BASE}item/{r["id"]}.html</link><guid>{BASE}item/{r["id"]}.html</guid><description>{h(r["summary"])}</description><pubDate>{datetime.fromisoformat(r["date"]).strftime("%a, %d %b %Y 00:00:00 +0800")}</pubDate></item>'
    (ROOT/'feed.xml').write_text(rss+'</channel></rss>\n')
    (ROOT/'data/build-manifest.json').write_text(json.dumps(sorted(manifest),ensure_ascii=False,indent=2)+'\n')
    print(f'Built {len(manifest)} pages; {len(checked)} reviewed talent stories; {len(accounts)} watched accounts.')
if __name__=='__main__': build()
