# 代码里的隐藏开关

`config.json` 决定**读哪些源**。这一层是写死在代码里的常量，决定**读到的东西能不能留下来**——它们不在配置里，也不会报错，只会让某些词、某些站、某些信号安静地消失。

按影响从大到小排。每一行都可以改，但都要动代码，不是改配置。

## 一、能不能进新词表（影响最大）

| 常量 | 值 | 位置 | 作用 | 坑 |
|---|---|---|---|---|
| `READ_KINDS` | `x, hf, breakout, newsite, revenue, seller` | `radar/usecases.py:559` | 只有这六类信号产出的名字会被拿去查关键词 | ⑨ Product Hunt / App Store / TikTok 热搜 **永远进不去**，不管分数多高 |
| `READ_MIN` | `0.8` | `radar/usecases.py:560` | 名字得分低于 0.8 不读 | 报告里 0.5 分也能显示，看着像候选，实际永远不会被查关键词（`judge.min_score` 是 0.5） |
| `ASKED_MAX` | `8` | `radar/usecases.py:83` | 一次 `keywords` 最多读 8 个名字 | 给 12 个，后 4 个静默丢掉 |

## 二、能不能进报告

| 常量 | 值 | 位置 | 作用 | 坑 |
|---|---|---|---|---|
| `SHOWN` | `20` | `radar/report.py:9` | 候选表最多显示 20 行 | 第 21 个起看不到，但仍在库里 |
| `OTHER_TERMS` | `15` | `radar/report.py:10` | 「其他上升词」最多列 15 个 | 同上 |
| `X_MIN_LIKES` | `100` | `radar/sources.py:25` | 一个名字只有**一个**账号提过时，要 100 赞才算数 | 两个账号提过可直接通过；冷门账号的好词会被丢 |
| `HF_TOP`, `HF_FETCH` | `50, 100` | `radar/sources.py:27` | HF 只看新进前 50 的模型（对比上一轮的前 100） | 排第 51–100 的不报 |
| `MIN_URLS` | `3` | `radar/sitemaps.py:34` | 一个词至少要出现在 **3 个**新增网址里 | 只加 2 个页的词不报 |
| `TOP`（sitemap） | `25` | `radar/sitemaps.py:35` | 每个站最多报 25 个上升词 | 长尾在 25 名之后的不报 |
| `DOMAIN_STOP` | `com/net/free/tool/…` | `radar/new_sites.py:31` | 从域名拆词时丢掉这些 | `aifree.com` 拆不出 `aifree` 这种名字 |
| `TOOLISH` | 工具词 + `trend/meme/viral/dance/edit/clip/reel` | `radar/feeds.py:44` | 热搜词的过滤 | 已放宽；**音频类仍会进来**（歌词、phonk） |
| `TOP`, `WORDS`, `SITES_MAX` | `20, 5, 10` | `radar/site_words.py:15-17` | 新站只报前 20 名的 5 个词，每次最多 10 个站 | 第 11 个站起这个月看不到 |
| `VIRAL`, `SHARE` | `1000`, `0.25` | `radar/opportunity.py:29-30` | ⚡ 标记要 1000 赞；格式要在 25% 的帖子里出现 | 小众但真实的教程不会带 ⚡ |

## 三、判定阈值（影响数字和结论）

| 常量 | 值 | 位置 | 作用 | 坑 |
|---|---|---|---|---|
| `RISE_FACTOR`, `RISE_MIN` | `2.0`, `10` | `radar/review.py:27` | 峰值要超过自身基线 **2 倍**且高出 **10 点**才算「涨了」 | 温和上涨会被判成 miss，命中率偏低 |
| `BEFORE_DAYS`, `MAX_VARIANTS` | `30`, `3` | `radar/review.py:25-26` | 基线看 30 天；每个词最多查 3 个写法 | 第 4 个写法不参与复盘 |
| `MIN_PEAK`, `MIN_MONTHS` | `50`, `7` | `radar/curve.py:26-28` | 最高月不到 50 次搜索就写「搜索太少」；不足 7 个月不画走势 | 小词读不出曲线 |
| `CALIBRATE_MIN` | `1000` | `radar/usecases.py:79` | 只有月搜 ≥1000 的词参与基准词校准 | 词太小不参与，日搜估计的锚点会变 |
| `TRENDS_DAYS`, `RECENT_DAYS` | `90`, `7` | `radar/usecases.py:75` | 走势看 90 天；「近 7 天比前 7 天」 | — |
| `FORUMS_KEPT`, `DR_DAYS` | `5`, `30` | `radar/competition.py:40,48` | 首页论坛帖最多列 5 个；站点评分缓存 30 天 | 论坛帖超过 5 个不显示 |
| `PAGE_ONE`, `IMPROVE_MAX` | `10`, `30` | `radar/yours.py:25-26` | 前十算「在首页」；11–30 名算「该改进」 | 排 31 名以后算「新建页面」 |
| `brief.KINDS`, `brief.USES` | 8 种类型 / 3 种用法 | `radar/brief.py:23-24` | 模型只能从这些取值里选 | 模型答别的值会被强制成 generic / watch |

## 四、内置词表和名单

| 常量 | 值 | 位置 | 作用 | 坑 |
|---|---|---|---|---|
| `STOP` | 140 个词（`ai`、`agent`、`app`、`best`、`build`…） | `radar/terms.py:17` | 内置停用词，和配置里的 `stop_words` 叠加 | 名字里带这些词会被拆开或丢掉 |
| `DOMAIN_STOP` | 见上 | `radar/new_sites.py:31` | 域名专用停用词 | — |
| `NON_STORE`, `SHARED` | 平台页、社交与代码托管域名 | `radar/sellers.py:54,81` | 卖家信号里排除「不是卖家自己的页面」 | 挂在 GitHub/Reddit 上的收款链接不算 |
| `KINDS`, `KIND_RULES` | `ai/template/course/content/physical/other/donation` | `radar/sellers.py:85-86` | 卖家分类的取值和关键词规则 | 模型失败时按这套规则分类 |
| `FORUM` | reddit / quora / ycombinator / stackoverflow… | `radar/competition.py:47` | 哪些结果算「论坛模块」 | 没列进去的论坛不算 |
| `TAILS` | alternative / alternatives / vs / free / pricing / review | `radar/sidelights.py:33` | 付费产品查这 6 种搜索 | 固定 6 个，不加别的 |
| `LOCALES` | 22 种语言后缀 | `radar/serpshape.py:31` | 哪些 `/xx/` 前缀算多语言重复 | 不在列表里的语言会各算一个页面 |

## 五、上限与成本

| 常量 | 值 | 位置 | 说明 |
|---|---|---|---|
| `MAX_CALLS`, `BATCH` | `20`, `5` | `radar/aisa.py:28-29` | 一次批量调用最多 20 个工具、同时 5 个 |
| `TIMEOUT`, `CHAT_TIMEOUT` | `240`, `90` | `radar/aisa.py:30-31` | 数据调用 240 秒，模型调用 90 秒 |
| `NOTES_KEPT`, `SUMMARY_WINDOW` | `10`, `60` | `radar/store.py:22-23` | 每个词只留最近 10 条备注；命中率统计看 60 天 |
| `CHUNK`（judge / brief） | `25` / `15` | `radar/judge.py:18`、`radar/brief.py:21` | 一次模型调用处理多少个词 |

## 改的时候注意

- 这些全是常量，没有配置开关，改一行就要跑一遍测试：`python -m pytest -q tests`（当前 183 通过、2 跳过）。
- 优先级：先看 `READ_KINDS` 和 `READ_MIN`，它们决定「报告里看到的词有没有下文」；其次看第二节的 `SHOWN`、`TOOLISH` 这类，它们决定「你看到多少」。
- 第三节的阈值改完，历史数据不会重算——复盘命中率只对之后跑的词生效。
