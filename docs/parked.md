# 已下线、等重启的功能

功能先下线，代码不删。这里记着它为什么下线、关在哪、怎么开回来、开回来之前必须先发生什么。

## 新词表（2026-11-11 下线）

**它本来做什么**：每天挑几个新名字（`per_day`，默认 5），搜原帖拿证据，让模型从上下文里提出「通用写法」，筛相关性，再给每个写法和名字查 Trends、多国搜索量、首页竞争、域名年龄、.com、相关查询，最后出一张带「优先 / 观察 / 跳过」的表。

**为什么下线**：它选词的口径和我们要的东西对不上，而测量环节花了整次运行 98% 的钱。

- 入口写死在 `radar/usecases.py` 的 `READ_KINDS`：只认 `x / hf / breakout / newsite / revenue / seller` 六类信号。Product Hunt、App Store、TikTok 热搜、Reddit 求助、上升搜索产出的词**永远进不来**，分数再高也不行（`docs/hidden-defaults.md` 也记了这条）。
- 于是进来的一定是「AI 圈在转的模型名 / 技术名」，通用词又由这些名字的上下文提出来，结果全是开发者词。
- 2026-11-11 18:05 那次实测：3 个名字（`gemini 4 carbon`、`fable 5.2`、`3js`）、40 个写法、5 个相关、2 个过月搜。花 **$0.652，占当次 $0.666 的 97.9%**，而 5 行结果里 4 行是模型发布或开发者词，`3js` 还是 three.js 的缩写。同样的钱换成 6 个源头的罗列，几乎免费。

**现在关在哪**：

| 位置 | 状态 |
|---|---|
| `config.json`（以及两个 `config.example.json`） | `"usecases": {"per_day": 0}`，`radar/__main__.py` 见 0 直接跳过整步，不再花钱 |
| `radar/report.py` 的 `daily()` | 不再输出 `# 新词表` 章节（那两行删了） |
| `radar/usecases.py` | 原样保留：取证、提词、筛词、测量、决策 |
| `radar/report.py` 的 `keyword_table()` / `_word_lines()` / `_word_mark()` | 原样保留，报告不用它，单条查询还用 |
| `python -m radar keywords <名字…>` | 仍然可用：临时给某个名字做一次体检（按需付费，不写每日记录） |
| MCP 的 `keywords` 工具 | 仍然可用 |

**重启条件**（先满足这个，再开回来）：

> 信息源能稳定抓到「普通人在搜、小站做得动、能变现」的词。

具体要先做的改动：

1. **换入口**：把 `ask`（Reddit 求助）、`feed`（Product Hunt / App Store / 上升搜索）加进 `READ_KINDS`，让消费端产品名有资格当名字。
2. **加一票否决**：提词和筛词的提示里加一条「搜这个词的人是普通消费者吗？开发者/研究者的词直接丢」。
3. **先跑两周看正例**：每天 5 个名字的花费不变，但要能日复一日看到「这个词值得做页面」再说。

**开回来怎么开**：

1. `config.json` 里 `usecases.per_day` 设回 5（或想要的数量）。
2. `radar/report.py` 的 `daily()` 里，在 `for source in SOURCES:` 之前加回：

   ```python
   lines += [f"# {t('ch_keywords')}"]
   lines += _body(keyword_table(cfg, extra.get("usecases", {"skipped": True}), notes=False,
                                origins=_origins(lead, extra))) or [t("uc_none")]
   ```

   同时把 `_origins()` 加回来（它给每个名字写「从哪来: X @账号 ♥赞:「原句」」，2026-11-11 那版在 git 历史 `7e11da4` 里）。
3. 跑一次 `python -m radar daily --out report.md`，看 `# 新词表` 是不是又按「一词一段、带从哪来」的格式出来了。

## 主题章节（2026-11-11 下线）

**它本来做什么**：按 `config.json` 里 `topics` 的正则，把各源命中的线索按主题归集，一个主题一小节。

**为什么下线**：今天 `AI video` 主题命中的 4 条全部来自 App Store，等于把 App Store 那一章又抄了一遍。它的价值在「同一个主题下多个源都在说」，只有单源命中时就是重复。

**关在哪**：`radar/report.py` 的 `daily()` 不再输出 `# 主题`；`topic_lines()` 和 `config.topics` 都保留，`python -m radar` 没有单独的入口。

**重启条件**：一个主题下至少两个不同的源同时有命中。

## 新名字的旁证（2026-11-11 下线）

**它本来做什么**：给「新词表」要读的那些名字补证据——同名新站（whois / crt.sh）、维基百科浏览、Google 认成什么、Discord 服务器数。

**为什么下线**：新词表 2026-11-11 下线了，它是给那批名字服务的，现在等于给一张不存在的表做旁证。它也不是信息源，不产词。

**关在哪**：`daily()` 不再输出这一章；`config.json` 里 `sidelights.names` 设 0（`radar/config.py` 的默认值也是 0），`sidelights.evidence()` 代码保留。

**重启条件**：新词表重启时一起开：`usecases.per_day` 开回 5，`sidelights.names` 开回 5。
