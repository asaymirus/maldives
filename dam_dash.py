"""Dash (dash.app) digital-asset-manager connector.

Public Dash portals (used by Pulse Hotels & Resorts, Villa Resorts, Soneva, ...) expose a guest API:
  GET  api-v2.dash.app/subdomains/<sub>/publicly-available-portal-datas/<slug>   -> portal id, name
  GET  api-v2.dash.app/portals/<portal-id>/access-token                           -> guest bearer token
  POST api-v2.dash.app/asset-searches  (Bearer)                                   -> assets; DOCUMENT previewUrl is the PDF
No login, no CAPTCHA: this is exactly what a visitor's browser does on the public portal page.
"""
import re, json, sys, os
from urllib.parse import urlparse
import requests
import lib
from lib import log, enqueue, jsonl_append, record_source
from resorts import match_resort, RESORTS

API = "https://api-v2.dash.app"
S = requests.Session()
S.headers.update({"User-Agent": lib.UA, "Accept": "application/json"})
DASH_DONE = os.path.join(lib.STATE, "dash_portals.jsonl")

# subdomain -> candidate portal slugs (discovered on brand sites + sensible guesses)
KNOWN_PORTALS = {
    "pulse": ["kandima-maldives-official-library", "nova-maldives-official-library", "nova-maldives", "the-nautilus-maldives",
              "nautilus-maldives-official-library", "the-nautilus-maldives-official-library", "pulse-hotels-resorts", "pulse-hotels-and-resorts",
              "kandima", "nova", "nautilus", "the-nautilus"],
    "villaresorts": ["villa-resorts", "villa-nautica", "villa-park", "royal-island", "villa-resorts-media", "press", "media"],
    "soneva": ["soneva", "soneva-media", "soneva-press", "press", "media", "media-library", "soneva-fushi", "soneva-jani", "soneva-secret",
               "soneva-press-kit", "press-kit", "soneva-brand-assets", "brand-assets", "soneva-image-library", "image-library"],
}


def account_exists(sub):
    r = S.post(f"{API}/publicly-available-account-data-searches", json={"from": 0, "pageSize": 1, "criterion": {"type": "FIELD_EQUALS", "field": "SUBDOMAIN", "value": sub}, "sorts": []}, timeout=60)
    try:
        return bool(r.json().get("results"))
    except Exception:
        return False


def portal_data(sub, slug):
    r = S.get(f"{API}/subdomains/{sub}/publicly-available-portal-datas/{slug}", timeout=60)
    if r.status_code != 200:
        return None
    try:
        return r.json()["result"]
    except Exception:
        return None


def token(portal_id):
    r = S.get(f"{API}/portals/{portal_id}/access-token", timeout=60)
    r.raise_for_status()
    return r.json()["result"]["accessToken"]


def folder_names(H):
    """Map folder/attribute option ids -> names (portals organise assets by resort/folder)."""
    names = {}
    try:
        fs = S.get(f"{API}/folder-settings", headers=H, timeout=60).json()["result"]
        fid = fs.get("fieldId")
        if not fid:
            return names
        frm = 0
        while True:
            r = S.post(f"{API}/field-option-searches", headers=H, json={"from": frm, "pageSize": 400, "criterion": {"type": "FIELD_IN", "field": "FIELD_ID", "values": [fid]}, "sorts": []}, timeout=60).json()
            for x in r.get("results", []):
                o = x["result"]
                parent = (o.get("parent") or {}).get("result", {}).get("value") if o.get("parent") else None
                names[o["id"]] = (parent + " / " if parent else "") + o["value"]
            if frm + 400 >= r.get("totalResults", 0):
                break
            frm += 400
    except Exception as e:
        log.info("dash folder names failed: %s", e)
    return names


def portal_documents(sub, slug, resort_hint=None):
    pd = portal_data(sub, slug)
    if not pd:
        return None
    pid = pd["id"]
    try:
        tok = token(pid)
    except requests.HTTPError as e:
        # portal exists but is not public (login required): record and skip, never attempt to bypass
        jsonl_append(DASH_DONE, {"subdomain": sub, "slug": slug, "portal": pd.get("name"), "portal_id": pid, "documents": 0, "queued": 0,
                                 "status": "login-required", "date": lib.TODAY})
        record_source(f"{sub}.dash.app/portals/{slug}", "dash-api", "login-required", 0, 0, pd.get("name"))
        log.info("DASH %s/%s '%s': login required (%s)", sub, slug, pd.get("name"), e.response.status_code if e.response is not None else e)
        return []
    H = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
    folders = folder_names(H)
    docs = []
    frm = 0
    while True:
        body = {"from": frm, "pageSize": 100, "sorts": [{"field": {"type": "FIXED", "fieldName": "ADDED_ORDER"}, "order": "DESC"}],
                "criterion": {"type": "FIELD_EQUALS", "field": {"type": "FIXED", "fieldName": "FILE_TYPE"}, "value": "DOCUMENT"}, "aggregations": {}}
        r = S.post(f"{API}/asset-searches", headers=H, json=body, timeout=90)
        if r.status_code != 200:
            log.info("dash asset-searches %s: %s", r.status_code, r.text[:200])
            break
        j = r.json()
        for x in j.get("results", []):
            a = x["result"]
            f = a.get("currentAssetFile") or {}
            mt = f.get("mediaType") or {}
            if mt.get("subType") != "pdf" and not (f.get("filename") or "").lower().endswith(".pdf"):
                continue
            folder = ""
            for k, vals in (a.get("metadata") or {}).get("values", {}).items():
                for v in vals if isinstance(vals, list) else [vals]:
                    if isinstance(v, str) and v in folders:
                        folder += folders[v] + " "
            docs.append({"id": a["id"], "filename": f.get("filename"), "size": f.get("size"), "date_added": f.get("dateAdded"),
                         "preview_url": f.get("previewUrl"), "folder": folder.strip(), "portal": pd.get("name"),
                         "can_download": any(p.get("action") == "DOWNLOAD_ASSET" for p in x.get("permittedActions", []))})
        frm += 100
        if frm >= j.get("totalResults", 0):
            break
    portal_url = f"https://{sub}.dash.app/portals/{slug}"
    n = 0
    for d in docs:
        if not d["preview_url"]:
            continue
        ctx = f"{d['portal']} {d['folder']}"
        ids, review = match_resort(f"{d['filename']} {ctx}", [resort_hint] if isinstance(resort_hint, int) else resort_hint)
        hint = ids if ids else resort_hint
        if enqueue(d["preview_url"], f"{sub}.dash.app", "brand-cdn", portal_url, hint if not isinstance(hint, list) or len(hint) > 1 else hint[0],
                   {"filename": d["filename"], "context": ctx, "dash_date_added": d["date_added"], "dash_asset_id": d["id"], "dash_size": d["size"]}):
            n += 1
    jsonl_append(DASH_DONE, {"subdomain": sub, "slug": slug, "portal": pd.get("name"), "portal_id": pid, "documents": len(docs), "queued": n, "date": lib.TODAY})
    record_source(f"{sub}.dash.app/portals/{slug}", "dash-api", "ok", len(docs), n, pd.get("name"))
    log.info("DASH %s/%s '%s': %d pdf documents, %d queued", sub, slug, pd.get("name"), len(docs), n)
    return docs


def discovered_portals():
    """Dash portal links found by the crawler (state/dam_hosts.jsonl) and custom domains redirecting to Dash."""
    out = set()
    for rec in lib.jsonl_read(os.path.join(lib.STATE, "dam_hosts.jsonl")):
        m = re.search(r"https?://([a-z0-9-]+)\.dash\.app/portals/([a-z0-9-]+)", rec["url"])
        if m:
            out.add((m.group(1), m.group(2), tuple(rec.get("resort_ids") or [])))
    return out


def run(extra=()):
    done = {(d["subdomain"], d["slug"]) for d in lib.jsonl_read(DASH_DONE)}
    targets = []
    for sub, slugs in KNOWN_PORTALS.items():
        if not account_exists(sub):
            record_source(f"{sub}.dash.app", "dash-api", "no-account", 0, 0)
            continue
        for s in slugs:
            targets.append((sub, s, None))
    for sub, slug, ids in discovered_portals():
        targets.append((sub, slug, list(ids) or None))
    for sub, slug, hint in extra:
        targets.append((sub, slug, hint))
    seen = set()
    for sub, slug, hint in targets:
        if (sub, slug) in done or (sub, slug) in seen:
            continue
        seen.add((sub, slug))
        try:
            res = portal_documents(sub, slug, hint)
            if res is None:
                log.debug("dash portal not found %s/%s", sub, slug)
        except Exception:
            log.exception("dash portal failed %s/%s", sub, slug)


if __name__ == "__main__":
    run()
    if "run" in sys.argv:
        lib.run_queue(source_filter={"brand-cdn"}, workers=3)
        lib.print_progress()
