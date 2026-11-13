"""One line on each lead: what it is, why it is worth a look, and what to do with it.

The signals say where a term came from; a term on its own says little. A small model reads
the term with the places it appeared (what the signal counted, what the product says about
itself, the post or listing) and returns its kind (a game, an AI tool, something that makes
video, images or voice, an information query, a brand, a generic word), one short sentence on
why it is worth a look now, and what to do with it (an inner page on a site you already run,
a new site, or watch).

One chat call a run, the model set in config.json (brief.model). Without a key, with
--skip brief, or when the call fails, keyword rules answer instead: they read the term's
shape, and say less.
"""
from __future__ import annotations

import json
import re

from . import aisa, i18n

CHUNK = 15
MAX_TOKENS = 3000
KINDS = {"game", "tool", "video", "image", "voice", "info", "brand", "generic"}
USES = {"inner", "new", "watch"}

SYSTEM = (
    "You label leads for a radar that finds things worth building a page or a tool for. For each term you get the "
    "places it appeared (`examples`), what the signal counted (`appeared`) and the product's own description "
    "(`about`). Return:\n"
    "- kind: one of game, tool, video, image, voice, info, brand, generic. A game or a game mode; an AI tool people "
    "would use; something that makes video, images or voice; an information query (news, a person, an event); a "
    "company or product name; or a generic word.\n"
    "- why: one short sentence, at most 12 words. Say what it does or what demand is forming. Never merely restate "
    "where it was found (\"an App Store listing\", \"featured on Product Hunt\").\n"
    "- need: the phrase a person would type into Google for the need behind this, at most 5 words, no brand or "
    "product name (\"ai video clipping\", \"private notes app\"). Empty string when the term is itself a brand, a "
    "company, a person's name or a URL fragment, and when nothing here shows a need. Do not invent a phrase.\n"
    "- use: inner (a page on a site you already run), new (a new site), or watch (not yet).\n"
    "Answer with JSON only, one object per term, in the same order: "
    "[{\"i\": 0, \"kind\": \"tool\", \"why\": \"...\", \"need\": \"...\", \"use\": \"inner\"}, ...]"
)


def _json_list(answer: str) -> list:
    """The JSON array in an answer, even with a sentence around it or a truncated tail."""
    text = answer.strip()
    try:
        items = json.loads(text)
    except ValueError:
        m = re.search(r"\[.*]", text, re.S)
        try:
            items = json.loads(m.group(0)) if m else []
        except ValueError:
            return []
    return items if isinstance(items, list) else []


def parse(answer: str, n: int) -> dict[int, dict]:
    """{index: {kind, why, use}} from the model's answer; indexes outside 0..n-1 are dropped."""
    out = {}
    for it in _json_list(answer):
        try:
            i = int(it["i"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= i < n:
            continue
        kind = str(it.get("kind") or "").strip().lower()
        use = str(it.get("use") or "").strip().lower()
        out[i] = {"kind": kind if kind in KINDS else "generic",
                  "why": " ".join(str(it.get("why") or "").split())[:120],
                  "need": " ".join(str(it.get("need") or "").split())[:60],
                  "use": use if use in USES else "watch"}
    return out


REDDIT_SYSTEM = (
    "你在读 Reddit 上有人贴出的帖子，判断它是不是在说自己想要一个东西：一个还不存在的工具、或者现有产品没做好的地方。"
    "每条给你原始标题。能说清的，用一句自然的中文说出这个人想要什么（做出什么功能、解决什么麻烦），"
    "不要每条都用「想要」开头，直接说那个东西是什么，不超过 25 个字。"
    "读不出在要什么、纯闲聊、无意义的内容，不要硬编，给它 drop。不要编造标题里没有的东西。"
    "Answer with JSON only: [{\"i\": 0, \"zh\": \"...\"}, {\"i\": 1, \"drop\": true}]"
)


def parse_read(answer: str, n: int) -> dict[int, dict]:
    """{index: {"zh": ...} or {"drop": True}} from the model's answer; indexes outside 0..n-1 are
    dropped. An index the model leaves out keeps the title as posted."""
    out = {}
    for it in _json_list(answer):
        try:
            i = int(it["i"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= i < n:
            continue
        zh = " ".join(str(it.get("zh") or "").split())[:60]
        out[i] = {"zh": zh} if zh else {"drop": True} if it.get("drop") else {}
    return out


def read_reddit(items: list[dict], setting: dict, use_model: bool = True) -> dict:
    """Sets `zh` on each Reddit post and drops the ones that ask for nothing: one Chinese sentence
    on what the poster wants, or out of the list. The reader of the report does not read English,
    and a title that names no want gives them nothing to act on. A post the model leaves out
    keeps its title as posted."""
    model = setting.get("model") or ""
    if not use_model or not setting.get("enabled", True) or not model or not items:
        return {"read": 0, "skipped": True}
    done, error = 0, ""
    for start in range(0, len(items), CHUNK):
        chunk = items[start:start + CHUNK]
        user = json.dumps([{"i": i, "title": (x.get("name") or "")[:160]} for i, x in enumerate(chunk)],
                          ensure_ascii=False)
        try:
            answer = aisa.chat(model, REDDIT_SYSTEM, user, max_tokens=MAX_TOKENS)
        except aisa.AisaError as exc:
            error = str(exc)[:160]
            break
        for i, label in parse_read(answer, len(chunk)).items():
            if label.get("zh"):
                chunk[i]["zh"] = label["zh"]
                done += 1
            elif label.get("drop"):
                chunk[i]["drop"] = True
    before = len(items)
    items[:] = [x for x in items if not x.get("drop")]     # nothing to build on: the source's own noise
    return {"read": done, "dropped": before - len(items), **({"error": error} if error else {})}


TOOLISH = re.compile(r"(?<![a-z])(ai|generator|maker|editor|remover|checker|converter|app|tool|filter|effect|"
                     r"template|agent|bot|plugin)(?![a-z])", re.I)
GAME = re.compile(r"(?<![a-z])(game|gaming|gameplay|roblox|minecraft|level|mod)(?![a-z])", re.I)
INFO = re.compile(r"(?<![a-z])(news|update|release|announce|rumor|leak|review|war|election)(?![a-z])", re.I)


def by_rules(rows: list[dict]) -> None:
    """Keyword rules, for when the model is off or its call failed. Never overwrites a label."""
    for r in rows:
        term, fmt = r["term"].lower(), r.get("format", "text")
        kind = fmt if fmt in ("video", "image", "voice") else (
            "game" if GAME.search(term) else "tool" if TOOLISH.search(term) else
            "info" if INFO.search(term) else "generic")
        r.setdefault("kind", kind)
        r.setdefault("why", "")
        r.setdefault("need", "")
        r.setdefault("use", "watch")


def blurb(r: dict) -> str:
    """The product's own description when the signal carried one (⑨, ⑥ and ⑧ do), else ""."""
    about = r.get("about")
    if isinstance(about, (list, tuple)) and len(about) > 1:
        return " ".join(str(about[1]).split())[:200]
    return ""


def annotate(rows: list[dict], setting: dict, use_model: bool = True) -> dict:
    """Sets kind, why and use on each row: the model first, rules for whatever it left out.
    `use_model=False` (--skip brief) keeps the labels from the rules alone."""
    model = setting.get("model") or ""
    if not use_model or not setting.get("enabled", True) or not model:
        by_rules(rows)
        return {"briefed": 0, "by_rules": len(rows), "skipped": True}
    done, error = 0, ""
    system = SYSTEM + "\nWrite `why` and `need` in " + ("Chinese." if i18n.lang() == "zh" else "English.")
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start:start + CHUNK]
        user = json.dumps([{"i": i, "term": r["term"], "appeared": list(r.get("signals") or [])[:2],
                            "about": blurb(r), "examples": [e[:160] for e in r.get("examples", [])[:2]]}
                           for i, r in enumerate(chunk)], ensure_ascii=False)
        try:
            labels = parse(aisa.chat(model, system, user, max_tokens=MAX_TOKENS), len(chunk))
        except aisa.AisaError as exc:
            error = str(exc)[:160]
            break
        for i, label in labels.items():
            chunk[i].update(label)
            done += 1
    by_rules(rows)                         # fills what the model did not answer, and keeps what it did
    return {"briefed": done, "by_rules": len(rows) - done, **({"error": error} if error else {})}
