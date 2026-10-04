"""Phase C: travel agencies, DMCs, tour operators and confirmed mirror sites.
Domains are ranked by matched yield afterwards (see sources in output)."""
import sys, re, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import lib
from lib import log, fetch_text, enqueue, jsonl_append
from crawl import crawl_site, render
from phase_b import commit

# Confirmed mirrors first, then Maldives DMCs / agencies, then specialist operators by market.
AGENCY_DOMAINS = [
    # confirmed mirrors
    "https://www.unihotel.org/", "https://www.mondomaldive.it/", "https://www.awesomegetawaymaldives.com/",
    "https://www.hummingbird.travel/", "https://www.kellyan.co.jp/",
    # Maldives-based DMCs / agencies / representation
    "https://www.innermaldives.com/", "https://www.letsgomaldives.com/", "https://www.voyagesmaldives.com/",
    "https://www.suntravelsmaldives.com/", "https://www.capitaltravel.com/", "https://www.travelconnectionmaldives.com/",
    "https://www.maldivesholidayoffers.com/", "https://www.secretparadise.mv/", "https://www.maldivestraveller.mv/",
    "https://www.resortlife.mv/", "https://www.islandsmaldives.com/", "https://www.maldivesdmc.com/",
    "https://www.ablemaldives.com/", "https://www.maldives-travel.com/", "https://www.simplymaldives.co.uk/",
    "https://www.maldivestravelspot.com/", "https://www.mymaldives.com/", "https://www.maldivesbookings.com/",
    "https://www.lilyhotels.com/", "https://www.maldivesexperts.com/", "https://www.maldives.com/",
    "https://www.maldivestourism.net/", "https://www.visitmaldives.com/", "https://www.atollsmaldives.com/",
    "https://www.ocean-maldives.com/", "https://www.maldivesresorts.com/", "https://www.allmaldives.com/",
    "https://www.maldiveslovers.com/", "https://www.maldivesfinest.com/", "https://www.maldivesmagazine.com/",
    "https://www.sunsetmaldives.com/", "https://www.islandhoppers.com.mv/", "https://www.triptomaldives.com/",
    # UK / Europe specialists
    "https://www.turquoiseholidays.co.uk/", "https://www.elegantresorts.co.uk/", "https://www.letsgo2.com/",
    "https://www.destinology.co.uk/", "https://www.kuoni.co.uk/", "https://www.scottdunn.com/",
    "https://www.abercrombiekent.co.uk/", "https://www.carrier.co.uk/", "https://www.maldivesholidays.co.uk/",
    "https://www.pureholidays.co.uk/", "https://www.tropicalsky.co.uk/", "https://www.holidayplace.co.uk/",
    # Italy
    "https://www.turisanda.it/", "https://www.ideeperviaggiare.it/", "https://www.veratour.it/", "https://www.alpitour.it/",
    "https://www.edenviaggi.it/", "https://www.francorosso.it/", "https://www.maldiveviaggi.it/", "https://www.maldive.it/",
    # Germany / Switzerland / Austria
    "https://www.dertour.de/", "https://www.meiers-weltreisen.de/", "https://www.fti.de/", "https://www.malediven.de/",
    "https://www.malediven-reisen.de/", "https://www.tropical-islands.de/", "https://www.airtours.de/", "https://www.manta-reisen.ch/",
    # Russia / CIS
    "https://www.maldives.ru/", "https://www.bontravel.ru/", "https://www.coral.ru/", "https://www.pac.ru/",
    # Japan / Asia
    "https://www.maldives-tour.jp/", "https://www.hankyu-travel.com/", "https://www.his-j.com/",
    # Gulf
    "https://www.musafir.com/", "https://www.holidayme.com/", "https://www.dnatatravel.com/",
    # China (English-facing)
    "https://www.maldives.cn/", "https://www.maldives-china.com/",
]


def tourism_ministry_register():
    """Try to pull the Ministry of Tourism travel-agency register and extract agency websites."""
    found = set()
    for u in ("https://www.tourism.gov.mv/en/registered_facilities/travel_agencies", "https://www.tourism.gov.mv/dms/",
              "https://www.tourism.gov.mv/en/", "https://tourism.gov.mv/"):
        html, r = fetch_text(u, timeout=60)
        if not html:
            html, final, _ = render(u, wait_ms=4000)
        if not html:
            continue
        for m in re.finditer(r"https?://(?:www\.)?([a-z0-9-]+\.(?:mv|com|net|travel|co\.uk))\b", html, re.I):
            d = m.group(1).lower()
            if "tourism.gov" in d or "gov.mv" in d or any(k in d for k in ("google", "facebook", "twitter", "instagram", "youtube", "cloudflare")):
                continue
            found.add(d)
        if found:
            break
    jsonl_append(lib.SOURCES, {"domain": "tourism.gov.mv", "method": "register", "status": "ok" if found else "no-list",
                               "pdf_found": 0, "pdf_matched": 0, "notes": f"{len(found)} agency domains", "date": lib.TODAY})
    return sorted(found)


def run(domains, workers=5, max_pages=150):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(crawl_site, d, None, "dmc-agency", key=f"agency:{d}", max_pages=max_pages, depth=2,
                          use_render=False): d for d in domains}
        for f in as_completed(futs):
            d = futs[f]
            try:
                s = f.result()
                log.info("C agency %-45s %-12s pages=%s pdfs=%s", d[:45], s.get("status"), s.get("pages"), s.get("pdfs"))
            except Exception:
                log.exception("agency crawl failed %s", d)


if __name__ == "__main__":
    domains = list(AGENCY_DOMAINS)
    if "register" in sys.argv:
        reg = tourism_ministry_register()
        log.info("ministry register: %d domains", len(reg))
        domains += [f"https://www.{d}/" for d in reg[:60]]
    run(domains)
    lib.run_log("C", f"agency/DMC crawl {len(domains)} domains (crawl)")
    if "crawl-only" not in sys.argv:
        stats = lib.run_queue()
        lib.print_progress()
        lib.run_log("C", f"agency/DMC queue: {stats}")
        commit("Phase C: agency/DMC/mirror crawl")
