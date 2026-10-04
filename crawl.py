"""Generic polite site crawler: sitemaps, WP media API, keyword-filtered BFS (depth 2), PDF + DAM link
collection, page text capture, and a Playwright fallback (headless Chromium, no stealth) for JS sites."""
import os, re, json, time, threading
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import lib
from lib import log, get, fetch_text, enqueue, save_page, extract_pdf_links, record_source, record_blocked, jsonl_append
from official_urls import DAM_HOSTS
from resorts import BY_ID, norm

PAGE_KEYS = re.compile(r"wedd|celebrat|romance|vow|honeymoon|event|meeting|mice|incentive|dining|restaurant|menu|bar\b|"
                       r"spa|wellness|dive|diving|water-?sport|snorkel|excursion|experience|activit|adventure|kids|family|"
                       r"children|villa|accommodation|room|suite|residence|factsheet|fact-sheet|download|brochure|media|press|"
                       r"gallery|offer|package|transfer|location|getting|about|overview|resort|island|sustainab|marine|"
                       r"conservation|wellbeing|retreat|yoga|fitness|surf|fishing|cruise|discover|explore|guide|map|plan|"
                       r"festive|calendar|programme|program|what|news|blog|faq|info", re.I)
SKIP_EXT = re.compile(r"\.(jpe?g|png|gif|webp|svg|css|js|ico|mp4|mov|woff2?|ttf|zip|xml|json|avif)(\?|$)", re.I)
SKIP_PATH = re.compile(r"/(wp-json|wp-admin|wp-login|feed|tag|author|cart|checkout|account|login|signin|booking|book-now|"
                       r"reservations?/|search|lang=|/fr/|/de/|/it/|/es/|/ru/|/zh/|/ja/|/ko/|/ar/|/pt/|/nl/|/pl/|/cs/|/tr/|/zh-)", re.I)
DAM_INDEX = os.path.join(lib.STATE, "dam_hosts.jsonl")
SITES = os.path.join(lib.STATE, "sites.jsonl")

_pw_lock = threading.Lock()
_pw = {"p": None, "browser": None}


def _browser():
    if _pw["browser"] is None:
        from playwright.sync_api import sync_playwright
        _pw["p"] = sync_playwright().start()
        exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
        kw = {"args": ["--no-sandbox"]}
        if os.path.exists(exe):
            kw["executable_path"] = exe
        if os.environ.get("HTTPS_PROXY"):
            kw["proxy"] = {"server": os.environ["HTTPS_PROXY"]}
        _pw["browser"] = _pw["p"].chromium.launch(**kw)
    return _pw["browser"]


def render(url, wait_ms=2500, click_downloads=True):
    """Render a page in headless Chromium. Returns (html, final_url, pdf_urls_seen_in_network)."""
    with _pw_lock:
        try:
            b = _browser()
            ctx = b.new_context(ignore_https_errors=True, user_agent=lib.UA, viewport={"width": 1366, "height": 900},
                                locale="en-GB")
            page = ctx.new_page()
            pdfs = set()

            def on_resp(resp):
                try:
                    ct = resp.headers.get("content-type", "")
                    u = resp.url
                    if "pdf" in ct or u.lower().split("?")[0].endswith(".pdf"):
                        pdfs.add(u)
                except Exception:
                    pass
            page.on("response", on_resp)
            ctx.on("page", lambda p: p.on("response", on_resp))
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            # scroll to trigger lazy loads
            for _ in range(4):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(400)
            # accept cookie banners (common selectors)
            for sel in ("button:has-text('Accept')", "button:has-text('ACCEPT')", "button:has-text('Agree')",
                        "button:has-text('I agree')", "#onetrust-accept-btn-handler", ".cc-btn.cc-dismiss"):
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=500):
                        el.click(timeout=1500)
                        break
                except Exception:
                    pass
            html = page.content()
            final = page.url
            # look for download-like anchors without .pdf and read their resolved href after JS
            try:
                hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => [e.href, e.textContent])")
                for h, t in hrefs:
                    tl = (t or "").lower()
                    if h and (".pdf" in h.lower() or ("download" in tl and "pdf" in tl) or
                              any(k in tl for k in ("factsheet", "fact sheet", "brochure")) and "download" in tl):
                        if ".pdf" in h.lower():
                            pdfs.add(h)
            except Exception:
                pass
            ctx.close()
            return html, final, pdfs
        except Exception as e:
            log.info("render fail %s %s", url, str(e)[:120])
            try:
                ctx.close()
            except Exception:
                pass
            return None, url, set()


def internal_links(html, base, allowed_hosts):
    out = set()
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return out
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        u = urljoin(base, href).split("#")[0]
        p = urlparse(u)
        if p.scheme not in ("http", "https"):
            continue
        host = p.netloc.lower().replace("www.", "")
        if host not in allowed_hosts:
            continue
        if SKIP_EXT.search(u) or SKIP_PATH.search(u):
            continue
        out.add(u)
    return out


def dam_links(html, base):
    """Links to digital asset managers / flipbook / cloud storage hosts."""
    found = set()
    for m in re.finditer(r"""https?://[^\s"'<>()]+""", html):
        u = m.group(0)
        hl = urlparse(u).netloc.lower()
        if any(d in hl or d in u.lower() for d in DAM_HOSTS):
            found.add(u.rstrip(".,);"))
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all(["a", "iframe"], href=True) + soup.find_all("iframe", src=True):
            u = urljoin(base, a.get("href") or a.get("src"))
            if any(d in u.lower() for d in DAM_HOSTS):
                found.add(u)
    except Exception:
        pass
    return found


def sitemap_urls(base_url, limit=400):
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    urls = set()
    seen = set()

    def read(sm, depth=0):
        if sm in seen or depth > 2 or len(urls) > limit * 3:
            return
        seen.add(sm)
        t, r = fetch_text(sm, timeout=45)
        if not t or "<loc>" not in t:
            return
        locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", t)
        for l in locs:
            l = l.strip()
            if l.lower().endswith(".xml") or "sitemap" in l.lower() and l.lower().endswith((".xml.gz",)):
                read(l, depth + 1)
            else:
                urls.add(l)
    for sm in ("/sitemap_index.xml", "/sitemap.xml", "/wp-sitemap.xml", "/sitemap-index.xml", "/page-sitemap.xml"):
        read(root + sm)
    # robots.txt sitemaps
    t, r = fetch_text(root + "/robots.txt", timeout=20)
    if t:
        for m in re.finditer(r"(?i)sitemap:\s*(\S+)", t):
            read(m.group(1))
    return urls


def wp_media_pdfs(base_url):
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    out = []
    for page in range(1, 15):
        r = get(f"{root}/wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&page={page}", timeout=45)
        if r is None or not r.ok:
            break
        try:
            items = r.json()
        except Exception:
            break
        if not isinstance(items, list) or not items:
            break
        for it in items:
            u = it.get("source_url")
            if u:
                out.append((u, (it.get("title") or {}).get("rendered", ""), it.get("date")))
        if len(items) < 100:
            break
    return out


def site_done(key):
    for s in lib.jsonl_read(SITES):
        if s.get("key") == key and s.get("status") in ("ok", "blocked", "unreachable", "unverified"):
            return s
    return None


def crawl_site(start_url, resort_ids, source_type, source_name=None, max_pages=70, depth=2, key=None,
               verify_terms=None, path_prefix=None, use_render=True, extra_hosts=()):
    """Crawl one site. resort_ids: ids this site belongs to (list) or None for mixed/agency sites.
    Returns a summary dict (also appended to state/sites.jsonl)."""
    key = key or start_url
    prev = site_done(key)
    if prev:
        return prev
    p = urlparse(start_url)
    host = p.netloc.lower()
    allowed = {host.replace("www.", "")} | {h.replace("www.", "") for h in extra_hosts}
    source_name = source_name or host.replace("www.", "")
    summary = {"key": key, "start_url": start_url, "resort_ids": resort_ids, "source_type": source_type,
               "pages": 0, "pdfs": 0, "dam": [], "status": "ok", "final_url": None, "date": lib.TODAY, "js": False}
    html, r = fetch_text(start_url, timeout=60)
    if r is None:
        summary["status"] = "unreachable"
        if host in lib.BLOCKED_HOSTS:
            summary["status"] = "blocked"
            record_blocked(host, "GET home", lib.BLOCKED_HOSTS[host])
        jsonl_append(SITES, summary)
        record_source(source_name, "crawl", summary["status"], 0, 0)
        return summary
    if host in lib.BLOCKED_HOSTS or (not r.ok and r.status_code in (403, 429, 503)):
        # try rendering once (JS challenge pages are left alone: we do not solve them)
        if use_render:
            html, final, pdfs0 = render(start_url)
            if html and not re.search(r"captcha|just a moment|access denied|attention required", html[:5000], re.I):
                lib.BLOCKED_HOSTS.pop(host, None)
                summary["js"] = True
            else:
                summary["status"] = "blocked"
                record_blocked(host, "GET home + render", f"{r.status_code}")
                jsonl_append(SITES, summary)
                record_source(source_name, "crawl", "blocked", 0, 0)
                return summary
        else:
            summary["status"] = "blocked"
            jsonl_append(SITES, summary)
            record_source(source_name, "crawl", "blocked", 0, 0)
            return summary
    if html is None:
        if r is not None and r.ok and r.content[:5] == b"%PDF-":
            enqueue(start_url, source_name, source_type, start_url, resort_ids[0] if resort_ids and len(resort_ids) == 1 else resort_ids)
        summary["status"] = "unreachable" if r is None or not r.ok else "ok"
        jsonl_append(SITES, summary)
        return summary
    final_url = r.url if r is not None else start_url
    summary["final_url"] = final_url
    fhost = urlparse(final_url).netloc.lower().replace("www.", "")
    allowed.add(fhost)
    if path_prefix is None and fhost != host.replace("www.", ""):
        pass
    # verify the site is about this resort
    if verify_terms:
        page_text = norm(BeautifulSoup(html, "lxml").get_text(" ")[:20000])
        if not any(norm(t) in page_text for t in verify_terms):
            # may be JS-rendered; try render
            if use_render:
                html2, final2, pdfs0 = render(start_url)
                if html2:
                    html, final_url = html2, final2
                    summary["js"] = True
                    page_text = norm(BeautifulSoup(html, "lxml").get_text(" ")[:20000])
            if not any(norm(t) in page_text for t in verify_terms):
                summary["status"] = "unverified"
                jsonl_append(SITES, summary)
                record_source(source_name, "crawl", "unverified", 0, 0, "resort name not found on page")
                return summary
    rid_hint = resort_ids[0] if resort_ids and len(resort_ids) == 1 else (resort_ids if resort_ids else None)
    pdf_count = 0
    dam = set()
    seen = set()
    queue = [(final_url, 0)]
    # sitemap and WP media first
    for u in sitemap_urls(final_url):
        pu = urlparse(u)
        if pu.netloc.lower().replace("www.", "") not in allowed or SKIP_EXT.search(u) or SKIP_PATH.search(u):
            continue
        if path_prefix and not pu.path.startswith(path_prefix):
            continue
        if u.lower().endswith(".pdf"):
            if enqueue(u, source_name, source_type, "sitemap", rid_hint):
                pdf_count += 1
        elif PAGE_KEYS.search(pu.path) or pu.path.count("/") <= 2:
            queue.append((u, 1))
    for u, title, date in wp_media_pdfs(final_url):
        if enqueue(u, source_name, source_type, "wp-media-api", rid_hint, {"wp_title": title, "wp_date": date}):
            pdf_count += 1
    if pdf_count:
        summary["wp_or_sitemap_pdfs"] = pdf_count
    # BFS
    render_budget = 12 if use_render else 0
    while queue and summary["pages"] < max_pages:
        u, d = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        if u == final_url:
            page_html = html
        else:
            page_html, rr = fetch_text(u, timeout=60)
            if page_html is None:
                if rr is not None and rr.ok and rr.content[:5] == b"%PDF-":
                    if enqueue(u, source_name, source_type, final_url, rid_hint):
                        pdf_count += 1
                continue
        summary["pages"] += 1
        # JS fallback: very thin page
        text_len = len(BeautifulSoup(page_html, "lxml").get_text(" ", strip=True))
        if use_render and render_budget > 0 and (text_len < 600 or (d == 0 and len(internal_links(page_html, u, allowed)) < 6)):
            html2, final2, pdfs2 = render(u)
            render_budget -= 1
            if html2 and len(html2) > len(page_html) * 0.8:
                page_html = html2
                summary["js"] = True
            for pu in pdfs2:
                if enqueue(pu, source_name, source_type, u, rid_hint):
                    pdf_count += 1
        # save page text
        if resort_ids:
            for rid in resort_ids[:2]:
                save_page(rid, u, page_html, source_type=source_type)
        for pu in extract_pdf_links(page_html, u):
            if enqueue(pu, source_name, source_type, u, rid_hint):
                pdf_count += 1
        for du in dam_links(page_html, u):
            dam.add(du)
            if ".pdf" in du.lower():
                if enqueue(du, source_name, source_type, u, rid_hint):
                    pdf_count += 1
        if d < depth:
            for l in internal_links(page_html, u, allowed):
                if l in seen:
                    continue
                pp = urlparse(l).path
                if path_prefix and not pp.startswith(path_prefix):
                    continue
                if PAGE_KEYS.search(pp) or pp.count("/") <= 2:
                    queue.append((l, d + 1))
    summary["pdfs"] = pdf_count
    summary["dam"] = sorted(dam)[:50]
    for du in sorted(dam):
        jsonl_append(DAM_INDEX, {"url": du, "found_on": final_url, "resort_ids": resort_ids, "date": lib.TODAY})
    if host in lib.BLOCKED_HOSTS:
        summary["status"] = "blocked-partial"
    jsonl_append(SITES, summary)
    record_source(source_name, "crawl", summary["status"], pdf_count, pdf_count if resort_ids else 0,
                  f"pages={summary['pages']} js={summary['js']} dam={len(dam)}")
    return summary
