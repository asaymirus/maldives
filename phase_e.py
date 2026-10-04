"""Phase E: flipbook platforms (Issuu, Yumpu, Scribd, FlipHTML5) + search API gap filling (if a key is set).
We record document URL/title/date for every match; we store a file only when the platform offers a plain
public download (no login, no CAPTCHA). Otherwise metadata only."""
import os, re, sys, json
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup
import lib
from lib import log, get, enqueue, jsonl_append, record_source
from crawl import render
from resorts import RESORTS, BY_ID, match_resort, norm
from phase_b import commit

FLIP = os.path.join(lib.STATE, "flipbooks.jsonl")
PRIORITY_TYPES = ("factsheet", "wedding", "events")


def search_name(r):
    # shortest distinctive alias gives the best recall
    cands = [a for a in r["aliases"] if len(a) >= 5] or [r["name"]]
    return min(cands, key=len) if len(min(cands, key=len)) >= 5 else r["name"]


def issuu(r, done):
    q = search_name(r) + " maldives"
    url = f"https://issuu.com/search?q={quote_plus(q)}"
    if url in done:
        return 0
    html, final, pdfs = render(url, wait_ms=5000)
    n = 0
    if html:
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        for a in soup.find_all("a", href=re.compile(r"^/[^/]+/docs/[^/?#]+")):
            href = "https://issuu.com" + a["href"].split("?")[0]
            if href in seen:
                continue
            seen.add(href)
            title = a.get_text(" ", strip=True) or a.get("aria-label") or ""
            ids, review = match_resort(href + " " + title)
            if r["resort_id"] not in ids:
                continue
            n += 1
            jsonl_append(FLIP, {"platform": "issuu", "resort_id": r["resort_id"], "url": href, "title": title[:200],
                                "published": None, "download": None, "date": lib.TODAY, "query": q})
    jsonl_append(FLIP, {"platform": "issuu", "resort_id": r["resort_id"], "url": url, "title": "__search__", "hits": n, "date": lib.TODAY})
    return n


def yumpu(r, done):
    q = search_name(r) + " maldives"
    url = f"https://www.yumpu.com/en/search?q={quote_plus(q)}"
    if url in done:
        return 0
    html, final, pdfs = render(url, wait_ms=5000)
    n = 0
    if html:
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        for a in soup.find_all("a", href=re.compile(r"yumpu\.com/[a-z]{2}/document/(read|view)/")):
            href = a["href"].split("?")[0]
            if href in seen:
                continue
            seen.add(href)
            title = a.get_text(" ", strip=True) or a.get("title") or ""
            ids, review = match_resort(href + " " + title)
            if r["resort_id"] not in ids:
                continue
            n += 1
            jsonl_append(FLIP, {"platform": "yumpu", "resort_id": r["resort_id"], "url": href, "title": title[:200],
                                "published": None, "download": None, "date": lib.TODAY, "query": q})
    jsonl_append(FLIP, {"platform": "yumpu", "resort_id": r["resort_id"], "url": url, "title": "__search__", "hits": n, "date": lib.TODAY})
    return n


def scribd(r, done):
    q = search_name(r) + " maldives"
    url = f"https://www.scribd.com/search?query={quote_plus(q)}"
    if url in done:
        return 0
    html, final, pdfs = render(url, wait_ms=5000)
    n = 0
    if html:
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        for a in soup.find_all("a", href=re.compile(r"scribd\.com/(document|doc|presentation)/\d+")):
            href = a["href"].split("?")[0]
            if href in seen:
                continue
            seen.add(href)
            title = a.get_text(" ", strip=True) or ""
            ids, review = match_resort(href + " " + title)
            if r["resort_id"] not in ids:
                continue
            n += 1
            jsonl_append(FLIP, {"platform": "scribd", "resort_id": r["resort_id"], "url": href, "title": title[:200],
                                "published": None, "download": None, "date": lib.TODAY, "query": q})
    jsonl_append(FLIP, {"platform": "scribd", "resort_id": r["resort_id"], "url": url, "title": "__search__", "hits": n, "date": lib.TODAY})
    return n


def search_api(r, missing_types):
    """Brave or SerpAPI, only when a key is set."""
    brave = os.environ.get("BRAVE_API_KEY")
    serp = os.environ.get("SERPAPI_KEY")
    if not (brave or serp):
        return 0
    n = 0
    name = r["name"]
    for t in missing_types:
        word = {"factsheet": "factsheet", "wedding": "wedding", "events": "events"}[t]
        q = f'"{name}" {word} filetype:pdf'
        urls = []
        if brave:
            rr = get(f"https://api.search.brave.com/res/v1/web/search?q={quote_plus(q)}&count=10", timeout=30,
                     headers={"X-Subscription-Token": brave, "Accept": "application/json"})
            if rr is not None and rr.ok:
                urls = [x.get("url") for x in rr.json().get("web", {}).get("results", [])]
        elif serp:
            rr = get(f"https://serpapi.com/search.json?q={quote_plus(q)}&api_key={serp}&num=10", timeout=30)
            if rr is not None and rr.ok:
                urls = [x.get("link") for x in rr.json().get("organic_results", [])]
        for u in urls:
            if u and ".pdf" in u.lower():
                if enqueue(u, "search-api", "search", q, r["resort_id"]):
                    n += 1
    return n


def missing_priority(docs):
    have = {}
    for d in docs.values():
        for rid in d.get("resort_ids") or [d["resort_id"]]:
            have.setdefault(rid, set()).add(d["doc_type"])
    return {r["resort_id"]: [t for t in PRIORITY_TYPES if t not in have.get(r["resort_id"], set())] for r in RESORTS}


if __name__ == "__main__":
    only_gaps = "all" not in sys.argv
    docs = lib.load_docs()
    gaps = missing_priority(docs)
    done = {x["url"] for x in lib.jsonl_read(FLIP) if x.get("title") == "__search__"}
    total = 0
    for r in RESORTS:
        if only_gaps and not gaps[r["resort_id"]]:
            continue
        n = issuu(r, done) + yumpu(r, done) + scribd(r, done)
        n += search_api(r, gaps[r["resort_id"]])
        total += n
        log.info("E %3d %-40s flipbook hits=%d gaps=%s", r["resort_id"], r["name"][:40], n, gaps[r["resort_id"]])
    record_source("issuu.com/yumpu.com/scribd.com", "search-render", "ok", total, total, "metadata only")
    if not (os.environ.get("BRAVE_API_KEY") or os.environ.get("SERPAPI_KEY")):
        record_source("search-api", "brave/serpapi", "skipped", 0, 0, "no BRAVE_API_KEY / SERPAPI_KEY set")
    stats = lib.run_queue(source_filter={"search", "flipbook"})
    lib.print_progress()
    lib.run_log("E", f"flipbooks/search: {total} hits, {stats}")
    commit("Phase E: flipbooks + search API")
