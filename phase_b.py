"""Phase B: official websites (batches of 20, list order) + group/brand hub sites + DAM follow-up."""
import sys, re, os, json, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import lib
from lib import log, jsonl_append, enqueue, get, fetch_text
from crawl import crawl_site, site_done, render, SITES, DAM_INDEX
from official_urls import OFFICIAL, GROUP_SITES
from resorts import RESORTS, BY_ID, match_resort

RENAMES = os.path.join(lib.STATE, "renames.jsonl")


def verify_terms(r):
    terms = [r["name"]] + r["aliases"]
    # drop generic
    return [t for t in terms if len(t) >= 4 and t.lower() not in ("maldives", "resort", "island")]


def official_for(r):
    rid = r["resort_id"]
    key = f"official:{rid}"
    prev = site_done(key)
    if prev:
        return prev
    cands = OFFICIAL.get(rid) or [f"https://www.{r['domain_hint']}/"]
    last = None
    for i, u in enumerate(cands):
        s = crawl_site(u, [rid], "official", key=f"official:{rid}:{i}", verify_terms=verify_terms(r),
                       path_prefix=(urlparse(u).path if urlparse(u).path.strip("/") and urlparse(u).netloc.split(".")[-2] in
                                    ("marriott", "hilton", "hyatt", "ihg", "accor", "sixsenses", "anantara", "avanihotels", "fourseasons",
                                     "centarahotelsresorts", "cinnamonhotels", "sunsiyam", "constancehotels", "banyantree", "angsana",
                                     "cococollection", "comohotels", "clubmed", "robinson", "riu", "diamondsresorts", "tajhotels",
                                     "jumeirah", "nh-hotels", "nh-collection", "oneandonlyresorts", "luxresorts", "standardhotels",
                                     "radissonhotels", "dusit", "outrigger", "jaresortshotels", "chevalblanc", "melia", "cenizaro",
                                     "adaaran", "heritancehotels", "parkhotelgroup", "baglionihotels", "soneva", "patinahotels",
                                     "ritzcarlton", "nokuhotels", "alilahotels", "hardrockhotels", "saiiresorts") else None))
        last = s
        if s["status"] in ("ok", "blocked-partial"):
            fin = s.get("final_url") or u
            if urlparse(fin).netloc.replace("www.", "") != urlparse(u).netloc.replace("www.", ""):
                jsonl_append(RENAMES, {"resort_id": rid, "name": r["name"], "from": u, "to": fin, "date": lib.TODAY})
            s = dict(s, key=key)
            jsonl_append(SITES, s)
            return s
    s = dict(last or {"status": "unreachable"}, key=key, resort_ids=[rid])
    jsonl_append(SITES, s)
    return s


def run_batch(ids, workers=5):
    rows = [BY_ID[i] for i in ids]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(official_for, r): r for r in rows}
        for f in as_completed(futs):
            r = futs[f]
            try:
                s = f.result()
                log.info("B official %3d %-40s %-10s pages=%s pdfs=%s js=%s", r["resort_id"], r["name"][:40], s.get("status"),
                         s.get("pages"), s.get("pdfs"), s.get("js"))
            except Exception as e:
                log.exception("official crawl failed %s", r["name"])


def group_sites():
    for key, (url, ids) in GROUP_SITES.items():
        try:
            s = crawl_site(url, ids, "official", key=f"group:{key}", max_pages=120, depth=2)
            log.info("B group %-14s %-10s pages=%s pdfs=%s", key, s.get("status"), s.get("pages"), s.get("pdfs"))
        except Exception:
            log.exception("group crawl failed %s", key)


# ------------------------------------------------------------ DAM follow-up (Dash, Brandfolder, Bynder, flipbooks...)
def dam_followup():
    """Visit each DAM link found during crawling; pull PDFs from public collections/share pages."""
    seen = set()
    done = {s["key"] for s in lib.jsonl_read(SITES) if s.get("key", "").startswith("dam:")}
    for rec in lib.jsonl_read(DAM_INDEX):
        u = rec["url"]
        if u in seen or f"dam:{u}" in done:
            continue
        seen.add(u)
        host = urlparse(u).netloc.lower()
        ids = rec.get("resort_ids")
        hint = ids[0] if ids and len(ids) == 1 else ids
        n = 0
        if u.lower().split("?")[0].endswith(".pdf"):
            enqueue(u, host, "brand-cdn", rec.get("found_on"), hint)
            n = 1
        elif any(k in host for k in ("dash.app", "brightdam", "bright-interactive", "bfldr", "brandfolder", "bynder", "canto", "widen",
                                     "imagerelay", "filecamp", "box.com", "dropbox", "drive.google", "sharepoint", "1drv", "onedrive",
                                     "flippingbook", "publitas", "fliphtml5", "anyflip", "heyzine", "simplebooklet", "flipsnack", "joomag")):
            html, final, pdfs = render(u, wait_ms=4000)
            for pu in pdfs:
                if enqueue(pu, host, "brand-cdn", u, hint):
                    n += 1
            if html:
                for pu in lib.extract_pdf_links(html, final):
                    if enqueue(pu, host, "brand-cdn", u, hint):
                        n += 1
                # Dash / Brandfolder expose JSON with asset download URLs inline
                for m in re.finditer(r'"(https?://[^"]+?\.pdf(?:\?[^"]*)?)"', html):
                    if enqueue(m.group(1).replace("\\/", "/"), host, "brand-cdn", u, hint):
                        n += 1
                for m in re.finditer(r'"(https?://[^"]*?(download|attachments|assets)[^"]*?)"', html, re.I):
                    cand = m.group(1).replace("\\/", "/")
                    if len(cand) < 400 and "pdf" in cand.lower():
                        if enqueue(cand, host, "brand-cdn", u, hint):
                            n += 1
        jsonl_append(SITES, {"key": f"dam:{u}", "status": "ok", "pdfs": n, "resort_ids": ids, "date": lib.TODAY})
        if n:
            log.info("DAM %s -> %d pdfs", u[:90], n)


def commit(msg):
    try:
        import build_outputs
        build_outputs.build_all()
    except Exception:
        log.exception("build_outputs failed")
    subprocess.run(["git", "add", "-A"], cwd=lib.ROOT)
    subprocess.run(["git", "commit", "-q", "-m", msg + "\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01HuKfdgdkSVamDCtYV6eLkT"], cwd=lib.ROOT)
    subprocess.run(["git", "push", "-q", "-u", "origin", "claude/gallant-johnson-ktui6q"], cwd=lib.ROOT)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "group":
        group_sites()
        lib.run_queue()
        lib.print_progress()
        lib.run_log("B", "group/brand hub sites")
        commit("Phase B: group/brand hub sites")
    elif args and args[0] == "dam":
        dam_followup()
        lib.run_queue()
        lib.print_progress()
        lib.run_log("B", "DAM follow-up")
        commit("Phase B: DAM follow-up")
    else:
        start = int(args[0]) if args else 1
        end = int(args[1]) if len(args) > 1 else 182
        for b in range(start, end + 1, 20):
            ids = list(range(b, min(b + 20, end + 1)))
            log.info("=== Phase B batch %d-%d", ids[0], ids[-1])
            run_batch(ids)
            stats = lib.run_queue()
            lib.print_progress()
            lib.run_log("B", f"official sites {ids[0]}-{ids[-1]}: {stats}")
            commit(f"Phase B: official sites {ids[0]}-{ids[-1]}")
