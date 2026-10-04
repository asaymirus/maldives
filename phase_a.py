"""Phase A: Crown & Champa sales portal + Neoscapes DMC (high-yield confirmed sources)."""
import re, sys, json, os
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import lib
from lib import log, get, fetch_text, enqueue, save_page, extract_pdf_links, record_source, record_blocked, jsonl_append
from resorts import match_resort, RESORTS

CC = "https://sales.crownandchamparesorts.com"
CC_HINT = {"hurawalhi": 30, "kagi": 71, "kudadoo": 28, "kuredu": 81, "komandoo": 79, "jawakara": [29, 83],
           "innahura": 31, "meeru": 78, "veligandu": 38, "veli": 38, "vilamendhoo": 174, "mirihi": 172,
           "dheruhfinolhu": 29, "mabinhura": 83, "nala": None}


def cc_hint(s):
    s = s.lower()
    for k, v in CC_HINT.items():
        if k in s:
            return v
    return None


def crown_champa():
    found = matched = 0
    # 1. WP media API
    page = 1
    while True:
        r = get(f"{CC}/wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&page={page}", timeout=60)
        if r is None or not r.ok:
            break
        try:
            items = r.json()
        except Exception:
            break
        if not items:
            break
        for it in items:
            u = it.get("source_url")
            if not u:
                continue
            found += 1
            title = (it.get("title") or {}).get("rendered", "")
            hint = cc_hint(u + " " + title)
            if hint is None and "nala" in (u + title).lower():
                jsonl_append(lib.EXTRAS, {"url": u, "title": title, "note": "Nala Maldives (Crown & Champa, not in list)", "date": lib.TODAY})
                continue
            matched += 1
            enqueue(u, "sales.crownandchamparesorts.com", "brand-cdn", f"{CC}/wp-json/wp/v2/media", hint,
                    {"wp_title": title, "wp_date": it.get("date")})
        page += 1
        if page > 20:
            break
    log.info("Crown&Champa media API: %d pdfs", found)
    # 2. per-resort sections and gallery pages
    html, _ = fetch_text(CC + "/")
    sections = set()
    if html:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            u = urljoin(CC, a["href"])
            if urlparse(u).netloc == urlparse(CC).netloc and u.count("/") >= 3 and not u.endswith((".pdf", ".jpg", ".png")):
                sections.add(u.split("?")[0])
    for key in CC_HINT:
        sections.add(f"{CC}/{key}/")
    # sitemap too
    for sm in ("/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap.xml", "/page-sitemap.xml"):
        t, r = fetch_text(CC + sm, timeout=30)
        if t and "<loc>" in t:
            for loc in re.findall(r"<loc>(.*?)</loc>", t):
                if loc.endswith(".xml"):
                    t2, _ = fetch_text(loc, timeout=30)
                    if t2:
                        sections.update(l for l in re.findall(r"<loc>(.*?)</loc>", t2) if not l.lower().endswith((".jpg", ".png", ".pdf")))
                else:
                    sections.add(loc)
    log.info("Crown&Champa: %d section pages", len(sections))
    for u in sorted(sections):
        t, r = fetch_text(u, timeout=60)
        if not t:
            continue
        hint = cc_hint(u)
        rid = hint if isinstance(hint, int) else (hint[0] if isinstance(hint, list) else None)
        if rid:
            save_page(rid, u, t, source_type="brand-cdn")
            if isinstance(hint, list):
                save_page(hint[1], u, t, source_type="brand-cdn")
        for pdf in extract_pdf_links(t, u):
            found += 1
            h = cc_hint(pdf) or hint
            if enqueue(pdf, "sales.crownandchamparesorts.com", "brand-cdn", u, h):
                matched += 1
    record_source("sales.crownandchamparesorts.com", "wp-media-api+crawl", "ok", found, matched)
    return found


def neoscapes():
    base = "https://www.neoscapesmaldives.com"
    urls = set()
    for sm in ("/sitemap_index.xml", "/resort-sitemap.xml", "/sitemap.xml", "/wp-sitemap.xml"):
        t, r = fetch_text(base + sm, timeout=60)
        if not t or "<loc>" not in t:
            continue
        for loc in re.findall(r"<loc>(.*?)</loc>", t):
            if loc.endswith(".xml"):
                t2, _ = fetch_text(loc, timeout=60)
                if t2:
                    urls.update(l for l in re.findall(r"<loc>(.*?)</loc>", t2) if "/resort/" in l)
            elif "/resort/" in loc:
                urls.add(loc)
    if not urls:
        # fall back: crawl listing pages
        t, r = fetch_text(base + "/resorts/", timeout=60)
        if t:
            urls.update(u for u in extract_links(t, base) if "/resort/" in u)
    log.info("Neoscapes: %d resort pages", len(urls))
    found = matched = 0
    for u in sorted(urls):
        t, r = fetch_text(u, timeout=60)
        if not t:
            if r is not None and urlparse(u).netloc.lower() in lib.BLOCKED_HOSTS:
                record_blocked("neoscapesmaldives.com", "GET resort page", str(r.status_code))
                break
            continue
        slug = u.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
        soup = BeautifulSoup(t, "lxml")
        h1 = soup.find("h1")
        name = h1.get_text(" ", strip=True) if h1 else slug
        ids, review = match_resort(name + " " + slug)
        rid = ids[0] if ids and not review else None
        if ids and review:
            # pick by name similarity to h1
            rid = ids[0]
        if rid is None:
            jsonl_append(lib.EXTRAS, {"url": u, "title": name, "note": "Neoscapes resort not in list", "date": lib.TODAY})
        else:
            save_page(rid, u, t, "overview", source_type="dmc-agency")
        pdfs = extract_pdf_links(t, u)
        for pdf in pdfs:
            found += 1
            if enqueue(pdf, "neoscapesmaldives.com", "dmc-agency", u, rid if rid else None):
                matched += 1 if rid else 0
    record_source("neoscapesmaldives.com", "sitemap+pages", "ok", found, matched)


def extract_links(html, base):
    soup = BeautifulSoup(html, "lxml")
    return {urljoin(base, a["href"]).split("#")[0] for a in soup.find_all("a", href=True)}


if __name__ == "__main__":
    which = sys.argv[1:] or ["cc", "neo", "run"]
    if "cc" in which:
        crown_champa()
    if "neo" in which:
        neoscapes()
    if "run" in which:
        lib.run_queue(source_filter={"brand-cdn", "dmc-agency"})
        lib.print_progress()
        lib.run_log("A", "Crown & Champa + Neoscapes")
