"""Leads merged from every signal, and the two reports in Markdown."""
from __future__ import annotations

import re

from . import asks, competition, opportunity, sellers, config, judge, usecases, yours
from .i18n import t

SHOWN = 20
POSTS_SHOWN = 3   # posts quoted in full per term
# signal key -> label key, in the order of how early the signal comes
KINDS = ["x", "hf", "breakout", "sitemap", "newsite", "revenue", "ask", "seller", "builder", "feed", "money", "usecase", "cosearch", "watch"]


def leads(cfg: dict, blocks: dict[str, dict]) -> tuple[list[dict], dict]:
    """Terms from every discovery signal, merged; a term in several is the strongest lead.
    Returns (rows, the judge's status)."""
    out: dict[str, dict] = {}
    for kind, block in blocks.items():
        for r in block.get("terms", []):
            row = out.setdefault(r["term"], {"term": r["term"], "kinds": [], "signals": [], "examples": [], "variants": [], "posts": []})
            row["kinds"].append(kind)
            row["signals"].append(r.get("note") or t("note_surge", label=t(f"kind_{kind}"), n=r["recent"], lift=r["lift"]))
            row["examples"] += r.get("examples", [])
            row["posts"] += r.get("posts", [])
            row["variants"] += [v for v in r.get("variants", []) if v not in row["variants"]]
            if r.get("repo"):
                row["repo"] = r["repo"]
            if r.get("about"):
                row["about"] = r["about"]
            if r.get("feed"):
                row.setdefault("feeds", [])
                if r["feed"] not in row["feeds"]:
                    row["feeds"].append(r["feed"])
    rows = list(out.values())
    for r in rows:
        r["known"] = config.known(cfg, r["term"])
        opportunity.tag(r)
    status = judge.score(rows, cfg["judge"]["model"]) if rows else {"judged": 0}
    cut = cfg["judge"]["min_score"]
    # Earliest signal first among equals: a name the labs said today beats a sitemap echo.
    rows.sort(key=lambda r: (-(r.get("named", 0) >= cut), -len(r["kinds"]),
                             min(KINDS.index(k) for k in r["kinds"]), opportunity.RANK[r["format"]], -r.get("named", 0)))
    return rows, status


def named(cfg: dict, lead: list[dict]) -> list[dict]:
    """Without the judge's score (no key, a failed call) every term counts; with it, only names."""
    cut = cfg["judge"]["min_score"]
    return [r for r in lead if r.get("named", 1.0) >= cut]


def to_record(cfg: dict, lead: list[dict]) -> list[dict]:
    return [r for r in named(cfg, lead)[:SHOWN] if not r["known"]]


# One chapter per source, in the order the README numbers them. Every chapter is written, empty
# or not: a reader asking "what did TikTok say today" must not have to guess whether it was silent
# or never read.
SOURCES = ("x", "sitemap", "newsite", "producthunt", "appstore", "google_new",
           "tiktok", "reddit", "rising", "revenue", "ask", "seller", "builder")
SOURCE_KEY = {"x": "x", "sitemap": "sitemap", "newsite": "newsite",
              "producthunt": "feed:producthunt", "appstore": "feed:appstore", "google_new": "feed:google_new",
              "tiktok": "feed:trending:tiktok", "reddit": "feed:trending:reddit", "rising": "feed:rising",
              "revenue": "revenue", "ask": "ask", "seller": "seller", "builder": "builder"}
BLOCK = {"x": "x", "sitemap": "sitemap", "newsite": "newsite", "revenue": "revenue", "ask": "ask",
         "seller": "seller", "builder": "builder"}
FEED_SOURCES = {"producthunt", "appstore", "google_new", "rising", "tiktok", "reddit"}
CHAPTER_SHOWN = 5
TOP_SHOWN = 5


def _from_source(r: dict, source: str) -> bool:
    """Whether this lead came from that source: a signal name, or the platform behind a feed."""
    key = SOURCE_KEY[source]
    return key[5:] in (r.get("feeds") or []) if key.startswith("feed:") else key in r.get("kinds", [])


def _body(lines: list[str]) -> list[str]:
    """A block's lines without its own heading: the chapter above it names the source."""
    out = list(lines)
    while out and not out[0].strip():
        out.pop(0)
    if out and out[0].startswith("###"):
        out.pop(0)
    while out and not out[0].strip():
        out.pop(0)
    return out


def _match(term: str, by_term: dict[str, dict]) -> dict:
    """The lead for an item the source listed, when one was judged."""
    t = (term or "").lower()
    if t in by_term:
        return by_term[t]
    for k, r in by_term.items():
        if k and (k in t or t in k):
            return r
    return None


def _rows(source: str, b: dict[str, dict], by_term: dict[str, dict]) -> list[tuple[str, str, str, dict]]:
    """Every item this source produced today: (name, what it is, the source's own number, its lead).

    The chapters list what the source listed, not only what the judge called a name: a TikTok
    trend that reads like a sentence is still what TikTok had today, and the reader decides."""
    out = []
    if source == "newsite":
        for s in b.get("newsite", {}).get("sites") or []:
            r = _match(s["domain"], by_term)
            out.append((s["domain"], _what(r) or t("why_newsite"), t("tag_visits", etv=f"{s['etv']:,}", kw=s["keywords"]), r))
    elif source == "revenue":
        for p in b.get("revenue", {}).get("products") or []:
            r = _match(p["name"], by_term)
            out.append((p["name"], _what(r) or _clip(_cell(p["about"]), 60), t("tag_revenue", usd=f"{p['usd']:,}"), r))
    elif source == "ask":
        for row in b.get("ask", {}).get("rows") or []:
            r = _match(row["phrase"], by_term)
            out.append((row["phrase"], _what(r) or t("why_ask"), t("tag_volume", n=f"{row['volume']:,}"), r))
    elif source == "seller":
        for s in b.get("seller", {}).get("sellers") or []:
            r = _match(s["host"], by_term)
            out.append((s["host"], _what(r) or _clip(_cell(s["title"]), 60), sellers.LABEL.get(s["platform"], s["platform"]), r))
    elif source == "builder":
        for s in b.get("builder", {}).get("sites") or []:
            r = _match(s["host"], by_term)
            out.append((s["host"], _what(r) or _clip(_cell(s["title"]), 60), sellers.LABEL.get(s["platform"], s["platform"]), r))
    elif source in FEED_SOURCES:
        name = SOURCE_KEY[source][5:].split(":")[0]
        where = SOURCE_KEY[source][5:].partition(":")[2]
        for i in (b.get("feed", {}).get("new") or {}).get(name) or []:
            if where and (i.get("where") or "") != where:
                continue
            r = _match(i["name"], by_term)
            about = _cell(i.get("about") or "").replace("Discussion / Link", "").strip()
            place = i.get("where") or ""
            fallback = (t("why_trending") if name == "trending" else t("why_rising", seed=place) if name == "rising"
                        else t("why_google") if name == "google_new" else "")
            out.append((i["name"], _what(r) or _clip(about, 60) or fallback,
                        place if name == "google_new" else "", r))
    else:                                  # X and the sitemaps report only what the judge kept
        out = [(r["term"], _what(r) or r["term"], "", r) for r in by_term.values() if _from_source(r, source)]
    used = {id(r) for *_, r in out if r}
    out += [(r["term"], _what(r), "", r) for r in by_term.values()
            if _from_source(r, source) and id(r) not in used]      # a judged word the source no longer lists
    return out


def _about(name: str, b: dict[str, dict]) -> str:
    """The description a source carried for a name, for when the brief could not run."""
    n = (name or "").lower()
    for items in (b.get("feed", {}).get("new") or {}).values():
        for i in items:
            if (i.get("name") or "").lower() == n:
                return _clip(_cell(i.get("about") or "").replace("Discussion / Link", "").strip(), 60)
    return ""


def _what(r: dict | None) -> str:
    """Why the radar kept it, in one short line."""
    return _clip(_cell(r.get("why") or ""), 60) if r else ""


def _line(name: str, what: str, number: str, r: dict | None) -> str:
    """One word: what it is and why it is here, then how to use it and what the source counted."""
    tag = " · ".join(x for x in ((t("bk_" + r["kind"]) if r and r.get("kind") else ""),
                                 (t("bu_" + r["use"]) if r and r.get("use") else t("bu_watch")),
                                 number) if x)
    mark = _marks(r) if r else ""
    return f"**{name}**{mark} — {what}（{tag}）" if what else f"**{name}**{mark}（{tag}）"


def _chapter_state(source: str, b: dict[str, dict], cfg: dict | None = None) -> str:
    """Why a chapter has nothing: not read today (weekly, or off in the config), or the source failed."""
    feeds_cfg = (cfg or {}).get("feeds") or {}
    if source in FEED_SOURCES:
        fd = b.get("feed") or {}
        if fd.get("skipped"):
            return t("src_skipped")
        name = SOURCE_KEY[source][5:].split(":")[0]
        if cfg is not None:
            if name not in (feeds_cfg.get("enabled") or []):
                return t("src_off")
            if name not in (fd.get("read") or {}) and name in (feeds_cfg.get("weekly") or []):
                return t("src_skipped")
        return "; ".join(e for e in fd.get("errors") or [] if e.startswith(name))
    block = b.get(BLOCK[source]) or {}
    return t("src_skipped") if block.get("skipped") else (block.get("error") or "")


MARK = {"video": " 🎬", "voice": " 🎙", "image": " 🖼", "text": ""}


def _marks(r: dict) -> str:
    """What the thing makes, and ⚡ when a widely shared tutorial or trend shows a manual workflow.
    The brief's kind wins when it names a medium: the report should not say "AI video" without 🎬."""
    kind = r.get("kind")
    return MARK.get(kind if kind in ("video", "voice", "image") else r.get("format", "text"), "") + \
        (" ⚡" if r.get("one_click") else "")


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def _score(r: dict) -> str:
    return f"{r['named']:.2f}" if "named" in r else t("dash")


def _kind_cell(r: dict) -> str:
    return t("bk_" + r["kind"]) if r.get("kind") else t("dash")


def _state(block: dict, ok: str) -> str:
    return block.get("error") or (t("skipped") if block.get("skipped") else ok)


def _cost(*blocks: dict) -> str:
    return f"${sum(int(b.get('cost_micros') or 0) for b in blocks) / 1e6:.3f}"


def topic_lines(cfg: dict, lead: list[dict], b: dict[str, dict], gsc: dict) -> list[str]:
    """Per topic in config.json: the leads, breakout repos and new queries that match it."""
    lines = []
    for name, pattern in cfg["topics"].items():
        pat = re.compile(pattern, re.I)
        hits = [r for r in named(cfg, lead) if pat.search(r["term"] + " " + " ".join(r["examples"][:2]))]
        repos = [r for r in b["breakout"].get("repos") or [] if pat.search(r["repo"] + " " + r["description"])]
        queries = [q for q in gsc.get("queries") or [] if pat.search(q["query"])]
        lines += ["", t("topic_h", name=name), ""]
        if not (hits or repos or queries):
            lines.append(t("topic_none"))
            continue
        lines += [t("topic_lead", term=r["term"], signals="; ".join(r["signals"]),
                    match=_matched(pat, r)) for r in hits[:10]]
        lines += [t("topic_repo", repo=r["repo"], stars=r["stars"], velocity=r["velocity"], desc=r["description"][:60]) for r in repos[:8]]
        lines += [t("topic_query", query=q["query"], impressions=q["impressions"], page=q["page"]) for q in queries[:8]]
    return lines


def _matched(pat: re.Pattern, r: dict) -> str:
    """The part of the lead that matched the topic: the whole why it is on this list, when the
    pattern can match a domain suffix or a single common word."""
    m = pat.search(r["term"] + " " + " ".join(r["examples"][:2]))
    return _clip(m.group(0), 40) if m else ""


def _breakout_lines(bo: dict, cfg: dict) -> list[str]:
    lines = ["", t("breakout_h", days=cfg["breakout"]["window_days"]), ""]
    repos = bo.get("repos") or []
    if not repos:
        return lines + [t("recent_none", why=_state(bo, t("no_breakouts")))]
    lines += [t("breakout_cols"), "|---|---|---|---|---|---|"]
    return lines + [f"| {'🆕 ' if r.get('new') else ''}[{r['repo']}](https://github.com/{r['repo']}) | {r['stars']} | {r['velocity']} | "
                    f"{'+' + str(r['delta']) if r['delta'] is not None else t('dash')} | {r['age_days']} | "
                    f"{_cell(r['description'][:60])} |" for r in repos]


def _new_site_lines(ns: dict, cfg: dict) -> list[str]:
    if ns.get("skipped"):
        return []
    c = cfg["new_sites"]
    lines = ["", t("newsite_h", days=c["window_days"], etv=c["min_etv"], kw=c["min_keywords"]), ""]
    sites = ns.get("sites") or []
    if not sites:
        return lines + [t("recent_none", why=ns.get("error") or t("newsite_none"))]
    lines += [t("newsite_cols"), "|---|---|---|---|---|"]
    lines += [f"| {'🆕 ' if r['new'] else ''}[{r['domain']}](https://{r['domain']}) | {r['created']} | {r['first_seen']} | "
              f"{r['etv']} | {r['keywords']} |" for r in sites]
    return lines + _site_word_lines([r for r in sites if r.get("words") is not None])


def _site_word_lines(sites: list[dict]) -> list[str]:
    """The first words each new site ranks for in the top 20 (radar/site_words.py)."""
    if not sites:
        return []
    lines = ["", t("newsite_words_h")]
    for r in sites:
        said = "; ".join(("⏱ " if w["since"] else "") + t("newsite_word", word=_cell(w["word"]), pos=w["position"] or t("dash"),
                                                           country=w["country"] or t("dash"), vol=w["volume"] or t("dash"),
                                                           kd=t("dash") if w["kd"] is None else w["kd"]) for w in r["words"])
        more = t("newsite_words_more", n=r["top"]) if r["top"] > len(r["words"]) else ""
        lines.append(f"- {r['domain']}: {said or t('newsite_words_none')}{more}")
    return lines


def _revenue_lines(rv: dict, cfg: dict) -> list[str]:
    if rv.get("skipped") and not rv.get("no_key"):
        return []
    lines = ["", t("revenue_h", usd=cfg["revenue"]["min_revenue_usd"]), ""]
    if rv.get("no_key"):
        return lines + [t("revenue_nokey")]
    rows = rv.get("products") or []
    if not rows:
        return lines + [t("recent_none", why=rv.get("error") or t("revenue_none"))]
    lines += [t("revenue_cols"), "|---|---|---|---|---|"]
    for p in rows:
        came = t("revenue_zero") if p["from_zero"] else ", ".join(t("revenue_" + c.split("-")[0]) for c in p["came"])
        site = f"[{p['name']}]({p['website']})" if p["website"] else p["name"]
        lines.append(f"| {site} | {_cell(p['about'][:110]) or t('dash')} | ${p['usd']:,} | {p['growth_text']} | {came} |")
    return lines + ["", t("revenue_tos")]


def _asks_lines(ak: dict, cfg: dict) -> list[str]:
    if ak.get("skipped"):
        return []
    lines = ["", t("asks_h"), ""]
    rows, quiet = ak.get("rows") or [], ak.get("quiet") or []
    if not rows and not quiet:
        return lines + [t("recent_none", why=ak.get("error") or t("asks_none", read=ak.get("read", 0), asks=ak.get("asks", 0)))]
    lines += [t("asks_intro", read=ak["read"], asks=ak["asks"], unsized=ak["unsized"], min=cfg["asks"]["min_volume"])]
    ai_on = any(r.get("ai") for r in rows)
    if rows:
        lines += ["", t("asks_cols") + (f" {t('ai_col')} |" if ai_on else ""), "|---|---|---|---|---|---|" + ("---|" if ai_on else "")]
    for row in rows:
        p = max(row["posts"], key=lambda x: x["score"])
        lines.append(f"| **{row['phrase']}**{t('asks_again') if row.get('again') else ''} | {len(row['posts'])} ({row['score']}) | "
                     f"{', '.join(asks.where(s) for s in row['subreddits'][:3])} | {row['volume']:,} | {_page_one(row.get('competition'))} | "
                     f"[{_cell(p['title'][:70])}]({p['url']}) |" + (f" {_ai_cell(row.get('ai'))} |" if ai_on else ""))
    lines += _ai_lines(rows, cfg)
    if quiet:
        lines += ["", t("asks_quiet_h", min=cfg["asks"]["min_volume"]), "", t("asks_quiet_cols"), "|---|---|---|---|"]
        for row in quiet:
            p = max(row["posts"], key=lambda x: x["score"])
            lines.append(f"| {row['phrase']} | {len(row['posts'])} ({row['score']}) | {', '.join(asks.where(s) for s in row['subreddits'][:3])} | "
                         f"[{_cell(p['title'][:80])}]({p['url']}) |")
    if ak.get("errors"):
        lines.append(t("asks_err", why="; ".join(ak["errors"][:3])))
    return lines + ["", t("asks_note")]


ENGINE = {"chatgpt": "ChatGPT", "google": "Google AI Mode"}


def _ai_cell(ai: dict | None) -> str:
    """The tools AI answers name for a job, the first three; ✅ when one of your sites is cited."""
    if not ai:
        return t("dash")
    names = list(dict.fromkeys(n for got in ai["by"].values() for n in got["names"]))
    cell = (", ".join(names[:3]) + (f" +{len(names) - 3}" if len(names) > 3 else "")) if names else t("ai_none")
    return cell + (" ✅" if ai.get("yours") else "")


def _ai_lines(rows: list[dict], cfg: dict) -> list[str]:
    asked = [r for r in rows if r.get("ai")]
    if not asked:
        return []
    lines = ["", t("ai_h", prompt=cfg["ai_answers"]["prompt"])]
    for r in asked:
        parts = [t("ai_engine", engine=ENGINE.get(e, e), names=", ".join(g["names"]) or t("ai_none"), sites=", ".join(g["sites"]) or t("dash"))
                 for e, g in r["ai"]["by"].items()]
        lines.append(t("ai_line", job=r["phrase"], engines=" · ".join(parts)) + (t("ai_yours") if r["ai"]["yours"] else ""))
    return lines + [t("ai_note")]


def _builder_lines(bd: dict) -> list[str]:
    if bd.get("skipped") or not bd.get("sites"):
        return []
    kinds_line = "、".join(f"{t('sk_' + k)} {n}" for k, n in (bd.get("by_kind") or {}).items() if n)
    lines = ["", t("builders_h"), "", t("builders_intro", links=bd["links"], old=bd.get("old", 0), new=bd["new"]) + (f" {kinds_line}" if kinds_line else ""),
             "", t("builders_cols"), "|---|---|---|---|"]
    for s in bd["sites"]:
        what = _cell((s["title"] + (" — " + s["description"] if s["description"] else ""))[:110]) or t("dash")
        lines.append(f"| [{s['host']}](https://{s['host']}/) | {sellers.LABEL[s['platform']]} | {what} | {s['first_seen']} |")
    return lines


def _feed_lines(fd: dict) -> list[str]:
    if fd.get("skipped"):
        return []
    lines = ["", t("feeds_h"), ""]
    from .feeds import LABEL as WHERE
    for name, items in fd.get("new", {}).items():
        if items:
            shown = "; ".join((f"[{i['name']}]({i['url']})" if i.get("url") else i["name"]) + (f" ({i['where']})" if i.get("where") else "")
                              for i in items)
            lines.append(f"- **{WHERE.get(name, name)}**: {_cell(shown)}")
    if fd.get("first_run"):
        lines.append(t("feeds_first", feeds=", ".join(WHERE.get(n, n) for n in fd["first_run"])))
    if fd.get("errors"):
        lines.append(t("feeds_err", why="; ".join(fd["errors"][:4])))
    return lines if len(lines) > 3 else []


def _money_lines(md: dict) -> list[str]:
    if md.get("skipped"):
        return []
    lines = ["", t("money_h"), ""]
    if md.get("no_key"):
        return lines + [t("money_nokey")]
    if md.get("portfolios"):
        lines += [t("money_folios")] + [t("money_folio_row", site=r["site"], pub=r["pub"], sisters=", ".join(r["sisters"][:8]))
                                        for r in md["portfolios"]]
    if md.get("advertisers"):
        lines += ["", t("money_ads")] + [t("money_ad_row", term=r["term"], names=", ".join(r["advertisers"][:10])) for r in md["advertisers"]]
    if not md.get("portfolios") and not md.get("advertisers"):
        lines.append(t("money_none"))
    return lines


def _side_lines(sd: dict) -> list[str]:
    rows = [r for r in sd.get("rows") or [] if any(k in r for k in ("sites", "wiki", "entity", "discord"))]
    if sd.get("skipped") or not rows:
        return []
    lines = ["", t("side_h"), ""]
    for r in rows:
        ent = r.get("entity") or {}
        kind = "whois" if r.get("sites_from") == "whois" else "crt.sh"
        sites = r["sites"][0] if r.get("sites") and r["sites"][0] else "0"
        more = ", ".join(r["sites"][1]) if r.get("sites") and r["sites"][0] else ""
        bits = [x for x in (
            t("side_sites_more", sites=sites, more=more, kind=kind) if more else t("side_sites", sites=sites, kind=kind)
            if "sites" in r else "",
            t("side_wiki", recent=f"{r['wiki'][1]:,}", before=f"{r['wiki'][2]:,}") if r.get("wiki") and r["wiki"][0] else "",
            t("side_known", type=ent["type"]) if ent.get("type") else "",
            t("side_taken", type=ent["taken"]) if ent.get("taken") else "",
            t("side_discord", n=r["discord"]) if r.get("discord") is not None else "") if x]
        lines.append(f"- **{r['name']}**: " + (" · ".join(bits) or t("side_none")))
    return lines


def _tail_lines(td: dict) -> list[str]:
    if td.get("skipped") or not td.get("rows"):
        return []
    return ["", t("tails_h"), "", t("tails_cols"), "|---|---|"] + [f"| {r['phrase']} | {r['volume']:,} |" for r in td["rows"][:20]]


def _seller_lines(sl: dict) -> list[str]:
    if sl.get("skipped"):
        return []
    lines = ["", t("sellers_h"), ""]
    rows = sl.get("sellers") or []
    if not rows:
        return lines + [t("recent_none", why="; ".join(sl.get("errors") or []) or sl.get("error") or t("sellers_none"))]
    platforms = "、".join(sellers.LABEL.get(p, p) for p in sl.get("platforms") or sellers.PLATFORMS)
    lines += [t("sellers_intro", links=sl["links"], old=sl.get("old", 0), new=sl["new"], platforms=platforms), "", t("sellers_cols"), "|---" * 8 + "|"]
    for s in rows:
        what = _cell((s["title"] + (" — " + s["description"] if s["description"] else ""))[:110]) or t("dash")
        seen = f"{s['visits']:,}" if s["visits"] else t("dash")
        ai = f" ({s['ai_share'] * 100:.1f}%)" if s.get("ai_share") is not None else ""
        lines.append(f"| [{s['host']}](https://{s['host']}/) | {t('sk_' + s.get('kind', 'other'))} | {sellers.LABEL[s['platform']]} | {what} | "
                     f"{seen} | {s.get('registered') or t('dash')} | {(s.get('top_source') or t('dash')) + ai} | {s['first_seen']} |")
    if sl.get("errors"):
        lines.append(t("sellers_err", why="; ".join(sl["errors"][:3])))
    if sl.get("kind_error"):
        lines.append(t("sellers_kind_err"))
    return lines + ["", t("sellers_note")]


def _tutorial_lines(tu: dict) -> list[str]:
    if tu.get("skipped") or not (tu.get("leads") or tu.get("errors")):
        return []
    lines = ["", t("tut_h"), ""]
    for lead in tu.get("leads") or []:
        lines.append(t("tut_lead", term=lead["term"], n=lead["comments"]))
        lines += [f"  - {g['gap']} ({t('gap_' + g['kind'].replace(' ', '_'))}, {g['count']}){' → ' + g['phrase'] if g['phrase'] else ''}"
                  for g in lead["gaps"]]
    if tu.get("errors"):
        lines.append(t("tut_err", why="; ".join(tu["errors"][:3])))
    return lines


def pains(result: dict) -> str:
    """The `pains` command: the gaps people point at for a kind of tool."""
    by = result["by_source"]
    lines = [t("pains_h", keyword=result["keyword"]), "",
             t("pains_src", chrome=by["chrome"], reddit=by["reddit"], youtube=by["youtube"]), ""]
    if result["gaps"]:
        lines += [t("pains_cols"), "|---|---|---|---|---|"]
        for g in result["gaps"]:
            q = g["quotes"][0]
            lines.append(f"| {_cell(g['gap'])} | {t('gap_' + g['kind'].replace(' ', '_'))} | {g['count']} | {g['phrase'] or t('dash')} | "
                         f"[{_cell(q['text'][:90])}]({q['url']}) |")
    else:
        lines.append(t("pains_none"))
    if result["errors"]:
        lines += ["", t("pains_err", why="; ".join(result["errors"][:4]))]
    lines += ["", t("pains_note"), t("cost", cost=_cost(result))]
    return "\n".join(lines) + "\n"


def _gsc_lines(gsc: dict) -> list[str]:
    if gsc.get("off"):
        return []
    lines = ["", t("gsc_h"), ""]
    if not gsc.get("queries"):
        return lines + [t("recent_none", why=_state(gsc, t("gsc_none")))]
    lines += [t("gsc_intro", window=gsc["window"], total=gsc["total_new"], min=gsc["min_impressions"]), "",
              t("gsc_cols"), "|---|---|---|---|"]
    return lines + [f"| {_cell(q['query'])} | {q['impressions']} | {q['clicks']} | {q['page']} |" for q in gsc["queries"]]


def _review_lines(cfg: dict, rev: dict, summ: dict) -> list[str]:
    days = cfg["review"]["after_days"]
    lines = ["", t("review_h", days=days), ""]
    if rev.get("checked"):
        lines += [t("review_cols"), "|---|---|---|---|"]
        lines += [f"| {c['term']} | {c['first_seen']} | {c['verdict']} | {c['lead_days'] if c['lead_days'] is not None else t('dash')} |"
                  for c in rev["checked"]]
    else:
        lines.append(t("review_none", why=_state(rev, t("review_young", days=days))))
    if summ.get("by_signal"):
        lines += ["", t("hit_intro", days=summ["window_days"], pending=summ["pending"]), "", t("hit_cols"), "|---|---|---|---|---|"]
        for k, s in sorted(summ["by_signal"].items(), key=lambda kv: KINDS.index(kv[0]) if kv[0] in KINDS else 99):
            label = t(f"kind_{k}") if k in KINDS else k
            lines.append(f"| {label} | {s['checked']} | {s['hit']} | {s['hit'] / s['checked']:.0%} | "
                         f"{s['median_lead'] if s['median_lead'] is not None else t('dash')} |")
    return lines


def _status_lines(b: dict[str, dict], extra: dict[str, dict]) -> list[str]:
    x, hf, bo, sm = b["x"], b["hf"], b["breakout"], b["sitemap"]
    lines = ["", t("status_h"), ""]
    if not x.get("skipped"):
        ok = "" if x.get("error") else t("st_x_ok", answered=x["answered"], accounts=x["accounts"], posts=x["posts"]) + \
            (t("st_x_first") if x.get("first_run") else "")
        lines.append(t("st_x", state=_state(x, ok)))
    if not hf.get("skipped"):
        ok = "" if hf.get("error") else t("st_hf_ok", models=hf["models"], spaces=hf.get("spaces", 0)) + (t("st_first") if hf.get("first_run") else "")
        lines.append(t("st_hf", state=_state(hf, ok)))
    ok = "" if bo.get("error") or bo.get("skipped") else t("st_breakout_ok", n=bo["searched"]) + \
        (t("st_breakout_first") if bo.get("first_run") else "")
    lines.append(t("st_breakout", state=_state(bo, ok)))
    sl = b.get("seller", {"skipped": True})
    if not sl.get("skipped"):
        lines.append(t("st_sellers", state=_state(sl, "" if sl.get("error") else t("st_sellers_ok", links=sl["links"], old=sl.get("old", 0), new=sl["new"]))))
    for key, label in (("builder", "st_builders"), ("feed", "st_feeds"), ("money", "st_money")):
        blk = b.get(key, {"skipped": True})
        if not blk.get("skipped"):
            errs = blk.get("errors") or []
            lines.append(t(label, state=blk.get("error") or ("; ".join(errs[:3]) if errs else "ok")))
    ak = b.get("ask", {"skipped": True})
    if not ak.get("skipped"):
        lines.append(t("st_asks", state=_state(ak, "" if ak.get("error") else t("st_asks_ok", read=ak["read"], asks=ak["asks"]))))
    rv = b.get("revenue", {"skipped": True})
    if not rv.get("skipped") or rv.get("no_key"):
        ok = t("revenue_nokey_short") if rv.get("no_key") else "" if rv.get("error") else t("st_revenue_ok", n=rv["read"]) + \
            (t("st_first") if rv.get("first_run") else "")
        lines.append(t("st_revenue", state=_state(rv, ok) if not rv.get("no_key") else ok))
    for site, s in sm.get("sites", {}).items():
        state = s.get("error") or (t("st_site_first") if s.get("first_run") else t("st_site_ok", urls=s["urls"], new=s["new"]))
        lines.append(t("st_site", site=site, state=state))
    if sm.get("error"):
        lines.append(t("st_sitemaps", state=sm["error"]))
    if extra.get("judge", {}).get("error"):
        lines.append(t("st_judge", state=extra["judge"]["error"]))
    br = extra.get("brief") or {}
    if br.get("error"):
        lines.append(t("st_brief", state=br["error"]))
    elif br:
        lines.append(t("st_brief", state=t("st_brief_skipped") if br.get("skipped")
                       else t("st_brief_ok", n=br.get("briefed", 0), rules=br.get("by_rules", 0))))
    if extra.get("record", {}).get("error"):
        lines.append(t("st_record", state=extra["record"]["error"]))
    timed = [(k, v["seconds"]) for k, v in [*b.items(), *extra.items()] if isinstance(v, dict) and v.get("seconds") is not None]
    slow = sorted(((k, sec) for k, sec in timed if sec >= 60), key=lambda kv: -kv[1])
    if timed:
        total = sum(sec for _, sec in timed)
        lines.append(t("st_time", total=_minutes(total), parts="、".join(f"{k} {_minutes(sec)}" for k, sec in slow) or t("dash")))
    return lines


def _minutes(seconds: int) -> str:
    return f"{seconds // 60} min" if seconds >= 60 else f"{seconds} s"


def daily(cfg: dict, lead: list[dict], b: dict[str, dict], gsc: dict, rev: dict, summ: dict, extra: dict[str, dict]) -> str:
    all_named = named(cfg, lead)
    by_term = {r["term"]: r for r in all_named}
    rows_by = {s: _rows(s, b, by_term) for s in SOURCES}       # one read per source: the chapters and the count agree
    lines = [t("title"), "", t("overview", words=len(all_named), items=sum(len(v) for v in rows_by.values()),
                               sources=len([s for s in SOURCES if rows_by[s]]), total=len(SOURCES),
                               cost=_cost(b["x"], rev, b.get("newsite", {}), b.get("ask", {}), b.get("seller", {}),
                                          extra.get("usecases", {}), extra.get("tutorials", {}), b.get("builder", {}),
                                          b.get("feed", {}), b.get("money", {}), extra.get("sidelights", {}),
                                          extra.get("tails", {}))),
             ""]
    top = sorted(all_named, key=lambda r: -(r.get("named") or 0))[:TOP_SHOWN]
    if top:
        lines += [f"# {t('ch_top')}", ""]
        for i, r in enumerate(top, 1):
            src = " · ".join(t("src_" + s) for s in SOURCES if _from_source(r, s)) or t("dash")
            lines.append(f"{i}. " + _line(r["term"], _what(r) or _about(r["term"], b), src, r))
        lines.append("")
    for source in SOURCES:
        rows = rows_by[source]
        lines += ["", f"# {t('src_' + source)}", ""]
        if rows:
            lines += [t("src_count", n=len(rows)), ""]
            for i, (name, what, number, r) in enumerate(rows[:CHAPTER_SHOWN], 1):
                lines.append(f"{i}. " + _line(name, what, number, r))
            if len(rows) > CHAPTER_SHOWN:
                lines.append(t("ch_more", n=len(rows) - CHAPTER_SHOWN))
        else:
            lines.append(_chapter_state(source, b, cfg) or t("src_empty"))
    if any(_marks(r) for r in all_named):
        lines += ["", t("tags_note")]
    topics = topic_lines(cfg, lead, b, gsc)
    if topics:
        lines += ["", f"# {t('ch_topics')}"] + topics
    if not b["breakout"].get("skipped"):
        lines += ["", f"# {t('src_breakout')}"] + _body(_breakout_lines(b["breakout"], cfg))
    for key, body in (("ch_sidelights", _body(_side_lines(extra.get("sidelights", {"skipped": True})))),
                      ("ch_money", _body(_money_lines(b.get("money", {"skipped": True})))),
                      ("ch_tails", _body(_tail_lines(extra.get("tails", {"skipped": True})))),
                      ("ch_tutorials", _body(_tutorial_lines(extra.get("tutorials", {"skipped": True})))),
                      ("ch_gsc", _body(_gsc_lines(gsc)))):
        if body:
            lines += ["", f"# {t(key)}", ""] + body
    lines += ["", f"# {t('ch_review')}"] + _body(_review_lines(cfg, rev, summ))
    lines += ["", f"# {t('ch_status')}"] + _body(_status_lines(b, extra))
    rest = [r for r in lead if r not in all_named]
    if rest:
        lines.append(t("st_rest", n=len(rest)))
    lines.append(t("cost", cost=_cost(b["x"], rev, b.get("newsite", {}), b.get("ask", {}), b.get("seller", {}), extra.get("usecases", {}),
                                      extra.get("tutorials", {}), b.get("builder", {}), b.get("feed", {}), b.get("money", {}),
                                      extra.get("sidelights", {}), extra.get("tails", {}))))
    return "\n".join(lines) + "\n"


def _page_one(comp: dict | None) -> str:
    """The page-one cell: verdict, weak results, difficulty, ads."""
    if not comp:
        return t("dash")
    bits = [t("pc_" + comp["verdict"])]
    if comp.get("weak") is not None:
        bits.append(t("pc_weak", n=comp["weak"]))
    if comp.get("kd") is not None:
        bits.append(t("pc_kd", kd=comp["kd"]))
    if comp.get("ads"):
        bits.append(t("pc_ads"))
    if comp.get("built") is not None:
        bits.append(t("pc_built", n=f"{comp['built']:,}"))
    if comp.get("paid"):
        bits.append(t("pc_paid", n=len(comp["paid"])))
    return " · ".join(bits + _features(comp))


FEATURES = ((("ai_overview",), "sf_ai"), (("featured_snippet", "answer_box"), "sf_answer"),
            (("discussions_and_forums",), "sf_forums"), (("video", "short_videos"), "sf_video"), (("top_stories",), "sf_news"))


def _features(comp: dict) -> list[str]:
    """Marks for what holds page one besides the ten results; forum threads among the results count as forums."""
    have = set(comp.get("features") or []) | ({"discussions_and_forums"} if comp.get("forums") else set())
    return [t(key) for types, key in FEATURES if have & set(types)]


BRACKETS = str.maketrans("[]", "()")


def _age(r: dict) -> str:
    """The first-searched cell: the week the term first drew interest, 🆕 when recent."""
    a = r.get("age")
    if not a or a.get("no_data"):
        return t("dash")
    if a.get("since_start"):
        return t("age_before", day=a["first_seen"][:7])
    return a["first_seen"] + (" " + t("age_new") if a.get("is_new") else "")


def _num(n: int) -> str:
    return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k" if n >= 1000 else str(n)


def _markets(m: dict | None) -> str:
    """The markets cell, compact: best market first, then searches/KD per market, then the top region."""
    if not m or not m.get("by"):
        return t("dash")
    bits = [f"**{t('mk_best', code=m['best'])}**"] if m.get("best") else []
    bits += [f"{code} {_num(v['volume'])}" + (f"/{v['kd']}" if v.get("kd") is not None else "") for code, v in m["by"].items()]
    if m.get("top_region"):
        bits.append(t("mk_top", name=m["top_region"]["name"]))
    return " · ".join(bits)


def _serp(sv: dict | None) -> str:
    """The page-one shape cell: verdict, homepages against inner pages, platforms, exact titles."""
    if not sv or not sv.get("verdict"):
        return t("dash")
    bits = [t("ss_" + sv["verdict"].replace("-", "_")), t("ss_counts", home=sv["homepages"], inner=sv["inner"], plat=sv["platforms"])]
    if sv.get("wrapped"):
        bits.append(t("ss_redirect", n=sv["wrapped"]))
    if sv.get("unread"):
        bits.append(t("ss_unread", n=sv["unread"]))
    if sv.get("exact_titles"):
        bits.append(t("ss_exact", n=sv["exact_titles"]))
    if sv.get("exact_home"):
        bits.append(t("ss_exact_home"))
    return " · ".join(bits)


def _extra_lines(cfg: dict, uc: dict, notes: bool = True) -> list[str]:
    """Under the table: what the three extra columns mean, #1 and #2 of the prioritized rows, failures."""
    rows = uc["rows"]
    lines = []
    if notes and any(r.get("age") or r.get("markets") or r.get("serp") for r in rows):
        lines.append(t("extra_note", days=cfg["word_age"]["new_days"], platforms=", ".join(cfg["serp_shape"]["platforms"])))
    tops = [(r["phrase"], r["serp"]["top"]) for r in rows if (r.get("serp") or {}).get("top")]
    if tops:
        link = lambda x: f"[{_cell(x['title']).translate(BRACKETS)[:70] or x['url']}]({x['url']})" if x and x["url"] else t("dash")  # noqa: E731
        lines += ["", t("ss_top_h"), *[t("ss_top", phrase=ph, one=link(top[0]), two=link(top[1] if len(top) > 1 else None)) for ph, top in tops]]
    if uc.get("extra_errors"):
        lines += ["", t("ex_err", names="; ".join(uc["extra_errors"]))]
    return lines


def _pct(n: int | None) -> str:
    return "?" if n is None else f"{n:+d}%"


def _year(y: dict | None) -> str:
    """The twelve-month cell: the curve, then its word."""
    if not y:
        return t("dash")
    label = y["label"]
    if label in ("rising", "falling"):
        n, chg = (6, y["c6"]) if y.get("c6") is not None else (3, y.get("c3"))
        word = t("yr_" + label, chg=_pct(chg), n=n)
    elif label == "spiked":
        word = t("yr_spiked", month=y["peak"], chg=_pct(y["from_peak"]))
    else:
        word = t("yr_" + label)
    if y.get("since"):
        word = t("yr_new", month=y["since"]) + " · " + word
    return f"{y['spark']} {word}".strip()


def _yours(y: dict | None) -> str:
    """After the decision: where your site ranks already, and so the action."""
    if not y:
        return ""
    where = (t("yo_serp", pos=y["serp"]["position"]) if y.get("serp")
             else t("yo_gsc", pos=y["console"]["position"]) if y.get("console") else "")
    return (f" · {where}" if where else "") + " → " + t("yo_" + y["action"])


def _own_lines(cfg: dict, rows: list[dict]) -> list[str]:
    """Under the table: what the → means, and the pages of yours that were found."""
    read = [r for r in rows if r.get("yours")]
    if not read:
        return []
    lines = ["", t("yo_note", domains=", ".join(yours.own_domains(cfg)))]
    found = [r for r in read if r["yours"]["serp"] or r["yours"]["console"]]
    if found:
        lines += ["", t("yo_h")]
    for r in found:
        y, bits = r["yours"], []
        if y["serp"]:
            bits.append(t("yo_serp_line", pos=y["serp"]["position"], url=y["serp"]["url"]))
        if y["console"]:
            c = y["console"]
            bits.append(t("yo_console_line", pos=c["position"], imp=c["impressions"], clicks=c["clicks"], days=cfg["yours"]["days"], url=c["page"]))
        lines.append(f"- **{r['phrase']}**: " + "; ".join(bits))
    return lines


def _thread_lines(rows: list[dict], notes: bool = True) -> list[str]:
    """Under the table: the note on answers above the results, and the forum threads on page one, best-of searches first."""
    comps = [r.get("competition") or {} for r in rows]
    lines = ["", t("sf_note")] if notes and any({"ai_overview", "featured_snippet", "answer_box"} & set(c.get("features") or []) for c in comps) else []
    threaded = sorted((r for r in rows if (r.get("competition") or {}).get("forums")), key=lambda r: not competition.LIST.search(r["phrase"]))
    if threaded:
        lines += ["", t("sf_forums_h")]
    for r in threaded:
        links = " · ".join(f"[{_cell(f['title'] or f['domain']).translate(BRACKETS)[:70]}]({f['url']})" for f in r["competition"]["forums"][:3])
        lines.append(f"- **{r['phrase']}**{t('sf_list') if competition.LIST.search(r['phrase']) else ''}: {links}")
    return lines


def _dot(d: dict) -> str:
    if not d["taken"]:
        return t("dc_free", domain=d["domain"])
    return t("dc_taken", domain=d["domain"], day=d["registered"]) if d.get("registered") else t("dc_taken_nodate", domain=d["domain"])


def _more_lines(cfg: dict, uc: dict, notes: bool = True) -> list[str]:
    """Under the table, 0.7's readings: the twelve months, your pages, page-one features and threads, the .com."""
    rows = uc["rows"]
    lines = ["", t("yr_note")] if notes and any(r.get("year") for r in rows) else []
    lines += _own_lines(cfg, rows) + _thread_lines(rows, notes)
    checked = [r for r in rows if r.get("dot_com")]
    if checked:
        lines += ["", t("dc_h"), *[f"- **{r['phrase']}**: " + " · ".join(_dot(d) for d in r["dot_com"]) for r in checked], t("dc_note")]
    return lines


def _page_one_lines(cfg: dict, uc: dict, notes: bool = True) -> list[str]:
    rows = [r for r in uc["rows"] if r.get("competition")]
    if not rows and not uc.get("competition_errors"):
        return []
    lines = [t("pc_note", dr=cfg["competition"]["weak_dr"])] if notes else []
    if rows and all(r["competition"].get("weak") is None for r in rows):
        lines.append(t("pc_no_dr"))
    weakest = [r for r in rows if r["competition"].get("weakest")]
    if weakest:
        lines += ["", t("pc_weakest_h")]
        for r in weakest:
            w, kinds = r["competition"]["weakest"], r["competition"]["kinds"]
            key = "pc_weakest" if w["dr"] < cfg["competition"]["weak_dr"] else "pc_weakest_strong"
            lines.append(t(key, phrase=r["phrase"], domain=w["domain"], dr=w["dr"], pos=w["position"],
                           kinds=", ".join(f"{t('pk_' + k)} {n}" for k, n in sorted(kinds.items(), key=lambda x: -x[1])))
                         + (t("pc_paid_who", who=", ".join(r["competition"]["paid"][:3])) if r["competition"].get("paid") else ""))
    if uc.get("competition_errors"):
        lines.append(t("pc_err", names="; ".join(uc["competition_errors"])))
    return lines


def _word_mark(r: dict) -> str:
    """What it makes, then 🔎 when Trends related queries turned it up and ⚠ when it carries a brand."""
    return MARK[opportunity.fmt({"term": r["phrase"]})] + (" 🔎" if r.get("source") == "searched" else "") + \
        (" ⚠" if r["kind"] == "generic" and r.get("brand") else "")


def _word_lines(i: int, r: dict, uc: dict, origins: dict[str, list[str]] | None = None) -> list[str]:
    """One word in up to three lines: what it is and the call, how big it is, and how hard page one looks.
    A reader decides from this, so a field that was not read is left out rather than printed as a dash."""
    generic = r["kind"] == "generic"
    none = r.get("no_data")
    behind = t("uc_behind", names=", ".join(r["names"])) if generic and r["names"] else ""
    head = t("uc_word", i=i, phrase=r["phrase"], mark=_word_mark(r),
             kind=t("uc_type_generic" if generic else "uc_type_name"), behind=(" · " + behind) if behind else "",
             decision=t("uc_" + r["decision"]) + (" ↓" if r.get("demoted") else "") + _yours(r.get("yours")))
    size = t("uc_pd", n=r["per_day"]) if "per_day" in r and not none else t("uc_pd_none")
    big = [x for x in (_year(r["year"]) if r.get("year") else "", size,
                       t("uc_start", day=r["started"]) if r.get("started") else "",
                       t("uc_peak", day=r["peak_day"]) if r.get("peak_day") else "",
                       t("uc_mom", m=r["momentum"]) if r.get("momentum") is not None else "",
                       (t("uc_now_geo", now=t("uc_now_" + r["now"]), geo=uc["geo"]) if r.get("trend_geo")
                        else t("uc_now_" + r["now"])) if r.get("now") and not none else "") if x]
    age = "" if none else _age(r)
    demand = [x for x in (t("uc_mk", markets=_markets(r["markets"])) if r.get("markets") else "",
                          t("uc_first", day=age) if age and age != t("dash") else "") if x]
    page = [x for x in (t("uc_pc", page=_page_one(r["competition"])) if r.get("competition") else "",
                        t("uc_shape", shape=_serp(r["serp"])) if r.get("serp") else "") if x]
    out = [head]
    if origins is not None and not generic:      # a name: the source and the item that produced it
        came = origins.get((r["phrase"] or "").lower()) or []
        out.append(t("uc_origin", items=" · ".join(came[:2])) if came else t("uc_origin_none"))
    out += [x for x in (" · ".join(big) if big else "", " · ".join(demand) if demand else "",
                        " · ".join(page) if page else "") if x]
    return [x + "  " for x in out[:-1]] + out[-1:]      # hard breaks when the report is rendered


def keyword_table(cfg: dict, uc: dict, notes: bool = True, origins: dict[str, list[str]] | None = None) -> list[str]:
    """The day's words, the names read and the generic terms behind them, one block each with a decision."""
    if uc.get("skipped"):
        return []
    lines = ["", t("uc_h"), ""]
    if uc.get("error"):
        return lines + [uc["error"]]
    if not uc.get("names"):
        return lines + [t("uc_none")]
    c = cfg["usecases"]
    if usecases.degraded(uc):
        lines += [t("uc_degraded"), ""]
    lines += [t("uc_intro", names=", ".join(uc["names"]), proposed=uc["proposed"], relevant=uc["relevant"], kept=uc["kept"], min=c["min_volume"],
                month=uc["volume_month"] or "?"),
              t("uc_bench", bench=uc["benchmark"], bench_daily=uc["bench_daily"]) if uc.get("bench_daily") else t("uc_bench_none", bench=uc["benchmark"]), ""]
    for i, r in enumerate(uc["rows"], 1):
        lines += _word_lines(i, r, uc, origins)
    lines += ["", t("uc_rules", min_daily=c["min_daily"])]
    lines += _page_one_lines(cfg, uc, notes)
    lines += _extra_lines(cfg, uc, notes)
    lines += _more_lines(cfg, uc, notes)
    if any(r["kind"] == "generic" and r["brand"] for r in uc["rows"]):
        lines.append(t("uc_brand_note"))
    if any(r.get("trend_geo") for r in uc["rows"]):
        lines.append(t("uc_geo_note", geo=uc["geo"]))
    if uc.get("country_errors"):
        lines.append(t("uc_geo_err", names="; ".join(uc["country_errors"])))
    if any(r.get("source") == "searched" for r in uc["rows"]):
        lines.append(t("uc_searched_note"))
    said = [f"- **{r['phrase']}** ({', '.join(r['names'])}): “{_cell(r['evidence'])}”" for r in uc["rows"]
            if r["kind"] == "generic" and r["evidence"] and r.get("source") != "searched"]
    if said:
        lines += ["", t("uc_said_h"), *said]
    if uc.get("tails"):
        lines += ["", t("uc_tails_h"), *[f"- **{n}**: {', '.join(v[:10])}" for n, v in uc["tails"].items()]]
    if uc.get("cosearch"):
        lines += ["", t("uc_cosearch_h") + " " + ", ".join(t("uc_cosearch_item", term=x["term"], name=x["with"]) for x in uc["cosearch"])]
    if uc.get("no_evidence"):
        lines += ["", t("uc_no_evidence", names=", ".join(uc["no_evidence"]))]
    if uc.get("posts_error"):
        lines += ["", t("uc_posts_err", why=uc["posts_error"])]
    if uc.get("related_errors"):
        lines += ["", t("uc_related_err", names="; ".join(uc["related_errors"]))]
    elif not uc.get("related"):
        lines += ["", t("uc_related_off")]
    return lines


def usecase_leads(uc: dict) -> list[dict]:
    """The generic terms as leads, for the 14-day review."""
    return [{"term": r["phrase"], "kinds": ["usecase"], "variants": [r["phrase"]],
             "signals": [t("note_usecase", names=", ".join(r["names"]), volume=r.get("volume", 0))]}
            for r in uc.get("rows", []) if r["kind"] == "generic"] + \
        [{"term": x["term"], "kinds": ["cosearch"], "variants": [x["term"]], "signals": [t("note_cosearch", name=x["with"])]}
         for x in uc.get("cosearch", [])]


def _clip(text: str, n: int) -> str:
    """Cut at a word boundary with an ellipsis, not mid-word."""
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    return (cut if len(cut) > n // 2 else text[:n]) + "…"


def posts_lines(rows: list[dict]) -> list[str]:
    """Each term's posts in full, with a link: what was said and where, without opening X."""
    lines = []
    for r in rows:
        for p in r.get("posts", [])[:POSTS_SHOWN]:
            if not lines:
                lines += ["", t("posts_h"), ""]
            link = t("post_link", url=p["url"]) if p.get("url") else ""
            lines.append(f"- **{r['term']}** · @{p['account']} ♥{p['likes']}{link}  \n  {p['text']}")
    return lines


def sources(cfg: dict, lead: list[dict], b: dict[str, dict], extra: dict[str, dict]) -> str:
    lines = [t("sources_title"), "", t("sources_cols"), "|---|---|---|---|---|"]
    top = named(cfg, lead)[:SHOWN]
    for r in top:
        ex = _cell("<br>".join(_clip(e, 60) for e in r["examples"][:2]))
        lines.append(f"| **{r['term']}** | {'; '.join(r['signals'])} | {_score(r)} | {r['known'] or t('none')} | {ex} |")
    lines += posts_lines(top)
    lines.append("")
    for key, label in (("x", "st_x"), ("hf", "st_hf")):
        if b[key].get("error"):
            lines.append(t(label, state=b[key]["error"]))
    for key, label in (("judge", "st_judge"), ("record", "st_record")):
        if extra.get(key, {}).get("error"):
            lines.append(t(label, state=extra[key]["error"]))
    lines.append(t("cost", cost=_cost(b["x"])))
    return "\n".join(lines) + "\n"
