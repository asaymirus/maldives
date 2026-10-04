"""Re-crawl official sites whose first pass ended unverified/unreachable (after URL fixes and crawler fixes)."""
import json, sys
import lib
from lib import log
from crawl import SITES
from phase_b import official_for, commit
from resorts import BY_ID

def reset(statuses=("unverified", "unreachable")):
    rows = lib.jsonl_read(SITES)
    bad = set()
    for r in rows:
        k = str(r.get("key", ""))
        if k.startswith("official:") and k.count(":") == 1 and r.get("status") in statuses:
            bad.add(int(k.split(":")[1]))
    keep = [r for r in rows if not (str(r.get("key", "")).startswith("official:") and int(r["key"].split(":")[1]) in bad)]
    with open(SITES, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info("reset %d official sites for retry: %s", len(bad), sorted(bad))
    return sorted(bad)

if __name__ == "__main__":
    ids = reset(tuple(sys.argv[1:]) or ("unverified", "unreachable"))
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(official_for, BY_ID[i]): i for i in ids}
        for f in as_completed(futs):
            i = futs[f]
            try:
                s = f.result()
                log.info("RETRY %3d %-40s %-12s pages=%s pdfs=%s", i, BY_ID[i]["name"][:40], s.get("status"), s.get("pages"), s.get("pdfs"))
            except Exception:
                log.exception("retry failed %d", i)
    stats = lib.run_queue()
    lib.print_progress()
    lib.run_log("B", f"retry official sites {ids}: {stats}")
    commit("Phase B: retry unverified/unreachable official sites")
