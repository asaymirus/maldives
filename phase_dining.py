"""Targeted pass: destination-dining pages and PDFs on every reachable official site.
Looks for romantic / honeymoon / anniversary / beach / sandbank dinners, private dining, sandbank events,
destination-dining packages. Reuses crawl.sitemap_urls + the page/PDF pipeline; skips pages already saved."""
import re, sys
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import lib
from lib import log, fetch_text, enqueue, save_page, extract_pdf_links, jsonl_append
from crawl import sitemap_urls, internal_links, render, SITES, dam_links
from resorts import BY_ID

DINING_RX = re.compile(r"destination[-_ ]?dining|private[-_ ]?dining|romantic|romance|honeymoon|anniversary|sandbank|sand[-_ ]?bank|"
                       r"beach[-_ ]?dinner|dinner|dining[-_ ]?experience|special[-_ ]?occasion|celebrat|picnic|castaway|candle|"
                       r"under[-_ ]?the[-_ ]?stars|floating[-_ ]?breakfast|private[-_ ]?chef|bbq|barbecue|in[-_ ]?villa[-_ ]?dining|experiences?", re.I)
PAGE_TEXT_RX = re.compile(r"romantic (dinner|dining)|honeymoon dinner|anniversary dinner|beach dinner|sand ?bank (dinner|lunch|breakfast|picnic|event|celebration|experience)|"
                          r"destination dining|private dining|dine under the stars|candle ?lit dinner|floating breakfast|private chef|dinner on the beach", re.I)


def official_sites():
    out = {}
    for s in lib.jsonl_read(SITES):
        k = str(s.get("key", ""))
        if k.startswith("official:") and k.count(":") == 1 and s.get("status") in ("ok", "blocked-partial") and s.get("final_url"):
            out[int(k.split(":")[1])] = s["final_url"]
    return out


def done_pages():
    return {p["url"] for p in lib.jsonl_read(lib.PAGES_IDX)}


def run_site(rid, url, seen):
    host = urlparse(url).netloc.lower().replace("www.", "")
    cands = set()
    for u in sitemap_urls(url):
        pu = urlparse(u)
        if pu.netloc.lower().replace("www.", "") != host:
            continue
        if DINING_RX.search(pu.path) and not re.search(r"\.(jpe?g|png|gif|webp|svg|css|js)$", pu.path, re.I):
            cands.add(u)
    # also follow dining/experience links from the home page
    html, r = fetch_text(url, timeout=60)
    if html:
        for l in internal_links(html, url, {host}):
            if DINING_RX.search(urlparse(l).path):
                cands.add(l)
    n_pages = n_pdf = n_hits = 0
    for u in sorted(cands)[:40]:
        if u.lower().endswith(".pdf"):
            if enqueue(u, host, "official", url, rid):
                n_pdf += 1
            continue
        if u in seen:
            continue
        html, r = fetch_text(u, timeout=60)
        if html is None:
            if r is not None and r.ok and r.content[:5] == b"%PDF-":
                enqueue(u, host, "official", url, rid)
            continue
        text_len = len(re.sub(r"<[^>]+>", " ", html))
        if text_len < 2000:
            h2, f2, pdfs = render(u)
            if h2:
                html = h2
                for p in pdfs:
                    if enqueue(p, host, "official", u, rid):
                        n_pdf += 1
        ptype = "destination_dining" if PAGE_TEXT_RX.search(html) or re.search(r"romantic|honeymoon|anniversary|sandbank|sand-bank|private-dining|destination-dining", u, re.I) else None
        if save_page(rid, u, html, page_type=ptype, source_type="official"):
            n_pages += 1
            if ptype == "destination_dining":
                n_hits += 1
        for p in extract_pdf_links(html, u):
            if enqueue(p, host, "official", u, rid):
                n_pdf += 1
        for d in dam_links(html, u):
            if ".pdf" in d.lower() and enqueue(d, host, "official", u, rid):
                n_pdf += 1
    jsonl_append(SITES, {"key": f"dining:{rid}", "status": "ok", "pages": n_pages, "pdfs": n_pdf, "dining_pages": n_hits, "resort_ids": [rid], "date": lib.TODAY})
    return rid, n_pages, n_pdf, n_hits


if __name__ == "__main__":
    sites = official_sites()
    done = {int(s["key"].split(":")[1]) for s in lib.jsonl_read(SITES) if str(s.get("key", "")).startswith("dining:")}
    todo = {rid: u for rid, u in sites.items() if rid not in done}
    seen = done_pages()
    log.info("dining pass: %d official sites", len(todo))
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(run_site, rid, u, seen): rid for rid, u in todo.items()}
        for f in as_completed(futs):
            try:
                rid, np_, npdf, nh = f.result()
                log.info("DINING %3d %-38s pages=%d dining_pages=%d pdfs=%d", rid, BY_ID[rid]["name"][:38], np_, nh, npdf)
            except Exception:
                log.exception("dining pass failed %s", futs[f])
    if "crawl-only" not in sys.argv:
        stats = lib.run_queue()
        lib.print_progress()
        lib.run_log("B+", f"destination-dining pass: {stats}")
