"""Bring state back in sync after an interrupted run:
- results marked stored/duplicate whose document is not in documents.json are dropped (they will be re-processed);
- PDFs in library/ not referenced by documents.json are deleted (they are re-downloaded on re-processing);
- stale pdfcache files are removed; truncated downloads are re-queued.
"""
import os, json
import lib
from lib import load_docs, ROOT, LIB, log


def main():
    docs = load_docs()
    known = set(docs)
    paths = {os.path.normpath(os.path.join(ROOT, d["local_path"])) for d in docs.values()}
    rows = lib.jsonl_read(lib.RESULTS)
    keep = []
    dropped = 0
    for r in rows:
        st = str(r.get("status", ""))
        if st in ("stored", "duplicate") and r.get("doc") not in known:
            dropped += 1
            continue
        if st in ("failed-truncated", "failed-read-error ChunkedEncodingError", "failed-read-error ConnectionError", "error FileNotFoundError"):
            dropped += 1
            continue
        keep.append(r)
    with open(lib.RESULTS, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    orphans = 0
    for root, dirs, files in os.walk(LIB):
        for fn in files:
            p = os.path.normpath(os.path.join(root, fn))
            if p not in paths:
                os.remove(p)
                orphans += 1
    for fn in os.listdir(os.path.join(lib.STATE, "pdfcache")):
        try:
            os.remove(os.path.join(lib.STATE, "pdfcache", fn))
        except OSError:
            pass
    # drop documents whose file vanished
    gone = [h for h, d in docs.items() if not os.path.exists(os.path.join(ROOT, d["local_path"]))]
    for h in gone:
        del docs[h]
    lib.mark_latest(docs)
    lib.save_docs(docs)
    log.info("reconcile: dropped %d results, removed %d orphan files, %d index entries without file", dropped, orphans, len(gone))


if __name__ == "__main__":
    main()
