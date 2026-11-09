# AIFlow 日常采集与更新

用户安排：北京时间周一至周五 09:30 扫描信息源，周末不运行。2026-11-06 决定先试运行不登录 Codex CLI 的方式：采集自动进行，候选由人工核查后入库。不得把“候选已采集”称为“新闻已更新”。

## 位置与定时

项目入口 `/Users/wz/Desktop/超级周报服务器/aiflow-site` 是指向 `/Users/wz/aiflow-site` 的符号链接。后台任务使用后者，避开 macOS 对 Desktop 的后台访问限制。此目录通过 GitHub API 发布，目前没有 `.git`，不要误用旧架构，也不要执行假定存在工作树的 reset/checkout。

`~/Library/LaunchAgents/com.aiflow.site.plist` 调用 `scripts/daily.sh` → `scripts/daily.py`。系统日历设置五个工作日 09:30，脚本按 Asia/Shanghai 再检查周末，并持有进程锁。Mac 系统时区应为 Asia/Shanghai；电脑需开机、登录并保持唤醒。X 需要用户已经登录的 Chrome 和允许 Apple 事件 JavaScript。当前试运行不依赖 Codex CLI 登录。

## 自动采集

依次运行 X 55 个启用账号、媒体 RSS、手动链接收件箱、DINQ、扩展 RSS、RSSHub、晚点、知乎、HN、Blind 和公开搜索索引。媒体 RSS 采集除人事关键词外，也按并购、治理、政策选举关键词收标题，候选条目标注 `kind`（personnel／event），两类都要过一遍。媒体窗口至少四天，并按上次巡检时间加 48 小时重叠，覆盖周末；X 原采集器最多回补七天，公开时间线和 RSS 可能截断，不能宣称完整覆盖。

原文及候选仅写 `.private-inbox/`。逐源记录读取、失败、有限窗口和候选数量；采集器报错或超时不应显示成“没有新闻”。空手动链接收件箱是正常空结果。日志在 `logs/daily-YYYY-MM-DD.log`。任务把本轮覆盖写入 monitor 和 run-history，构建并测试通过后发布巡检状态；新候选仍待核查。

## 核查与入库

以 AI 人才流动、裁员、组织变化、员工公开观察为主，同时收录会改变人事与权力格局的重大事件：并购交易（含团队并入、收购后创始人去向）、治理风波（董事会调查、罢免、不当行为、监管处罚）、政策与选举（AI 监管、出口管制、听证、政治任命）。判断标准是它是否会牵动谁在什么位置上；只影响产品、估值或跑分的纯发布与评测仍不进入要闻。按既有数据类型与 context 范围收录，新增类型 `deal`（并购交易）、`governance`（治理风波）、`policy`（政策选举）。核对具体原帖或原始报道，保留公开日期、事件日期和信息的不确定性。聚合首页、个人主页、搜索摘要不构成事件证据；不要补写未经确认的职务、原因或去向。

`primary` 表示本人／官方原文，`reported` 表示已读媒体原文；均需具体来源、reviewed_at、review_note。未核实线索明确标记 `lead`，敏感传闻缺乏依据时先留私有候选。默认不自动晋升未证实线索。要闻少量线索和最近七天随机池遵守现有显示规则。

先按来源 URL，再按人物、公司、事件去重，同一事件增加来源而不重复建条目。保留已有 ID 和链接。摘要用中文，通常 60–140 字，不复制完整原文。不能把采集日期作为旧事件的报道日期。

## 检查与发布

运行 `python3 scripts/build.py`、`python3 -m unittest discover -s tests`、`node --check assets/app.js`、`node --check assets/theme.js`。任何检查失败都停止发布。

发布前核对远端 gh-pages SHA。`scripts/publish.py --expected-head <SHA> --verify` 使用当前远端树，保留其他远端文件，非强制快进；远端变化时停止，先同步。`.private-inbox/published-head` 保存上次发布 SHA，定时任务遇到不一致时停止，避免覆盖他人的更新。私有候选、原帖全文、日志和凭据不得发布。

发布完成需确认 GitHub Pages 构建对应提交成功，并比较线上首页、观察名单与本地内容。人工新增时还需打开新文章核对。只有实际上线的内容才能报告“已更新”。通知用户以有意义的新消息、更正或需要处理的运行失败为主。
