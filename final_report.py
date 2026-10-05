"""Build the final REPORT.md with source notes (run after build_outputs)."""
import json, collections, os
import lib, build_outputs
from lib import load_docs
from resorts import RESORTS, BY_ID

docs = load_docs()
dash = sum(1 for d in docs.values() if ".dash.app" in (d.get("source") or ""))
review = sum(1 for d in docs.values() if d["match_status"] == "needs-review")
no_text = sum(1 for d in docs.values() if not d.get("text_layer"))
portals = lib.jsonl_read(os.path.join(lib.STATE, "dash_portals.jsonl"))
sites = {s["key"]: s for s in lib.jsonl_read(os.path.join(lib.STATE, "sites.jsonl")) if str(s.get("key", "")).startswith("official:") and s["key"].count(":") == 1}
st = collections.Counter(s.get("status") for s in sites.values())
res = lib.jsonl_read(lib.RESULTS)
rc = collections.Counter(str(r.get("status", "")).split("-")[0] for r in res)
excluded = [r["url"] for r in res if r.get("status") == "excluded-trade"]
rejected = [r["url"] for r in res if r.get("status") == "rejected-foreign"]
agencies = [s for s in lib.jsonl_read(lib.SOURCES) if s.get("method") == "crawl" and s.get("domain") and not any(k in s["domain"] for k in ("dash", "commoncrawl"))]
extra = [
    "## How the sources performed", "",
    f"- **Official websites**: {st.get('ok', 0)} crawled fully, {st.get('blocked-partial', 0)} partially (bot wall on some paths), {st.get('blocked', 0)} blocked (CAPTCHA/WAF: Marriott, Hilton, Hyatt, Six Senses, Anantara/Minor, Four Seasons, Constance, Baglioni, ...), {st.get('unverified', 0)} unverified (JavaScript shell with no resort text even after headless render), {st.get('unreachable', 0)} unreachable (TLS/DNS failures from this egress, e.g. joali.com, coastlineresidences.com).",
    f"- **Dash (dash.app) brand portals** (new this run): the public-portal guest API was reverse-engineered from the page's own requests (portal lookup → guest access token → asset search; DOCUMENT previews are the PDFs). Portals read: " + "; ".join(f"{p['subdomain']}/{p['slug']} ({p.get('documents', 0)} PDFs{', login required' if p.get('status') == 'login-required' else ''})" for p in portals) + f". {dash} documents in the library come from Dash (Kandima incl. MICE brochure 2026 and 2024 factsheet, Nova, Pulse brand kit, Villa Nautica / Villa Park / Royal Island). Soneva's Dash portals exist but require a login, so they were not accessed.",
    "- **Other DAMs**: the crawler logged every Brandfolder / Bynder / Canto / Widen / flipbook / cloud-storage link seen on resort pages (`state/dam_hosts.jsonl`) and rendered the shareable ones; COMO's CloudFront press room and a Heyzine flipbook yielded PDFs. Constance's Brandfolder (cdn.bfldr.com) links were only reachable through constancehotels.com, which blocks us.",
    "- **Crown & Champa portal**: WP media API + section pages; validity codes decoded (mmddyy pairs, e.g. 110125103126 = 1 Nov 2025 – 31 Oct 2026) into valid_from / valid_to.",
    f"- **Agencies / DMCs**: {len({s['domain'] for s in agencies})} domains crawled (robots.txt respected); neoscapesmaldives.com is the single most useful mirror (222 docs), then unihotel.org, awesomegetawaymaldives.com, maldives.ru. The Ministry of Tourism register (tourism.gov.mv) returns HTTP 403 to this egress, so a curated list was used.",
    "- **Archives**: Wayback CDX returns 403 and web.archive.org resets connections through this egress; the availability API located 88 archived copies of failed PDF URLs but none could be fetched. Common Crawl's index worked earlier in the session (e.g. 21 Sun Siyam and 37 COMO PDFs indexed) but returned 503/504 for the final run; `python3 phase_d.py cc run all` is ready to re-run when the index recovers (288 domain/path targets prepared, 1 done).",
    "- **Flipbook platforms**: Issuu's rendered search page exposes no document links and Yumpu's results do not match the resorts; after 69 resorts with zero hits the stage was stopped (metadata-only by design). **Search API**: skipped, no `BRAVE_API_KEY` / `SERPAPI_KEY` set.",
    "", "## Processing outcomes", "",
    f"- Candidate URLs processed: {len(res)} → stored {rc.get('stored', 0)}, duplicates {rc.get('duplicate', 0)}, unmatched {rc.get('unmatched', 0)}, rejected foreign sister-property {rc.get('rejected', 0)}, excluded trade-only {rc.get('excluded', 0)}, failed {rc.get('failed', 0)}.",
    f"- {review} stored documents are `needs-review`: the file does not name the resort itself (typical for menus, maps and price lists) and the match rests on the official page/portal it was found on. {no_text} documents have no text layer (OCR tools are installed; run `ocrmypdf` on these before fact extraction).",
    f"- Excluded as trade-only ({len(excluded)}): " + ", ".join(excluded[:8]) + (" ..." if len(excluded) > 8 else ""),
    f"- Rejected as foreign sister properties ({len(rejected)}), e.g.: " + ", ".join(u.rsplit('/', 1)[-1][:50] for u in rejected[:8]),
    "", "## Fact packs", "",
    "- `output/factpacks/<NNN>_<slug>.json|.md` for all 182 resorts, `all_resorts.csv` flat table. Extraction is rule-based (regexes over the latest factsheet/brochure/menus and the scraped pages); every fact carries `source_url` + `as_of` in the pack's `sources` map and fields the rules could not fill are null and listed under `gaps`. Villa-category and dining lists need a human read for two-column factsheet layouts.",
    "", "## Recommended next steps", "",
    "1. Re-run `python3 phase_d.py cc run all` when index.commoncrawl.org stops returning 503 (it covers the blocked chain sites: Marriott/Hilton/Hyatt/Six Senses/Anantara/Four Seasons/Constance).",
    "2. Direct email requests for wedding and MICE brochures to the resorts still missing them (see table above); the Dash/brand-portal route worked for Pulse and Villa Resorts, so ask other groups (Atmosphere Core, Sun Siyam, Universal, Coco Collection) for their portal links.",
    "3. Give the crawler a residential/office egress or a Brave/SerpAPI key for the search gap-fill; 79 previously blocked official sites were retried from this IP and most remain behind bot walls.",
    "4. Review the `needs-review` documents and the villa/dining fields in the fact packs; OCR the no-text-layer files.",
]
build_outputs.build_all(extra_sections=extra)
