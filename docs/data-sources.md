# 信息源清单（2026-11-11 记）

这个项目能接的源，比报告里出现的那 13 个多。这份清单记着：**哪些在跑、哪些没开、开在哪、开一次大概多少钱**，方便以后做减法或者加回去。

报告里的 13 章由 `radar/report.py` 的 `SOURCES` 写死；每个源跑不跑，由 `config.json` 和每天那条调度命令里的 `--skip` 决定。

## 一、报告里在跑的 13 个

每天（6 个）：

| 报告章节 | 代码 | 数据来自 | 一次花费 |
|---|---|---|---|
| `# X` | `sources.x_new` | X 账号的帖子（`x_accounts`） | $0.012 |
| `# 竞品 sitemap` | `sitemaps.diff` | 你配的 sitemap，比对新增页面 | 0（普通 HTTP） |
| `# Product Hunt` | `feeds.producthunt` | Product Hunt GraphQL API 的 featured 发布（`PH_API_KEY`，没 key 退回 Atom feed） | 0（API 免费） |
| `# App Store` | `feeds.appstore` | App Store 新上架（`app_genres`） | 含在 $0.002 |
| `# TikTok 热搜` | `feeds.trending` | TikTok 热搜（`feeds.trending`） | 含在 $0.002 |
| `# Reddit` | `feeds.reddit_asks` | r/SomebodyMakeThis、r/AppIdeas 的新帖 RSS（`feeds.reddit_subs`） | 0（普通 HTTP） |

每周一（7 个）：

| 报告章节 | 代码 | 数据来自 | 一次花费 |
|---|---|---|---|
| `# 新站` | `new_sites.new_sites` | DataForSEO 域名库（`new_sites.queries`） | $0.409 |
| `# Google 新收录` | `feeds.google_new` | Figma 社区 / TAAFT / Chrome 商店 | 含在 $0.090 |
| `# 上升搜索` | `feeds.rising` | Trends 上升搜索（按 `feeds.seeds`） | 含在 $0.090 |
| `# TrustMRR 收入` | `revenue.products` | TrustMRR API | 0（免费 key） |
| `# 求助` | `asks.asks` | Reddit 搜索「找工具」的帖 | $0.150 |
| `# 收款链接` | `sellers.sellers` | Stripe / Polar / Gumroad 等新卖家 | $0.482 |
| `# 建站作品` | `sellers.builders` | v0 / beehiiv 刚建的站 | $0.166 |

花费是 2026-11-09（周一）和 2026-11-11（周三）两次实测，从 `report.json` 里按块加出来的，不是估价。

## 二、有代码、有章节，但调度命令用 `--skip` 关着

| 源 | 章节 | 关在哪 | 开法 |
|---|---|---|---|
| Hugging Face 新模型 | **没有章节**，只会在「先看这几个」和「主题」里出现 | 调度命令 `--skip hf` | 去掉 `hf`。想让它成章要改 `report.py` 的 `SOURCES` |
| GitHub 爆发 | `# GitHub 爆发` | `--skip breakout` | 去掉 `breakout` |
| 付费信号（AdSense / 投广告的词） | `# 付费信号` | `--skip money` | 去掉 `money`（周一才跑，`money.weekday = 0`） |

## 三、代码里有、配置没打开

| 源 | 代码 | 现在 | 开法 |
|---|---|---|---|
| Search Console | `gsc.gsc_new` | `gsc: {}`，空的 | 在 `gsc` 里配查询，配了才有 `# Search Console` 章节 |
| Show HN | `feeds.show_hn` | 没启用 | `feeds.enabled` 加 `"hn"` |
| OpenRouter | `feeds.openrouter` | 没启用 | 加 `"openrouter"` |
| Civitai | `feeds.civitai` | 没启用 | 加 `"civitai"` |
| awesome list | `feeds.awesome` | 没启用 | 加 `"awesome"` |
| 抖音热搜 | `feeds.TRENDING["douyin"]` | 没启用 | `feeds.trending` 加 `"douyin"` |
| TikTok 话题标签 | `feeds.TRENDING["tiktok_tags"]` | 没启用 | 加 `"tiktok_tags"` |
| 27 个官方实验室 X 账号 | `x_accounts.labs` | 现在是空的 | 把 `config.example.json` 里那份填回 `labs`（Anthropic / OpenAI / DeepMind / Qwen / DeepSeek…） |
| 另外 4 个站点 | `sitemaps` | 现在 8 个，示例 12 个 | 照 `config.example.json` 补 |

## 四、依赖别的信号才有内容（不用单独开）

| 章节 | 依赖 |
|---|---|
| `# 付费产品周边的搜索`（`sidelights.tails`） | ⑥ 收入和 ⑧ 卖家今天有名单，才有词可查 |
| `# 教程观众在要什么`（`pains.tutorial_asks`） | 线索里出现 ⚡（高赞帖在讲一套手动流程）才有得读 |
| `# 新名字的旁证`（`sidelights.evidence`） | **已下线**（2026-11-11，跟着新词表一起）；`config.json` 里 `sidelights.names` 设 0。见 [`parked.md`](parked.md) |
| `# 主题`（`topic_lines`） | **已下线**（2026-11-11）：单源命中时只是重复别的章节。见 [`parked.md`](parked.md) |
| `# 复盘`（`review.review`） | 14 天前报出的词到期才读，不用开关 |

## 五、已下线

- **新词表**（`usecases`）：2026-11-11 下线，`per_day` 设 0。原因、开关、重启条件见 [`parked.md`](parked.md)。

## 不属于「源」的模块

`competition`、`wordage`、`markets`、`serpshape`、`dotcom`、`yours`、`curve`、`ai_answers` 这些是给词**补数据**的（首页竞争、域名年龄、多国搜索量…），不产词，所以不算源：

- `competition`（首页竞争）周一跑「求助」时也在用；
- `ai_answers`（AI 回答里点名了谁）属于「求助」的附加列；
- 其余 `wordage` / `markets` / `serpshape` / `dotcom` / `yours` / `curve` 只被新词表调用，**跟着新词表一起停了**，重启新词表时会自动回来。

## 做减法从哪下手

要砍就砍**第一节那 13 个**——只有它们在花钱。第二、三节是「存在但没开机」，不开就不花钱；第四节是依赖型，砍了上游它自己就没了。
