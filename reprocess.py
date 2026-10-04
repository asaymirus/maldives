"""Re-run classification / edition / status over every stored document (after rule changes).
Also drops 'unmatched' and 'failed-blocked' results so the queue runner retries them.
"""
import os, sys, json, shutil
import lib
from lib import load_docs, save_docs, pdfinfo, pdftotext, classify_doc, detect_edition, doc_status, mark_latest, log, ROOT, LIB
from resorts import BY_ID


def reprocess(move=True):
    docs = load_docs()
    changed = 0
    for h, d in docs.items():
        path = os.path.join(ROOT, d["local_path"])
        if not os.path.exists(path):
            continue
        info = pdfinfo(path)
        first = pdftotext(path, 1, 3)
        full = pdftotext(path) if d.get("text_layer") else first
        orig = d["file_name"].split("_", 1)[1] if "_" in d["file_name"] else d["file_name"]
        if len(orig) > 9 and orig[8] == "_" and all(c in "0123456789abcdef" for c in orig[:8]):
            orig = orig[9:]
        dt, how = classify_doc(orig, d.get("title", ""), first)
        year, ysrc, vf, vt = detect_edition(orig, full, info, d.get("last_modified"))
        status = doc_status(dt, year, vt)
        if (dt, year, vf, vt, status) != (d["doc_type"], d["edition_year"], d.get("valid_from"), d.get("valid_to"), d["status"]):
            changed += 1
        d.update({"doc_type": dt, "doc_type_how": how, "edition_year": year, "edition_source": ysrc,
                  "valid_from": vf, "valid_to": vt, "status": status})
        if move:
            folder = BY_ID[d["resort_id"]]["folder"]
            dest_dir = os.path.join(LIB, folder, dt)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, f"{year or 'nd'}_{orig}")
            if os.path.abspath(dest) != os.path.abspath(path):
                if os.path.exists(dest):
                    dest = os.path.join(dest_dir, f"{year or 'nd'}_{h[:8]}_{orig}")
                shutil.move(path, dest)
                old_dir = os.path.dirname(path)
                if not os.listdir(old_dir):
                    os.rmdir(old_dir)
                d["local_path"] = os.path.relpath(dest, ROOT)
                d["file_name"] = os.path.basename(dest)
    mark_latest(docs)
    save_docs(docs)
    log.info("reprocessed %d docs, %d changed", len(docs), changed)


def requeue_unmatched():
    rows = lib.jsonl_read(lib.RESULTS)
    keep = [r for r in rows if not (r.get("status") in ("unmatched",) or str(r.get("status", "")).startswith("failed-blocked"))]
    with open(lib.RESULTS, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info("requeued %d results", len(rows) - len(keep))


if __name__ == "__main__":
    if "requeue" in sys.argv:
        requeue_unmatched()
    else:
        reprocess()
