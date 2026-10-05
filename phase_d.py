"""Phase D: web archives.
- Wayback CDX is refused from this egress (403); the availability API works, so we use it per known URL.
- Common Crawl index works over plain http (flaky; retried). We query it for every official domain and
  every blocked domain, filtered to PDFs, and fetch the archived WARC record bytes.
"""
import sys, re, json, io, gzip, time
from urllib.parse import urlparse, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import lib
from lib import log, get, enqueue, jsonl_append, record_source
from official_urls import OFFICIAL, GROUP_SITES
from resorts import RESORTS, BY_ID
from phase_b import commit

CC_INDEX = "http://index.commoncrawl.org"
CC_DATA = "https://data.commoncrawl.org/"
CC_DONE = lib.STATE + "/cc_done.jsonl"


def cc_collections(n=4):
    for _ in range(4):
        r = get(f"{CC_INDEX}/collinfo.json", timeout=60)
        if r is not None and r.ok:
            try:
                return [c["id"] for c in r.json()][:n]
            except Exception:
                pass
        time.sleep(3)
    return ["CC-MAIN-2026-39", "CC-MAIN-2026-33", "CC-MAIN-2026-26", "CC-MAIN-2026-18"]


def cc_query(coll, domain):
    """Returns a list of records, or None when the index could not be queried (503/504 overload, timeouts)."""
    out = []
    for attempt in range(5):
        r = get(f"{CC_INDEX}/{coll}-index?url={quote(domain + '/*')}&filter=mime:application/pdf&output=json&limit=500", timeout=90, allow_block=True)
        if r is not None and r.status_code == 404:
            return out
        if r is not None and r.ok:
            for line in r.text.splitlines():
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
            return out
        time.sleep(min(90, 10 * (2 ** attempt)))  # the public index throttles with 503/504; back off hard
    return None


def cc_fetch(rec):
    """Fetch one archived record from Common Crawl's WARC and return the PDF bytes."""
    off, ln = int(rec["offset"]), int(rec["length"])
    url = CC_DATA + rec["filename"]
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"Range": f"bytes={off}-{off + ln - 1}", "User-Agent": lib.UA}, timeout=120)
            if r.status_code in (200, 206):
                raw = gzip.decompress(r.content)
                # WARC headers, then HTTP headers, then body
                idx = raw.find(b"\r\n\r\n")
                idx2 = raw.find(b"\r\n\r\n", idx + 4)
                body = raw[idx2 + 4:] if idx2 > 0 else raw
                return body
        except Exception as e:
            time.sleep(3)
    return None


def archive_domains():
    doms = set()
    for rid, urls in OFFICIAL.items():
        for u in urls:
            h = urlparse(u).netloc.lower().replace("www.", "")
            # chain mega-sites are too broad for a domain/* query; use path prefix instead
            path = urlparse(u).path.strip("/")
            if h.split(".")[0] in ("marriott", "hilton", "hyatt", "ihg", "all", "sixsenses", "anantara", "avanihotels", "fourseasons",
                                   "centarahotelsresorts", "cinnamonhotels", "constancehotels", "banyantree", "angsana", "cococollection",
                                   "comohotels", "clubmed", "robinson", "riu", "diamondsresorts", "tajhotels", "jumeirah", "nh-hotels",
                                   "nh-collection", "oneandonlyresorts", "luxresorts", "standardhotels", "radissonhotels", "dusit",
                                   "outrigger", "jaresortshotels", "chevalblanc", "melia", "cenizaro", "adaaran", "heritancehotels",
                                   "parkhotelgroup", "baglionihotels", "soneva", "patinahotels", "ritzcarlton", "nokuhotels", "hardrockhotels",
                                   "saiiresorts", "sunsiyam", "planhotel"):
                doms.add((f"{h}/{path}" if path else h, (rid,)))
            else:
                doms.add((h, (rid,)))
    for key, (u, ids) in GROUP_SITES.items():
        doms.add((urlparse(u).netloc.lower().replace("www.", ""), tuple(ids)))
    # brand CDNs / media libraries (section 4.2) whose HTML front-ends block us
    doms |= {
        ("media.sixsenses.com", (1, 90,)), ("de87ve0y4m3tc.cloudfront.net/comohotels.com-2459770069/cms/pressroom", (66, 121,)),
        ("sunsiyam.com/media", (50, 118, 147, 148, 179,)), ("anantara.com/uploads", (106, 145, 146,)), ("avanihotels.com/uploads", (122,)),
        ("nh-hotels.com", (39, 92,)), ("nh-collection.com", (39,)), ("niyama.com", (117,)), ("cdn.bfldr.com", (109, 155,)),
        ("fourseasons.com/alt", (56, 86, 87,)), ("fourseasons.com/content/dam", (56, 86, 87,)), ("soneva.com", (137, 141, 143,)),
        ("atmospherecore.com", (5, 41, 77, 80, 115, 133, 138,)), ("atmosphere-core.com", (5, 41, 77, 80, 115, 133, 138,)),
        ("conradmaldives.com", (99,)), ("waldorfastoriamaldives.com", (67,)), ("hilton.com/en/hotels/mlehici", (99,)), ("hilton.com/en/hotels/mlewawa", (67,)),
        ("hilton.com/en/hotels/mleamhi", (8,)), ("marriott.com/en-us/hotels/mlewh", (102,)), ("marriott.com/en-us/hotels/mlexr", (134,)),
        ("marriott.com/en-us/hotels/mlejw", (18,)), ("marriott.com/en-us/hotels/mlewi", (107,)), ("marriott.com/en-us/hotels/mlesi", (103,)),
        ("marriott.com/en-us/hotels/mlemd", (40,)), ("ritzcarlton.com/en/hotels/mlerz", (37,)), ("marriott.com/en-us/hotels/mlejk", (16,)),
        ("sixsenses.com/en/resorts/laamu", (1,)), ("sixsenses.com/en/resorts/kanuhura", (90,)), ("joali.com", (6, 7,)), ("joalibeing.com", (6,)),
        ("coastlineresidences.com", (36,)), ("clubmed.com", (100, 101,)), ("robinson.com", (130, 131,)), ("riu.com", (129,)),
    }
    merged = {}
    for dom, ids in doms:
        merged.setdefault(dom, set()).update(ids)
    return sorted((dom, sorted(ids)) for dom, ids in merged.items())


def run_common_crawl(only_missing=True):
    docs = lib.load_docs()
    have_fs = {d["resort_id"] for d in docs.values() if d["doc_type"] in ("factsheet",)}
    done = {(r["coll"], r["domain"]) for r in lib.jsonl_read(CC_DONE)}
    colls = cc_collections()
    log.info("Common Crawl collections: %s", colls)
    targets = archive_domains()
    if only_missing:
        targets = [(d, ids) for d, ids in targets if any(i not in have_fs for i in ids) or len(ids) > 3]
    log.info("Common Crawl: %d domains", len(targets))
    n_found = n_stored = 0
    for coll in colls[:1]:
        for domain, ids in targets:
            if (coll, domain) in done:
                continue
            recs = cc_query(coll, domain)
            if recs is None:
                log.info("Common Crawl index unavailable for %s (%s); will retry on next run", domain, coll)
                record_source(domain, f"commoncrawl {coll}", "index-unavailable", 0, 0)
                continue
            hint = ids[0] if len(ids) == 1 else ids
            for rec in recs:
                if rec.get("status") not in ("200", 200):
                    continue
                orig = rec["url"]
                n_found += 1
                enqueue(orig, "commoncrawl:" + coll, "archive", f"{CC_INDEX}/{coll}-index?url={domain}", hint,
                        {"cc": {"filename": rec["filename"], "offset": rec["offset"], "length": rec["length"], "timestamp": rec.get("timestamp")}})
            jsonl_append(CC_DONE, {"coll": coll, "domain": domain, "records": len(recs), "date": lib.TODAY})
            record_source(domain, f"commoncrawl {coll}", "ok", len(recs), 0)
    log.info("Common Crawl queued %d pdf records", n_found)


def wayback_available(url):
    r = get(f"https://archive.org/wayback/available?url={quote(url, safe='')}", timeout=60, allow_block=True)
    if r is None or not r.ok:
        return None
    try:
        snap = r.json().get("archived_snapshots", {}).get("closest")
    except Exception:
        return None
    if snap and snap.get("available"):
        return snap.get("url"), snap.get("timestamp")
    return None


def wayback_for_failed():
    """For queued PDF URLs that failed (404/blocked), look for a Wayback copy."""
    rows = lib.jsonl_read(lib.RESULTS)
    failed = [r for r in rows if str(r.get("status", "")).startswith("failed-http") or str(r.get("status", "")).startswith("failed-blocked")]
    log.info("Wayback: %d failed urls to check", len(failed))
    n = 0
    for r in failed[:400]:
        u = r["url"]
        res = wayback_available(u)
        if res:
            snap_url, ts = res
            raw = re.sub(r"/web/(\d+)/", r"/web/\1id_/", snap_url)
            q = next((x for x in lib.jsonl_read(lib.QUEUE) if x["url"] == u), {})
            if enqueue(raw, "web.archive.org", "archive", u, q.get("resort_hint"), {"capture": ts}):
                n += 1
    log.info("Wayback: %d archived copies queued", n)


# Common Crawl records are downloaded from the WARC rather than the live URL
def _download_pdf_cc(item):
    cc = item.get("cc")
    if not cc:
        return None
    body = cc_fetch(cc)
    if body and body[:5] == b"%PDF-":
        return body
    return None


_orig_download = lib.download_pdf


def _patched_download(url):
    q = QUEUE_BY_URL.get(url)
    if q and q.get("cc"):
        body = _download_pdf_cc(q)
        meta = {"url": url, "http_status": 200 if body else None, "last_modified": q["cc"].get("timestamp"), "error": None if body else "cc-fetch-failed"}
        return body, meta
    return _orig_download(url)


QUEUE_BY_URL = {}

if __name__ == "__main__":
    which = sys.argv[1:] or ["cc", "wayback", "run"]
    if "cc" in which:
        run_common_crawl(only_missing="all" not in which)
    if "wayback" in which:
        wayback_for_failed()
    if "run" in which:
        QUEUE_BY_URL.update({q["url"]: q for q in lib.jsonl_read(lib.QUEUE) if q.get("source_type") == "archive"})
        lib.download_pdf = _patched_download
        stats = lib.run_queue(source_filter={"archive"}, workers=4)
        lib.print_progress()
        lib.run_log("D", f"archives: {stats}")
        commit("Phase D: archives (Common Crawl, Wayback availability)")
