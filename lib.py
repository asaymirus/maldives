"""Shared pipeline: polite HTTP, state on disk, PDF download/inspect/classify/store.

All state lives under state/ and library/ so every job is resumable.
"""
import os, re, json, time, hashlib, threading, subprocess, datetime, logging, csv
from urllib.parse import urlparse, urljoin, unquote
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

from resorts import RESORTS, BY_ID, match_resort, looks_foreign, norm

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "state")
LIB = os.path.join(ROOT, "library")
OUT = os.path.join(ROOT, "output")
PAGES = os.path.join(OUT, "pages")
for d in (STATE, LIB, OUT, PAGES, os.path.join(STATE, "pdfcache")):
    os.makedirs(d, exist_ok=True)

TODAY = datetime.date.today().isoformat()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(os.path.join(STATE, "run.log")), logging.StreamHandler()])
log = logging.getLogger("lib")

# ---------------------------------------------------------------- polite HTTP
_host_lock = defaultdict(threading.Semaphore)
_host_sem = {}
_host_last = {}
_host_backoff = {}
_lock = threading.Lock()
BLOCKED_HOSTS = {}  # host -> reason


def _sem(host):
    with _lock:
        if host not in _host_sem:
            _host_sem[host] = threading.Semaphore(2)
        return _host_sem[host]


def _throttle(host, delay=0.8):
    with _lock:
        last = _host_last.get(host, 0)
        wait = max(0, last + delay - time.time()) + _host_backoff.get(host, 0)
        _host_last[host] = time.time() + wait
    if wait > 0:
        time.sleep(wait)


SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})


def is_challenge(resp):
    """Detect CAPTCHA / bot-protection pages. We mark them blocked and move on."""
    if resp.status_code in (403, 429, 503):
        body = (resp.text[:4000] if "text" in resp.headers.get("content-type", "") else "").lower()
        if any(k in body for k in ("captcha", "cf-chl", "challenge-platform", "just a moment", "attention required",
                                   "access denied", "incapsula", "_incapsula_", "perimeterx", "px-captcha", "datadome",
                                   "bot detection", "are you a human", "sucuri", "please verify you are a human")):
            return True
        if resp.status_code == 403 and "cloudflare" in (resp.headers.get("server", "") + body).lower():
            return True
    return False


def get(url, timeout=90, stream=False, retries=2, allow_block=False, **kw):
    host = urlparse(url).netloc.lower()
    if host in BLOCKED_HOSTS and not allow_block:
        return None
    sem = _sem(host)
    with sem:
        for attempt in range(retries + 1):
            _throttle(host)
            try:
                r = SESSION.get(url, timeout=timeout, stream=stream, allow_redirects=True, **kw)
            except requests.RequestException as e:
                log.debug("GET fail %s %s", url, e)
                if attempt == retries:
                    return None
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code in (429, 503):
                with _lock:
                    _host_backoff[host] = min(30, _host_backoff.get(host, 1) * 2)
                if is_challenge(r):
                    BLOCKED_HOSTS[host] = f"{r.status_code} challenge"
                    return r
                if attempt < retries:
                    time.sleep(3 * (attempt + 1))
                    continue
            if is_challenge(r):
                BLOCKED_HOSTS[host] = f"{r.status_code} challenge"
                log.info("BLOCKED %s (%s)", host, r.status_code)
            with _lock:
                if r.ok:
                    _host_backoff[host] = 0
            return r
    return None


def fetch_text(url, **kw):
    r = get(url, **kw)
    if r is None or not r.ok:
        return None, r
    ct = r.headers.get("content-type", "")
    if "pdf" in ct or r.content[:5] == b"%PDF-":
        return None, r
    return r.text, r


# ---------------------------------------------------------------- JSONL state
def jsonl_append(path, obj):
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def jsonl_read(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


QUEUE = os.path.join(STATE, "queue.jsonl")
RESULTS = os.path.join(STATE, "results.jsonl")  # one line per processed candidate URL
PAGES_IDX = os.path.join(STATE, "pages.jsonl")
SOURCES = os.path.join(STATE, "sources.jsonl")
EXTRAS = os.path.join(STATE, "extras.jsonl")
BLOCKED = os.path.join(STATE, "blocked.jsonl")
DOCS = os.path.join(STATE, "documents.json")  # sha -> document record


def load_docs():
    if os.path.exists(DOCS):
        with open(DOCS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_docs(docs):
    tmp = DOCS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=0)
    os.replace(tmp, DOCS)


def processed_urls():
    return {r["url"] for r in jsonl_read(RESULTS)}


def queued_urls():
    return {r["url"] for r in jsonl_read(QUEUE)}


def enqueue(url, source, source_type, found_on="", resort_hint=None, extra=None):
    url = clean_url(url)
    if not url:
        return False
    if url in _queued_cache:
        return False
    _queued_cache.add(url)
    rec = {"url": url, "source": source, "source_type": source_type, "found_on": found_on,
           "resort_hint": resort_hint, "added": TODAY}
    if extra:
        rec.update(extra)
    jsonl_append(QUEUE, rec)
    return True


_queued_cache = queued_urls()


def record_source(domain, method, status, pdf_found=0, pdf_matched=0, notes=""):
    jsonl_append(SOURCES, {"domain": domain, "method": method, "status": status, "pdf_found": pdf_found,
                           "pdf_matched": pdf_matched, "notes": notes, "date": TODAY})


def record_blocked(domain, tried, detail=""):
    jsonl_append(BLOCKED, {"domain": domain, "tried": tried, "detail": detail, "date": TODAY})


def clean_url(u):
    if not u:
        return None
    u = u.strip().replace(" ", "%20")
    if u.startswith("//"):
        u = "https:" + u
    if not u.startswith("http"):
        return None
    u = u.split("#")[0]
    return u


# ---------------------------------------------------------------- HTML helpers
PDF_RE = re.compile(r"""https?://[^\s"'<>()\\]+?\.pdf(?:\?[^\s"'<>()\\]*)?""", re.I)
REL_PDF_RE = re.compile(r"""["'(]((?:/|\.\./|\./)?[^\s"'<>()]+?\.pdf(?:\?[^\s"'<>()]*)?)["')]""", re.I)


def extract_pdf_links(html, base_url):
    links = set()
    for m in PDF_RE.finditer(html):
        links.add(m.group(0))
    for m in REL_PDF_RE.finditer(html):
        u = m.group(1)
        if not u.startswith("http"):
            links.add(urljoin(base_url, u))
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all(["a", "iframe", "embed", "object"], href=True) + soup.find_all(["iframe", "embed", "object"], src=True) + soup.find_all("object", data=True):
            u = a.get("href") or a.get("src") or a.get("data")
            if u and (".pdf" in u.lower() or "download" in u.lower() and "pdf" in u.lower()):
                links.add(urljoin(base_url, u))
        for a in soup.find_all("a", href=True):
            txt = (a.get_text(" ", strip=True) or "").lower()
            href = a["href"]
            if any(k in txt for k in ("factsheet", "fact sheet", "brochure", "download", "menu", "pdf", "price list", "wedding", "map"))\
                    and not href.startswith(("mailto:", "tel:", "javascript:", "#")):
                full = urljoin(base_url, href)
                if ".pdf" in full.lower() or "/download" in full.lower() or "/uploads/" in full.lower() or "/files/" in full.lower() or "/documents/" in full.lower():
                    links.add(full)
    except Exception:
        pass
    return {clean_url(l) for l in links if clean_url(l)}


def clean_page_text(html):
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "nav", "footer", "header", "svg", "form", "iframe"]):
        t.decompose()
    for t in soup.find_all(attrs={"class": re.compile(r"(nav|menu|footer|cookie|breadcrumb|header)", re.I)}):
        t.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text


PAGE_TYPES = [
    ("wedding", r"wedd|celebrat|romance|vow|honeymoon|renewal|marry"),
    ("events", r"event|meeting|mice|incentive|conference|group"),
    ("dining", r"dining|restaurant|menu|bar|culinar|gastronom|food|cuisine|eat"),
    ("spa", r"spa|wellness|massage|yoga|retreat|ayurved"),
    ("diving", r"dive|diving|water-?sport|snorkel|surf|marine|ocean|aquatic"),
    ("excursions", r"excursion|experience|activit|adventure|discover|things-to-do"),
    ("kids", r"kid|family|children|teen|junior"),
    ("villas", r"villa|accommodation|room|suite|residence|bungalow|stay"),
    ("transfers", r"transfer|getting-here|location|how-to-get|arrival|seaplane"),
    ("offers", r"offer|promotion|package|deal|special"),
    ("downloads", r"download|brochure|factsheet|fact-sheet|media|press|gallery"),
    ("sustainability", r"sustain|environment|green|conservation|csr|responsib"),
    ("overview", r"about|overview|resort|island|home|^/?$"),
]


def classify_page(url, title=""):
    s = (urlparse(url).path + " " + title).lower()
    for ptype, rx in PAGE_TYPES:
        if re.search(rx, s):
            return ptype
    return "other"


def save_page(resort_id, url, html, page_type=None, source_type="official"):
    title, text = clean_page_text(html)
    if len(text) < 200:
        return None
    if resort_id:
        folder = BY_ID[resort_id]["folder"]
    else:
        folder = "000_unmatched"
    page_type = page_type or classify_page(url, title)
    d = os.path.join(PAGES, folder)
    os.makedirs(d, exist_ok=True)
    host = urlparse(url).netloc.replace("www.", "")
    base = re.sub(r"[^a-z0-9]+", "-", (urlparse(url).path or "home").lower()).strip("-")[:60] or "home"
    fname = f"{page_type}__{host}__{base}.md"
    path = os.path.join(d, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\nSource: {url}\nScraped: {TODAY}\nResort: {BY_ID[resort_id]['name'] if resort_id else 'unmatched'}\nPage type: {page_type}\n\n---\n\n{text}\n")
    jsonl_append(PAGES_IDX, {"resort_id": resort_id, "url": url, "page_type": page_type, "title": title,
                             "chars": len(text), "scraped_on": TODAY, "path": os.path.relpath(path, ROOT),
                             "source_type": source_type})
    return path


# ---------------------------------------------------------------- PDF handling
MAX_BYTES = 60 * 1024 * 1024


def download_pdf(url):
    """Return (bytes, meta) or (None, meta)."""
    meta = {"url": url, "http_status": None, "last_modified": None, "error": None}
    r = get(url, stream=True, timeout=90, headers={"Accept": "application/pdf,*/*"})
    if r is None:
        meta["error"] = "blocked-or-unreachable"
        host = urlparse(url).netloc.lower()
        if host in BLOCKED_HOSTS:
            meta["error"] = "blocked"
        return None, meta
    meta["http_status"] = r.status_code
    meta["last_modified"] = r.headers.get("Last-Modified")
    meta["final_url"] = r.url
    if not r.ok:
        meta["error"] = f"http-{r.status_code}"
        return None, meta
    buf = bytearray()
    try:
        for chunk in r.iter_content(65536):
            buf.extend(chunk)
            if len(buf) > MAX_BYTES:
                meta["error"] = "too-large"
                return None, meta
            if len(buf) >= 5 and not bytes(buf[:5]) == b"%PDF-":
                meta["error"] = "not-pdf"
                return None, meta
    except requests.RequestException as e:
        meta["error"] = f"read-error {e.__class__.__name__}"
        return None, meta
    if len(buf) < 5 or bytes(buf[:5]) != b"%PDF-":
        meta["error"] = "not-pdf"
        return None, meta
    return bytes(buf), meta


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def pdfinfo(path):
    try:
        out = subprocess.run(["pdfinfo", path], capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return {}
    info = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    return info


def pdftotext(path, first=None, last=None):
    cmd = ["pdftotext", "-layout"]
    if first:
        cmd += ["-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    cmd += [path, "-"]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120, errors="ignore").stdout
    except Exception:
        return ""


def parse_pdf_date(s):
    m = re.search(r"(\d{4})", s or "")
    return int(m.group(1)) if m else None


# doc type patterns, checked IN ORDER
DOC_TYPE_RULES = [
    ("obsolete", r"covid|corona|sars-cov|health.?protocol|safety.?guideline|hygiene.?protocol|new.?normal|quarantine"),
    ("wedding", r"wedd|ceremon|vow|renewal.?of|honeymoon|romance|romantic|proposal|elope|bride|marry|marriage|celebration.?of.?love"),
    ("events", r"\bmice\b|meeting|incentive|conference|corporate|group.?event|events?.?(brochure|kit|guide|factsheet)|team.?building|buyout"),
    ("dive_map", r"\b(snorkel\w*|dive|diving|reef|house.?reef)\b.{0,15}\b(map|sites?|chart)\b|\bdive.?sites?\b"),
    ("factsheet", r"fact.?sheet|factfile|fact.?file|resort.?information|hotel.?information|at.?a.?glance|key.?facts|general.?information|resort.?profile"),
    ("map", r"\bmap\b|site.?plan|island.?plan|resort.?plan|island.?layout|resort.?layout|\bplan\b"),
    ("spa_menu", r"\bspa\b|wellness|massage|treatment|ayurved|yoga|therap"),
    ("dining_menu", r"\bmenu|\bwine|cocktail|beverage|drink|dining|restaurant|cuisine|a.?la.?carte|breakfast|lunch|dinner|\bbar\b|cellar|in.?villa.?dining|room.?service|sommelier|teppanyaki|grill|caf[eé]"),
    ("dive_prices", r"\bdive\b|\bdiving\b|\bdiver|water.?sport|snorkel|\bsurf|fishing|kayak|catamaran|sail|jet.?ski|parasail|seabob|aquatic|\bmarine\b|\bpadi\b|\bssi\b|price.?list|rate.?card|tariff"),
    ("excursions", r"excursion|activit|experience|adventure|island.?hopping|sunset.?cruise|dolphin|whale.?shark|manta|boat.?trip|discover|things.?to.?do|guest.?program"),
    ("kids", r"kids|children|child|family|teen|junior|baby|babysit"),
    ("villa_plans", r"villa|suite|room|residence|accommodation|floor.?plan|bungalow|layout"),
    ("all_inclusive", r"all.?inclusive|meal.?plan|half.?board|full.?board|dine.?around|premium.?plan|\bai\b|package|inclusion|rate|tariff|offer|promotion|deal|special"),
    ("sustainability", r"sustainab|environment|marine.?lab|conservation|carbon|green|eco|csr|responsib|turtle|coral"),
    ("calendar", r"calendar|festive|christmas|new.?year|easter|ramadan|programme|program|schedule|weekly|what.?s.?on|whats.?on|agenda"),
    ("brochure", r"brochure|presentation|overview|guide|handbook|directory|e-?book|catalog|flyer|leaflet|lookbook|portfolio|introduc"),
    ("press_kit", r"press|media.?kit|news|release|award"),
]


def classify_doc(filename, title, text):
    """Filename first (strong), then title, then first-pages text. Returns (doc_type, how)."""
    fn = unquote(filename or "")
    fn = re.sub(r"([a-z])([A-Z])", r"\1 \2", fn)          # CamelCase -> words
    fn = re.sub(r"([A-Za-z])(\d)|(\d)([A-Za-z])", lambda m: " ".join(g for g in m.groups() if g), fn)
    fn = fn.lower().replace("_", " ").replace("-", " ").replace(".pdf", "")
    ti = (title or "").lower()
    tx = (text or "")[:3000].lower()
    for dt, rx in DOC_TYPE_RULES:
        if re.search(rx, fn):
            return dt, "filename"
    for dt, rx in DOC_TYPE_RULES:
        if re.search(rx, ti):
            return dt, "title"
    # text: count hits, but preserve priority ordering for ties by iterating in order with threshold
    hits = []
    for dt, rx in DOC_TYPE_RULES:
        n = len(re.findall(rx, tx))
        if n:
            hits.append((dt, n))
    if hits:
        top = max(n for _, n in hits)
        for dt, n in hits:
            if n >= max(2, top * 0.5):
                return dt, "text"
    return "other", "none"


def decode_validity(filename):
    """Crown & Champa style codes: ...110125103126... = 01-Nov-2025 to 31-Oct-2026 (ddmmyy ddmmyy)."""
    fn = unquote(filename)
    for m in re.finditer(r"(?<!\d)(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?!\d)", fn):
        g = list(map(int, m.groups()))
        # the portal uses mmddyy (110125103126 = 1 Nov 2025 .. 31 Oct 2026); fall back to ddmmyy
        for order in ((1, 0, 2, 4, 3, 5), (0, 1, 2, 3, 4, 5)):
            d1, m1, y1, d2, m2, y2 = (g[i] for i in order)
            try:
                a = datetime.date(2000 + y1, m1, d1)
                b = datetime.date(2000 + y2, m2, d2)
            except ValueError:
                continue
            if 2015 <= a.year <= 2035 and a < b and (b - a).days <= 800:
                return a.isoformat(), b.isoformat()
    return None, None


YEAR_RE = re.compile(r"(?<!\d)(20[12]\d)(?!\d)")


def detect_edition(filename, text, info, last_modified):
    fn = unquote(filename)
    vf, vt = decode_validity(fn)
    if vf:
        return int(vf[:4]), "validity-code", vf, vt
    m = YEAR_RE.findall(fn)
    if m:
        return int(max(m)), "filename", None, None
    # explicit season / validity ranges in text
    t = (text or "")[:6000]
    rng = re.search(r"(?:valid|season|edition|rates?|from|effective)\D{0,40}(20[12]\d)\D{0,40}?(?:to|-|–|until|till)\D{0,20}(20[12]\d)", t, re.I)
    if rng:
        return int(rng.group(1)), "text-validity", None, None
    years = [int(y) for y in YEAR_RE.findall(t)]
    years = [y for y in years if y <= datetime.date.today().year + 1]
    if years:
        # prefer the most common recent year
        from collections import Counter
        c = Counter(years)
        best = max(c.items(), key=lambda kv: (kv[1], kv[0]))[0]
        return best, "text", None, None
    y = parse_pdf_date(info.get("ModDate") or info.get("CreationDate"))
    if y:
        return y, "pdf-date", None, None
    if last_modified:
        m = re.search(r"(20\d\d)", last_modified)
        if m:
            return int(m.group(1)), "last-modified", None, None
    return None, "unknown", None, None


def doc_status(doc_type, edition_year, valid_to):
    if doc_type == "obsolete":
        return "obsolete"
    if valid_to and valid_to >= TODAY:
        return "current"
    if edition_year and edition_year >= 2025:
        return "current"
    return "outdated"


def safe_filename(url):
    name = unquote(urlparse(url).path.rsplit("/", 1)[-1]) or "document.pdf"
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)[:120]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def process_candidate(item, docs, source_rank):
    """Download, inspect, match, classify and store one queued candidate. Returns a result record."""
    url = item["url"]
    res = {"url": url, "source": item.get("source"), "source_type": item.get("source_type"),
           "found_on": item.get("found_on"), "checked_on": TODAY, "status": None}
    data, meta = download_pdf(url)
    res.update({k: meta.get(k) for k in ("http_status", "last_modified", "error")})
    if data is None:
        res["status"] = "failed-" + (meta.get("error") or "unknown")
        return res
    h = sha256(data)
    res["sha256"] = h
    res["size_kb"] = round(len(data) / 1024)
    if h in docs:
        d = docs[h]
        if url not in d["all_urls"]:
            d["all_urls"].append(url)
        # official copy wins as primary
        if source_rank.get(item.get("source_type"), 9) < source_rank.get(d.get("source_type"), 9):
            d["url"], d["source"], d["source_type"] = url, item.get("source"), item.get("source_type")
        res["status"] = "duplicate"
        res["doc"] = h
        return res
    cache = os.path.join(STATE, "pdfcache", h + ".pdf")
    with open(cache, "wb") as f:
        f.write(data)
    info = pdfinfo(cache)
    first = pdftotext(cache, 1, 3)
    text_layer = len(re.sub(r"\s", "", first)) > 80
    full = pdftotext(cache) if text_layer else first
    fname = safe_filename(url)
    title = info.get("Title", "")
    # trade-only screen
    tl = (fname + " " + title + " " + full[:5000]).lower()
    if re.search(r"trade.?only|strictly.?confidential|confidential.{0,40}(rate|contract|agent|trade)|net.?rates?\b|contract.?rates?|allotment|for.?travel.?(agents|trade).?only|not.?for.?distribution|b2b.?rate|tour.?operator.?rate|wholesale.?rate", tl):
        res["status"] = "excluded-trade"
        os.remove(cache)
        return res
    # property match
    hint = item.get("resort_hint")
    hints = [hint] if isinstance(hint, int) else (hint or [])
    match_text = f"{url} {fname} {title} {first[:4000]}"
    ids, review = match_resort(match_text, hints)
    foreign, fhits = looks_foreign(f"{fname} {title} {first[:3000]}", url)
    if not ids:
        if hints and not foreign:
            # the source page/section named this resort (e.g. a per-resort portal section); accept, flag for review
            ids, review = list(hints), True
        else:
            res["status"] = "unmatched"
            res["foreign_hits"] = fhits
            res["title"] = title
            # keep cache for later review in extras
            jsonl_append(EXTRAS, {"url": url, "title": title, "sha256": h, "foreign_hits": fhits, "date": TODAY,
                                  "snippet": re.sub(r"\s+", " ", first[:300])})
            return res
    if foreign and not any(f" {norm(BY_ID[i]['aliases'][0] if BY_ID[i]['aliases'] else BY_ID[i]['name'])} " in f" {norm(match_text)} " for i in ids):
        res["status"] = "rejected-foreign"
        res["foreign_hits"] = fhits
        os.remove(cache)
        return res
    doc_type, how = classify_doc(fname, title, first)
    year, ysrc, vf, vt = detect_edition(fname, full, info, meta.get("last_modified"))
    status = doc_status(doc_type, year, vt)
    rid = ids[0]
    folder = BY_ID[rid]["folder"]
    dest_dir = os.path.join(LIB, folder, doc_type)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{year or 'nd'}_{fname}")
    if os.path.exists(dest):
        dest = os.path.join(dest_dir, f"{year or 'nd'}_{h[:8]}_{fname}")
    os.replace(cache, dest)
    doc = {
        "sha256": h, "resort_id": rid, "resort_ids": ids, "resort_name": BY_ID[rid]["name"],
        "doc_type": doc_type, "doc_type_how": how, "file_name": os.path.basename(dest),
        "title": title, "edition_year": year, "edition_source": ysrc, "valid_from": vf, "valid_to": vt,
        "pages": int(info.get("Pages", 0) or 0), "size_kb": round(len(data) / 1024), "text_layer": text_layer,
        "source": item.get("source"), "source_type": item.get("source_type"), "url": url, "all_urls": [url],
        "found_on": item.get("found_on"), "local_path": os.path.relpath(dest, ROOT), "r2_key": None,
        "status": status, "match_status": "needs-review" if review else "matched", "is_latest": False,
        "checked_on": TODAY, "last_modified": meta.get("last_modified"), "pdf_date": info.get("CreationDate"),
        "notes": "" if not review else f"ambiguous match {ids}",
    }
    docs[h] = doc
    res["status"] = "stored"
    res["doc"] = h
    res["resort_id"] = rid
    res["doc_type"] = doc_type
    return res


SOURCE_RANK = {"official": 0, "brand-cdn": 1, "dmc-agency": 2, "flipbook": 3, "archive": 4, "search": 5, "seed": 6}


def mark_latest(docs):
    groups = defaultdict(list)
    for d in docs.values():
        d["is_latest"] = False
        for rid in d.get("resort_ids") or [d["resort_id"]]:
            groups[(rid, d["doc_type"])].append(d)
    for (rid, dt), ds in groups.items():
        ds.sort(key=lambda d: (-(d["edition_year"] or 0), SOURCE_RANK.get(d["source_type"], 9), -(d["pages"] or 0)))
        ds[0]["is_latest"] = True


def run_queue(limit=None, workers=6, source_filter=None):
    """Process everything in the queue that has not been processed yet."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    done = processed_urls()
    items = [q for q in jsonl_read(QUEUE) if q["url"] not in done]
    if source_filter:
        items = [q for q in items if q.get("source_type") in source_filter or q.get("source") in source_filter]
    seen = set()
    uniq = []
    for q in items:
        if q["url"] not in seen:
            seen.add(q["url"])
            uniq.append(q)
    items = uniq[:limit] if limit else uniq
    docs = load_docs()
    log.info("queue: %d candidates to process", len(items))
    stats = defaultdict(int)
    n = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(process_candidate, it, docs, SOURCE_RANK): it for it in items}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                res = fut.result()
            except Exception as e:
                log.exception("candidate failed %s", it["url"])
                res = {"url": it["url"], "status": f"error {e.__class__.__name__}", "checked_on": TODAY}
            jsonl_append(RESULTS, res)
            stats[res["status"].split("-")[0] if res["status"] else "?"] += 1
            n += 1
            if n % 25 == 0:
                save_docs(docs)
                log.info("progress %d/%d %s", n, len(items), dict(stats))
    mark_latest(docs)
    save_docs(docs)
    log.info("queue done: %s", dict(stats))
    for host, why in BLOCKED_HOSTS.items():
        record_blocked(host, "pdf download", why)
    return dict(stats)


def run_log(phase, note):
    path = os.path.join(OUT, "run_log.md")
    new = not os.path.exists(path)
    docs = load_docs()
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write("# Run log\n\n| date | phase | note | docs total |\n|---|---|---|---|\n")
        f.write(f"| {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | {phase} | {note} | {len(docs)} |\n")


def coverage_table(docs=None):
    docs = docs or load_docs()
    have = defaultdict(set)
    for d in docs.values():
        for rid in d.get("resort_ids") or [d["resort_id"]]:
            have[rid].add(d["doc_type"])
    rows = []
    for r in RESORTS:
        s = have.get(r["resort_id"], set())
        rows.append((r["resort_id"], r["name"][:38], "Y" if "factsheet" in s else "", "Y" if "wedding" in s else "",
                     "Y" if "events" in s else "", "Y" if "map" in s else "", len([d for d in docs.values() if r["resort_id"] in (d.get("resort_ids") or [d["resort_id"]])])))
    return rows


def print_progress():
    rows = coverage_table()
    n_fs = sum(1 for r in rows if r[2]); n_w = sum(1 for r in rows if r[3]); n_e = sum(1 for r in rows if r[4])
    n_m = sum(1 for r in rows if r[5]); n_0 = sum(1 for r in rows if r[6] == 0)
    print(f"\n== coverage: factsheet {n_fs}/182  wedding {n_w}  events {n_e}  map {n_m}  nothing {n_0}  docs {len(load_docs())}\n")
