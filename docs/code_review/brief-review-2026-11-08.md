# 审查：brief / 按信息源分节 / 报告归档改动（2026-11-08）

审查对象是工作区里未提交的改动：`radar/brief.py`（新）、`report.py`、`store.py`、`__main__.py`、`i18n.py`、`config.py`、`tests/test_radar.py`。
第一轮结论：**功能是对的，测试通过，可以合并；但先修 3 个 P1，再让它跑正式日报。** 没有发现会崩数据或写错库的 bug。

> **第二轮复核（修完之后）见文末。P1/P2 已全部关闭，另发现 5 个不阻塞的小问题。**

## 我核对过、确认没问题的部分

- 分节：`_leads_by_source()`（`report.py:54`）按 `KINDS` 顺序取最早信号，跨信号去重正确；无名字时输出 `leads_none`；`rest` 用的是完整的 `all_named`，没有漏掉「其他上升词」。
- 表格：`leads_cols` 7 列，分隔行 7 列（`report.py:433`），中英一致。
- 回退：模型没配 / 无 key / 调用失败 / 返回坏 JSON → `by_rules()` 用 `setdefault` 补，**不会覆盖**模型已给的标签（`brief.py:72-74`）。
- 语言：`why` 跟随 `i18n.lang()`（`brief.py:83`），中文报告确实走中文。
- 归档：`executescript` 建两表，老库兼容；SQL 全参数化；同一天多次运行保留多行、`report(day)` 取最后一次；`--day` 非法值返回 1 不抛栈。
- 测试：`uv run --with pytest --with markdown python -m pytest -q` → **171 passed, 2 skipped**。只装 pytest 不装 markdown 时挂 1 个（`notify.html`），是环境问题。
- CLI 实测：`python3 -m radar reports --state state` 正常返回 0。

## P1：建议合并前修

### 1. `why` 泛的根因：brief 没拿到最有用的上下文

`brief.py:86` 只把 `term` + 两条 `examples` 发给模型。但线索里明明有更值钱的东西：

- `r["about"]`：产品/站的**自述**。⑨ 的 Product Hunt / Google 新页面 / App Store、⑥ 的收入产品、⑧ 的卖家都带了（`feeds.py:222`、`revenue.py:122`、`sellers.py:333`）。
- `r["signals"]`：信号自带的说明（"App Store 新上架"、"30 天收入 $x"）。
- `r["format"]`：🎬/🎙/🖼 已经是规则判好的。

所以模型对「kemo」只看到 `App Store · Productivity: Kemo`，只能写出 "App Store listing suggests a useful app tool."——这不是 prompt 不够严，是输入里没有可说的东西。收紧 prompt 治标，补上下文治本。

建议（二选一或都做）：

```python
about = r.get("about")
blurb = about[1] if isinstance(about, (list, tuple)) and len(about) > 1 else ""
user = json.dumps([{
    "i": i, "term": r["term"],
    "appeared": list(r.get("signals") or [])[:2],
    "about": blurb[:200],
    "examples": [e[:160] for e in r.get("examples", [])[:2]],
} for i, r in enumerate(chunk)], ensure_ascii=False)
```

并在 `SYSTEM` 的 `why` 上加一句：*"Say what it does or what demand is forming; never merely restate the source ('an App Store listing')."*

### 2. brief 失败完全不可见

`run()` 会把异常收进 `extra["brief"]["error"]`，但 `_status_lines()` 只渲染 `judge` 和 `record`（`report.py:409`），`sources()` 同样（`report.py:760`）。结果是：没配 key、模型挂掉、JSON 被截断，用户只看到一列 `—`，报告底部没有任何说明。这和项目一直强调的「数据源挂了要在表下面写明」相反。

`cost` 文案也只提了「名字判断的模型调用另计」（`i18n.py:172`），没提 brief。

建议：
- `_status_lines` 的循环加 `("brief", "st_brief")`，新增 `st_brief` 文案（最好同时报「模型标了 n 条 / 其余用规则」）。
- `cost` 文案改成「名字判断与 brief 的模型调用另计」。

### 3. 25 条一次 + `max_tokens=1500`，中文有截断风险

`CHUNK = 25`（`brief.py:19`），`aisa.chat()` 默认 `max_tokens=1500`（`aisa.py:108`）。25 条 ×（`i`/`kind`/`use` + 12 词 `why`）英文约 900–1,200 token，中文 `why` 每字约 1.5 token，逼近或超过 1500。一旦截断，`parse()` 拿不到合法 JSON，**整块 25 条静默退回规则**，而用户不会知道（见 P1-2）。

建议：`CHUNK = 15`，或给这次调用显式 `max_tokens=3000`；两者一起更稳。

顺带：现在 `annotate(lead, ...)` 传的是**全量** `lead`。⑨ 九路 feed 每路最多 10 条，加 sitemap/X/HF，忙日 `lead` 很容易 60–120 条 → 3–5 次 chat、每次最长 90 秒，既加钱又加时。而报告只展示 `named()[:SHOWN]`（≤20 条）。建议在 `cmd_daily` / `cmd_sources` 里只传 `report.named(cfg, lead)[:report.SHOWN]`；`annotate` 原地改 dict，所以 `lead` 里同一批对象仍会带上字段。这也能让模块 docstring 的「One chat call a run」变成真的。

## P2：值得改，但不阻塞

### 4. `sources` 调了 brief，却从不渲染

`__main__.py:94` 在 `cmd_sources` 里也跑了 brief，但 `report.sources()`（`report.py:749`）的表还是 term/signals/score/known/examples，没有 kind/why/use。每 8 小时白花一次模型调用和几十秒。建议二选一：sources 报告也加三列，或 sources 不跑 brief（我倾向后者：sources 追求快，决策在 daily 做）。

### 5. `brief` 没进示例配置，用户看不到也调不了

`config.py:30` 加了 `DEFAULTS["brief"]`，但根目录和 `radar/` 下两份 `config.example.json` 都没有 `brief` 块，README 的配置表也没有。示例配置是随包发布的，等于这个功能对用户不可见。测试只校验两份示例彼此一致，所以不会报错。

### 6. 报告丢了「搜索变体」和「信号的量化」

旧表有 `signals` 和 `variants` 两列，新表都没有：

- `variants`：GitHub 爆发给的是大家真会搜的写法（"niko strata"）；现在 `report.json` 里还有，人看报告时没了。
- `signals`：每条线索的量化说明，例如 `GitHub 爆发 owner/repo ★3178（均 626/天）`、`X: 3 个账号 ♥500`、`30 天收入 $1,200`。新表只把**最早的信号名**放进分节标题，数字全丢了——而 `breakout` 的 `examples` 只有 `repo: description`，不含星数。也就是说，读者再也看不到「这个仓库每天涨 626 星」这种最强证据。
- 另一个词被两个信号同时抓到时，第二个信号也完全不可见（`report.leads` 的排序仍在用 `len(kinds)`）。

这不一定是错的，但和「为什么看」的初衷冲突：最硬的证据反而被删了。建议二选一：把 `signals` 和 `variants` 压进「证据」格（`note + " · " + variants`），或恢复一个紧凑的「信号」列。

### 7. 归档只覆盖 `daily`，不覆盖 `sources`

`store.save_report` 只在 `cmd_daily` 调用（`__main__.py:150`）。而你描述的是「每次运行存一行」。`sources` 每 8 小时一次、只在有新词时写报告，这些同样会丢。另外：**`state/radar.db` 的 `reports` 表现在是 0 行**，`report.md` 最后写入是 15:48——你看到的 15:47 那份并没有进库（要么当时还没接上，要么保存失败被静默吞掉）。`extra["saved"]` 的错误同样无人渲染，建议一起在状态行显示。

### 8. `kind` 和 `format` 是两套判断，可能互相打脸

`_marks()` 的 🎬/🎙/🖼 来自 `opportunity.fmt()` 的规则，`_kind_cell()` 的类型来自模型；两者可以矛盾（模型说「AI 视频」但行尾没有 🎬），而且 `report.leads` 的排序用的是 `format`，brief 跑在排序之后，模型判的视频不会按视频排。建议：`kind` 属于 video/image/voice 时用它覆盖 `format`（或至少覆盖 🎬），否则考虑去掉重复的「类型」列。

## P3：小问题，顺手改

- `store.py:8` 模块 docstring 仍写 "one row a day"，和实际「一次运行一行」矛盾。
- `__main__.py:26` 帮助写 `reports [--days 14]`，实际默认 `7`（`__main__.py:287`）。
- 分节顺序以 `KINDS`（`report.py:13`）为准：⑥收入 → ⑦求助 → ⑧卖家 → ⑧b → ⑨ → ⑩，与 README 编号一致；你消息里写的是「卖家 → 求助」。若后者才是本意，改 `KINDS` 一处即可（分节和线索排序都会跟着变）。
- `cmd_reports` / `cmd_leads` 的输出是硬编码英文（`__main__.py:255-262`），不符合「所有用户可见文本走翻译文件」。
- `--skip brief` 会让三列全变 `—`，而不是退回规则。若希望「跳过模型但仍填规则」，在 skip 时传 `{"enabled": False}` 即可。
- `brief.parse` 先跑 `re.search(r"\[.*\]", ..., re.S)` 再 `json.loads`：模型若在 JSON 后面再写一段带 `]` 的话，贪婪匹配会把尾巴一起吞掉，解析失败 → 静默退回规则。更稳的顺序是先 `json.loads(answer.strip())`，失败再用正则兜底（现有行为可接受，属加固）。
- 版本没动：`pyproject.toml` / `plugin.json` / `server.json` / `.claude-plugin/marketplace.json` 都还是 0.6.2，CHANGELOG 没有条目，README 没有 `reports` 命令和 `brief` 配置。
- 提示注入：`examples`/`about` 来自帖子与网页，和 `judge`/`usecases` 同一暴露面，不是新增风险，但补 `about` 后注入面略增；保持「只当数据」的系统提示即可。

## 建议补的测试（现在 6 个新测试都是正路）

1. 没有 named 线索时：`leads_none` 出现，且 `Other rising terms` 仍列出普通词。
2. brief 失败时：错误真的出现在「数据状态」里（对应 P1-2）。
3. `--skip brief` 的行为（现在是空列；若改成规则，用测试锁住）。
4. brief 只收到展示行（对应 P1-3 的裁剪）。
5. `store.reports` 的 `--days` 边界（第 7 天含、第 8 天不含）。
6. 中文渲染：`#### ⑨ 新上架` + 7 列都对得上。

## 合并后的待办清单（含上一轮发现）

| 优先级 | 事项 | 位置 |
|---|---|---|
| P1 | brief 输入补 `about` / `signals`，prompt 禁止复述来源 | `brief.py:86` |
| P1 | brief 失败进状态行；cost 文案带上 brief | `report.py:409,760`、`i18n.py:172` |
| P1 | 降 `CHUNK` 或提 `max_tokens`；只标展示的 ≤20 条 | `brief.py:19,89`、`__main__.py:94,125` |
| P2 | sources 要么渲染三列、要么不跑 brief | `report.py:749`、`__main__.py:94` |
| P2 | `brief` 写进两份 `config.example.json` + README 配置表 | `config.example.json`、`radar/config.example.json`、`README.md` |
| P2 | `signals`（星数/点赞/收入）与 `variants` 并入证据格或恢复一列 | `report.py:436` |
| P2 | `sources` 也归档；`saved` 失败要显示；确认下次 daily 真的多一行 | `__main__.py:150`、`report.py:409` |
| P2 | `kind` 与 `format` 统一（至少让 🎬 跟模型走） | `brief.py:65`、`report.py:67` |
| P3 | docstring 的 one-row-a-day / --days 14；CLI 文案进 i18n；`--skip brief` 语义 | `store.py:8`、`__main__.py:26,249` |
| P3 | README 命令表 + CHANGELOG + 四处版本号 | 发布前 |
| — | `trending` 的 `country_code` 400（用户已说先不碰） | `feeds.py:152` |

## 一句话

这轮改动的方向和实现都站得住，真正的风险不是逻辑错，而是**模型输出质量（输入缺料）、失败被静默吞掉、以及文档/配置没跟上**。把 P1 三条修掉，这份日报就比旧版明显更有用；P2 主要是别白花钱、别丢信息。

---

# 第二轮复核（修完之后，同日）

**测试：178 passed, 2 skipped**（`uv run --with pytest --with markdown python -m pytest -q`）。第一轮的 P1 三条、P2 五条全部关闭，P3 只剩已知的两项。我实测了 brief 的真实入参和报告渲染，结论是**可以提交**；下面 5 条都不阻塞。

## 已确认修好

- **P1-1 输入补料**：`annotate` 现在发 `term` / `appeared`（信号说明）/ `about`（自述，`blurb()` 去空白截 200）/ `examples`；prompt 明确「不要只复述来源」。测试 `test_brief_sends_what_the_signal_knows` 锁住了这三项和 `max_tokens=3000`。
- **P1-2 失败可见**：`_status_lines` 现在区分 成功（模型 n / 规则 m）、`--skip brief`、失败三种；`cost` 文案带上 brief；`_archive()` 把归档失败追加到报告末尾。`st_brief*` / `st_saved` 中英都有。
- **P1-3 截断与范围**：`CHUNK=15`、`MAX_TOKENS=3000`；`cmd_daily` 只传 `report.named(cfg, lead)[:report.SHOWN]`，忙日一次调用。
- **P2**：sources 不再跑 brief；两份 `config.example.json` 与 README 都加了 `brief`；`_evidence()` 把「例子 · 信号（★/点赞/收入）· 搜索变体」压进证据格（实测 `storytold/gridcraft: an open-source grid · GitHub breakout storytold/gridcraft ★3178 (626/day) · storytold gridcraft`）；sources 也归档；`_marks()` 优先用模型的 kind。
- **P3**：`store.py` 的 one-row-a-day、`reports [--days 7]`、`reports` 文案进 i18n、`--skip brief` 退回规则、`parse` 先整体 `json.loads`，都已改。

## 新发现（不阻塞，建议下一步顺手处理）

1. **`parse` 的兜底从贪婪改成了非贪婪，小概率整块丢标签。**
   `brief.py:47` 现在是 `re.search(r"\[.*?]", text, re.S)`。模型若返回 ```json 围栏或前后有话，正则只截到**第一个** `]`；如果 `why`/`term` 里本身有 `]`（例如 `"a [beta] tool"`），整段 JSON 解析失败 → 15 条全部退回规则。实测：
   ```python
   brief.parse('Here: [{"i":0,"kind":"tool","why":"a [beta] tool","use":"new"}]', 1)  # -> {}
   ```
   既然已经先尝试整体 `json.loads`，兜底用回贪婪的 `r"\[.*]"` 更稳（干净的输出走不到正则）。
2. **`reports --day` 会被同一天的 sources 报告挡住。**
   现在 sources 也归档，`store.report(day)` 取当天最后一条。实测同一天先写 `DAILY` 再写 `SOURCES`，`report(day)` 返回 `SOURCES`。查「那天」通常想要的是日报。建议 `--day` 优先返回当天的 `daily`（没有时再退回最后一条），或加 `--command daily|sources`。
3. **模型没配置时状态文案不准。** `brief.annotate` 在 `model` 为空时走 `by_rules`，返回 `{"briefed": 0, "by_rules": n}`（没有 `skipped`），状态行显示「模型标注 0 条,规则补充 n 条」；实际是「没配模型」。在 `if not model` 时返回 `skipped: True` 即可。
4. **`reports` 列表行里的 `chars` 仍是硬编码英文**（`__main__.py` 的 `f"...{r['chars']} chars"`），`cmd_leads` 同（已知、不在本次范围）。要么把整行做成模板，要么接受它是纯数据行。
5. **`_report_lang` 对非 dict 的 config 会抛 `AttributeError`**：`json.loads(...).get("lang")` 在文件是数组/字符串时没被 `except (OSError, ValueError)` 接住。加 `AttributeError` 即可。

另：排序仍用规则判的 `format`（`report.leads` 在 brief 之前跑），而 🎬 已经跟模型走。两者不一致只影响「同等条件下视频优先」的排序，不影响显示；可以接受，记一笔。

## 提交建议

- 代码可以提交。
- `docs/brief-review-2026-11-08.md` 如果跟着提交：这是公开仓库，正文写了对未发布代码的评审。我已把标题和称呼改成中性的「改动评审」，可以直接提交，作为这轮设计的记录；不想公开的话就留在不进版本库的位置。
- 版本号和 CHANGELOG 按你说的，发布前一起动。
