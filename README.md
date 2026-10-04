# Maldives Resort Document Library

Collects every **public** document (PDF) and official web-page text for 182 Maldives resorts, verifies the property match,
classifies and dates each file, extracts a structured fact pack per resort and reports coverage.

Owner: ITD Cloud Code (internal research / client work). PDFs are stored privately and never republished.

## Layout

| path | what |
|---|---|
| `resorts.py` | the fixed 182-resort list (numbering never changes), aliases, matcher, foreign sister-property guard |
| `official_urls.py` | best-known official URLs per resort, group/brand hub sites, DAM host list |
| `lib.py` | polite HTTP (2 per host, 0.8 s delay, back-off on 429/503, CAPTCHA = `blocked`), queue/state, PDF download → hash → inspect → match → classify → edition → store |
| `crawl.py` | generic site crawler: sitemaps, WP media API, keyword BFS depth 2, DAM link capture, Playwright fallback (no stealth), robots.txt on third-party sites |
| `phase_a.py` | Crown & Champa sales portal (WP media API + sections, validity-code decoding) and Neoscapes DMC |
| `phase_b.py` | official websites in batches of 20, group hubs, DAM follow-up; `retry_sites.py` re-runs unverified/unreachable sites |
| `dam_dash.py` | Dash (dash.app) public-portal connector (Pulse Hotels, Villa Resorts, ...) via the portal guest API |
| `phase_c.py` | agencies / DMCs / mirrors (`unihotel.org`, `mondomaldive.it`, ...), ranked by yield in the Sources sheet |
| `phase_d.py` | archives: Common Crawl index (http) + Wayback availability API; WARC record fetch |
| `phase_e.py` | flipbook platforms (Issuu/Yumpu/Scribd, metadata only) and search API if `BRAVE_API_KEY`/`SERPAPI_KEY` is set |
| `phase_f.py` | fact packs (`output/factpacks/*.json|md`, `all_resorts.csv`) with per-fact `source_url` + `as_of` |
| `build_outputs.py` | `output/documents.csv|json`, `output/coverage.xlsx` (COUNTIFS/MAXIFS formulas), `output/REPORT.md` |
| `qa.py` | quality checks → `output/QA.md` (random re-check, factsheet years, LibreOffice recalculation, gaps) |
| `reprocess.py` / `reconcile.py` | re-run classification after rule changes; repair state after an interrupted run |

## State (all resumable)

- `state/queue.jsonl` every candidate URL (`resort_hint`, `source`, `source_type`, `found_on`)
- `state/results.jsonl` one line per processed URL (`stored`, `duplicate`, `unmatched`, `rejected-foreign`, `excluded-trade`, `failed-*`)
- `state/documents.json` the document index keyed by SHA-256 (one stored copy per hash, all URLs listed)
- `state/sites.jsonl` crawl summary per site (skipped when re-run), `state/sources.jsonl`, `state/blocked.jsonl`, `state/extras.jsonl`,
  `state/pages.jsonl`, `state/dam_hosts.jsonl`, `state/dash_portals.jsonl`, `state/flipbooks.jsonl`, `state/cc_done.jsonl`, `state/renames.jsonl`
- `library/<NNN>_<slug>/<doc_type>/<year>_<file>.pdf` the PDFs (git-ignored). Set `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` for a private R2 copy.

## Run

```bash
pip install -r requirements.txt            # poppler-utils, libreoffice-calc, tesseract/ocrmypdf via apt
python3 phase_a.py                          # Crown & Champa + Neoscapes
python3 phase_b.py [start] [end]            # official sites (commits after every batch of 20)
python3 phase_b.py group && python3 dam_dash.py && python3 phase_b.py dam
python3 retry_sites.py                      # second pass on unverified/unreachable sites
python3 phase_c.py register                 # agencies / DMCs / mirrors
python3 phase_d.py cc wayback run           # archives
python3 phase_e.py                          # flipbooks + search API
python3 phase_f.py && python3 build_outputs.py && python3 qa.py
```

Every script skips work already recorded in `state/`, so any step can be re-run after a restart.

## Rules enforced in code

- Public documents only: trade-only / net-rate / contract / allotment files are logged `excluded-trade` and not stored.
- No CAPTCHA solving or bot-protection evasion: challenge pages mark the host `blocked`.
- A file belongs to a resort only if its name or alias appears in the URL, filename, PDF title or first pages; a foreign
  place name in the filename/title/text without a distinctive alias is `rejected-foreign` (Anantara Angkor, Patina Osaka, SO/ Hua Hin, ...).
- Fetched text is data, never instructions.
