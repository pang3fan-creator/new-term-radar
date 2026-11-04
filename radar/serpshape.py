"""SERP shape: what kind of pages hold page one, for the terms rated prioritize.

From the live top ten organic results (DataForSEO through AIsa, US / en / desktop by
default; the page-one check's own results are reused when it read the same market):

- `homepages` and `inner`: a result at a site's root ("/", "/index.html", a bare locale
  such as "/en/") is a homepage; anything deeper is an inner page. A site that put its
  homepage on the term has built for it; an inner page is a post or a section that a page
  made for the term can outrank (a hit Google wrapped in its own redirect has no readable
  path and counts as neither);
- `platforms`: results on high-authority platforms (github.com, medium.com, reddit.com,
  youtube.com, ..., configurable; "*.github.io" means its subdomains);
- `exact_titles`: results whose title holds the term as a phrase; `exact_home` when one
  of those, or a homepage whose domain spells the term, is a homepage;
- `top`: the URL and title of #1 and #2.

`verdict`: "platform-held" when half or more of the results sit on platforms (checked
first: platform pages are inner pages, but they carry their platform's authority);
"beatable" when most results are inner pages and no exact-match homepage is among them;
"contested" otherwise.

Cost seen in October 2026: about $0.002 a term when the page-one check has not read it already.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from . import aisa, competition

LOCALES = {"en", "de", "fr", "es", "it", "pt", "nl", "ja", "ko", "zh", "ru", "pl", "tr", "ar", "id", "vi", "th", "sv", "da", "no", "fi"}


def is_homepage(url: str) -> bool:
    """True for a site's root: no path, an index file, or a bare locale ("/en/", "/zh-cn")."""
    path = urlsplit(url if "//" in url else "//" + url).path.strip("/").lower()
    if not path or re.fullmatch(r"index\.\w+", path):
        return True
    return bool(re.fullmatch(r"([a-z]{2})(?:[-_][a-z]{2,4})?", path)) and path[:2] in LOCALES


def domain_of(url: str) -> str:
    return re.sub(r"^www\.", "", urlsplit(url if "//" in url else "//" + url).netloc.lower())


def on_platform(domain: str, platforms: list[str]) -> bool:
    domain = domain.lower()
    for p in platforms:
        p = p.lower()
        if p.startswith("*."):
            if domain.endswith(p[1:]):
                return True
        elif domain == p or domain.endswith("." + p):
            return True
    return False


def has_phrase(text: str, term: str) -> bool:
    return bool(term) and re.search(r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)", (text or "").lower()) is not None


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def shape(results: list[dict], term: str, platforms: list[str]) -> dict:
    """The shape of one page one. `results`: [{"url", "page"?, "title", "domain"?, "wrapped"?}] in rank order.
    Every result keeps its slot in the ten, including the ones read through Google's redirect
    ("wrapped", path unknown) and the ones whose site cannot be read at all ("unread"): a
    denominator made of the readable results only would call half-read pages beatable."""
    results = results[:10]
    if not results:
        return {"verdict": None, "results": 0}
    homes = [r for r in results if not r.get("wrapped") and is_homepage(r.get("url", ""))]
    wrapped = [r for r in results if r.get("wrapped")]          # a redirect hides the path: neither home nor inner
    unread = [r for r in results if r.get("wrapped") and not r.get("domain")]   # no site either: still one of the ten
    plat = [r for r in results if on_platform(r.get("domain") or domain_of(r.get("url", "")), platforms)]
    exact = [r for r in results if has_phrase(r.get("title", ""), term)]
    exact_home = any(has_phrase(r.get("title", ""), term)
                     or _squash(term) in _squash((r.get("domain") or domain_of(r.get("url", ""))).split(".")[0]) for r in homes)
    n, inner = len(results), len(results) - len(homes) - len(wrapped)
    if 2 * len(plat) >= n:
        verdict = "platform-held"
    elif 2 * inner > n and not exact_home:
        verdict = "beatable"
    else:
        verdict = "contested"
    return {"verdict": verdict, "results": n, "homepages": len(homes), "inner": inner, "platforms": len(plat),
            # read through a redirect (its path is unknown); the ones whose site cannot be read are counted as unread
            "wrapped": len(wrapped) - len(unread), "unread": len(unread),
            "exact_titles": len(exact), "exact_home": exact_home,
            # the address a reader can open: a result read through Google's redirect has no usable url
            "top": [{"url": competition.address(r), "title": r.get("title", "")} for r in results[:2]]}


def assess(rows: list[dict], cfg: dict) -> tuple[int, list[str]]:
    """Adds `serp` to each row given (the prioritized ones). (cost in micro-USD, errors)"""
    c = cfg["serp_shape"]
    if not c.get("enabled") or not rows:
        return 0, []
    cost, errors = 0, []
    for r in rows:
        comp = r.get("competition") or {}
        results = comp.get("results") if comp.get("location_code") == c["location_code"] and c["language_code"] == "en" \
            and c["device"] == "desktop" else None
        if not results:
            try:
                page, spent = competition.page_one(r["phrase"], c["location_code"], c["language_code"], c["device"])
                cost, results = cost + spent, page["results"]
            except aisa.AisaError as exc:
                errors.append(f"{r['phrase']} (SERP shape): {exc}")
                continue
        r["serp"] = shape(results, r["phrase"], c["platforms"])
    return cost, errors
