"""Phase F: structured fact packs per resort, extracted from collected documents and scraped pages.

Rules/regexes only; nothing is invented. Every fact lists its source_url + as_of in `sources`.
Fields the rules cannot fill stay null and are listed in `gaps` for manual review."""
import os, re, json, csv, collections
from urllib.parse import urlparse
import lib
from lib import load_docs, pdftotext, OUT, ROOT
from resorts import RESORTS, BY_ID, norm

FP = os.path.join(OUT, "factpacks")
os.makedirs(FP, exist_ok=True)

ATOLLS = ["North Malé Atoll", "South Malé Atoll", "North Male Atoll", "South Male Atoll", "Kaafu Atoll", "Baa Atoll", "Raa Atoll",
          "Lhaviyani Atoll", "Noonu Atoll", "Shaviyani Atoll", "Haa Alifu Atoll", "Haa Alif Atoll", "Haa Dhaalu Atoll", "Ari Atoll",
          "North Ari Atoll", "South Ari Atoll", "Alifu Alifu Atoll", "Alifu Dhaalu Atoll", "Vaavu Atoll", "Felidhu Atoll", "Meemu Atoll",
          "Faafu Atoll", "Dhaalu Atoll", "Thaa Atoll", "Laamu Atoll", "Gaafu Alifu Atoll", "Gaafu Alif Atoll", "Gaafu Dhaalu Atoll",
          "Huvadhoo Atoll", "Huvadhu Atoll", "Gnaviyani Atoll", "Addu Atoll", "Seenu Atoll", "Rasdhoo Atoll", "Malé Atoll", "Male Atoll",
          "Gaafu Atoll", "Faafu", "Dhaalu", "Lhaviyani", "Noonu", "Shaviyani", "Raa", "Baa", "Thaa", "Laamu", "Vaavu", "Meemu", "Addu"]
DIVE_OPS = ["Euro-Divers", "Euro Divers", "Prodivers", "Pro Divers", "Dive Butler", "Ocean Dimensions", "TGI Maldives", "TGI", "Sea Explorer",
            "Diverland", "Ocean Group", "Dive Ocean", "Best Dives", "Blue Marine", "Delphis", "Werner Lau", "Aquaventure", "Dive & Sail",
            "Ocean-Pro", "Ocean Pro", "Aquafanatics", "Sub Oceanic", "Moodhu Bulhaa", "Dive Point", "Diving Bluetribe", "Blue Tribe",
            "Sun Dive", "Dive Desk", "Crystal Divers", "Ocean Paradise", "Scuba Nation", "DiveOceanus", "Dive Oceanus", "Secret Paradise",
            "Reef Divers", "Divers Pro", "Marine Savers", "Nautico", "Ocean Watersports", "Fun Azul", "Dive Club", "PADI 5 Star", "Dive Centre"]
MEAL = [("BB", r"\b(bed\s*(&|and)\s*breakfast|BB)\b"), ("HB", r"\b(half[\s-]*board|HB)\b"), ("FB", r"\b(full[\s-]*board|FB)\b"),
        ("AI", r"\b(all[\s-]*inclusive|AI)\b"), ("Dine Around", r"dine[\s-]*around"), ("Premium AI", r"premium\s+all[\s-]*inclusive|premium\s+inclusive|ultra\s+all[\s-]*inclusive|platinum\s+plan")]


def read_doc(d):
    p = os.path.join(ROOT, d["local_path"])
    if not os.path.exists(p):
        return ""
    return pdftotext(p)


def read_pages(rid):
    """Return list of (page_type, url, text) for a resort's saved pages, official first."""
    out = []
    for p in lib.jsonl_read(lib.PAGES_IDX):
        if p.get("resort_id") != rid:
            continue
        fp = os.path.join(ROOT, p["path"])
        if not os.path.exists(fp):
            continue
        t = open(fp, encoding="utf-8").read()
        body = t.split("\n---\n", 1)[-1]
        out.append((p["page_type"], p["url"], body, p.get("source_type", "official"), p["scraped_on"]))
    out.sort(key=lambda x: 0 if x[3] == "official" else 1)
    return out


class Pack:
    def __init__(self, r):
        self.r = r
        self.sources = collections.defaultdict(list)

    def add(self, field, value, url, as_of):
        if value in (None, "", [], {}):
            return
        self.sources[field].append({"value": value, "source_url": url, "as_of": as_of})


def first_num(rx, text, flags=re.I):
    m = re.search(rx, text, flags)
    if m:
        for g in m.groups():
            if g and re.match(r"^\d", g):
                try:
                    return int(re.sub(r"[^\d]", "", g))
                except ValueError:
                    pass
    return None


def extract_from_text(pk, text, url, as_of, kind):
    t = text
    tn = re.sub(r"[ \t]+", " ", t)
    # atoll / island
    for a in ATOLLS:
        if re.search(r"\b" + re.escape(a) + r"\b", tn):
            pk.add("atoll", a if "Atoll" in a else a + " Atoll", url, as_of)
            break
    m = re.search(r"(?:island of|located on|situated on|on the island)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b", tn)
    if m:
        pk.add("island", m.group(1), url, as_of)
    # opened / renovated
    m = re.search(r"(?:opened|opening|established|inaugurated)\D{0,20}((?:19|20)\d\d)", tn, re.I)
    if m:
        pk.add("opened_or_renovated", f"opened {m.group(1)}", url, as_of)
    m = re.search(r"(?:renovat|refurbish|re-?open)\w*\D{0,25}((?:19|20)\d\d)", tn, re.I)
    if m:
        pk.add("opened_or_renovated", f"renovated {m.group(1)}", url, as_of)
    m = re.search(r"\b([3-5])[\s-]*star\b", tn, re.I)
    if m:
        pk.add("star_rating", m.group(1) + "-star", url, as_of)
    # transfer
    for mode, rx in (("seaplane", r"sea\s*plane"), ("speedboat", r"speed\s*boat|speed\s*launch"), ("domestic flight", r"domestic\s+flight|domestic\s+air|internal\s+flight"), ("yacht", r"\byacht\b")):
        if re.search(rx, tn, re.I):
            pk.add("transfer.modes", mode, url, as_of)
            m = re.search("(?:" + rx + r")\D{0,80}?(\d{1,3})\s*(?:-|to|–)?\s*(?:\d{1,3})?\s*(?:min|minute)", tn, re.I) or \
                re.search(r"(\d{1,3})\s*(?:-|to|–)?\s*(?:\d{1,3})?\s*(?:min|minute)s?\D{0,60}?(?:" + rx + ")", tn, re.I)
            if m:
                pk.add(f"transfer.minutes.{mode}", int(m.group(1)), url, as_of)
    # island size
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*(?:hectares?|ha\b)", tn, re.I)
    if m:
        pk.add("island_size", f"{m.group(1)} ha", url, as_of)
    m = re.search(r"(\d{2,4})\s*(?:m|metres|meters)\s*(?:x|by|×)\s*(\d{2,4})\s*(?:m|metres|meters)?", tn, re.I)
    if m:
        pk.add("island_size", f"{m.group(1)} m x {m.group(2)} m", url, as_of)
    # villas total
    m = re.search(r"\b(\d{2,3})\s+(?:luxurious\s+|spacious\s+|private\s+|stunning\s+|beautiful\s+)?(?:villas|rooms|suites|keys|guest\s*rooms|accommodations|residences)\b", tn, re.I)
    if m:
        pk.add("villas.total", int(m.group(1)), url, as_of)
    m = re.search(r"(?:total\s+(?:of\s+)?|comprises?\s+|offers?\s+|features?\s+)(\d{2,3})\s+(?:villas|rooms|suites|keys)", tn, re.I)
    if m:
        pk.add("villas.total", int(m.group(1)), url, as_of)
    # villa categories: "12 x Beach Villa (120 sqm)" / "Beach Villa 12 120 sqm" / lines
    for line in tn.splitlines():
        l = line.strip()
        if not (8 < len(l) < 140) or not re.search(r"villa|suite|bungalow|residence|pavilion|retreat", l, re.I):
            continue
        if re.search(r"restaurant|dining|spa|menu|wedding|price|usd|\$", l, re.I):
            continue
        cnt = first_num(r"^\s*(\d{1,3})\s*(?:x|×)?\s", l)
        if cnt is None:
            cnt = first_num(r"\b(\d{1,3})\s*(?:x|×|units?|villas|rooms)?\s*$", l) or first_num(r"\((\d{1,3})\)", l)
        size = first_num(r"(\d{2,4}(?:[.,]\d+)?)\s*(?:sqm|sq\.?\s*m|m2|m²|square\s*met)", l)
        occ = first_num(r"(?:max\.?|maximum|up to|occupancy)\D{0,15}(\d)\s*(?:adults|persons|pax|guests)", l)
        name = re.sub(r"[\d()x×]+|sqm|sq\.?\s*m|m2|m²|square\s*met\w*|max\.?.*$|\s{2,}.*$", " ", l, flags=re.I).strip(" -:|,.")
        name = re.sub(r"\s+", " ", name)
        if cnt is None and size is None:
            continue
        name = name.split(" | ")[0].strip()
        # drop the running description that follows an upper-case heading in two-column layouts
        mm = re.match(r"^([A-Z][A-Z0-9 &'-]{5,}?)(?:\s+[a-z].*)?$", name)
        if mm:
            name = mm.group(1).strip()
        if not re.search(r"villa|suite|bungalow|residence|pavilion|retreat", name, re.I) or len(name) < 6 or len(name) > 60:
            continue
        if re.search(r"total|number of|court|studio|gym|odeon|pavilion", name, re.I):
            continue
        cat = {"name": name, "count": cnt, "size_sqm": size, "max_occupancy": occ,
               "pool": bool(re.search(r"pool", l, re.I)) or None, "overwater": bool(re.search(r"over\s*water|lagoon|ocean", l, re.I)) or None}
        pk.add("villas.categories", cat, url, as_of)
    # dining
    for line in tn.splitlines():
        l = line.strip(" -•·:|")
        l = re.split(r"\s{3,}|\s\|\s", l)[0].strip()
        if 3 < len(l) < 45 and re.search(r"\b(Restaurant|Bar|Grill|Café|Cafe|Bistro|Lounge|Teppanyaki|Brasserie|Trattoria|Pizzeria|Steakhouse|Deli|Kitchen|Cellar)\b", l) \
                and not re.search(r"\b(the|our|at|in|with|and|of|for|from|all|a)\s+(restaurant|bar)s?\b.{6,}|restaurants?\s+(and|&)\s+bars?|open|serves|offers|\d|studio|court|gym|skin|accessible|dining\s*$|^(restaurant|bar)s?$", l, re.I):
            typ = "bar" if re.search(r"\bBar\b|Lounge|Cellar", l) and not re.search(r"Restaurant", l) else "restaurant"
            pk.add("dining", {"name": l, "cuisine": None, "type": typ}, url, as_of)
    for code, rx in MEAL:
        if re.search(rx, tn):
            pk.add("meal_plans", code, url, as_of)
    m = re.search(r"all[\s-]*inclusive[^.\n]{0,200}\.", tn, re.I)
    if m:
        pk.add("all_inclusive_details", m.group(0).strip()[:300], url, as_of)
    # spa
    m = re.search(r"\b((?:[A-Z][\w'&-]+\s){0,3}Spa)\b(?!\s*(?:menu|treatment|and|&))", tn)
    if m and not re.match(r"^(The|Our|A|Resort|Island|Maldives|Luxury)\s+Spa$", m.group(1)):
        pk.add("spa.name", m.group(1).strip(), url, as_of)
    m = re.search(r"(\d{1,2})\s+(?:spa\s+)?treatment\s+(?:rooms|suites|pavilions|villas)", tn, re.I)
    if m:
        pk.add("spa.treatment_rooms", int(m.group(1)), url, as_of)
    # diving
    for op in DIVE_OPS:
        if re.search(r"\b" + re.escape(op) + r"\b", tn):
            pk.add("diving_watersports.operator", op, url, as_of)
            break
    m = re.search(r"house\s*reef[^.\n]{0,160}", tn, re.I)
    if m:
        pk.add("diving_watersports.house_reef", m.group(0).strip()[:200], url, as_of)
    for act in ("snorkelling", "snorkeling", "scuba diving", "windsurfing", "kitesurfing", "surfing", "kayaking", "stand-up paddle", "paddleboard",
                "catamaran", "jet ski", "parasailing", "water skiing", "wakeboarding", "seabob", "fishing", "sunset cruise", "dolphin cruise",
                "whale shark", "manta", "sailing", "banana boat", "fun tube", "flyboard", "semi-submarine", "glass-bottom", "canoe"):
        if re.search(r"\b" + re.escape(act), tn, re.I):
            pk.add("diving_watersports.activities", act, url, as_of)
    for exc in ("island hopping", "local island", "sandbank", "dolphin", "sunset fishing", "night fishing", "big game fishing", "Male city tour",
                "whale shark", "manta", "turtle", "snorkel safari", "picnic", "stargazing", "private dinner", "castaway", "cinema", "cooking class"):
        if re.search(r"\b" + re.escape(exc), tn, re.I):
            pk.add("excursions", exc, url, as_of)
    # kids
    m = re.search(r"\b((?:[A-Z][\w'&-]+\s){0,3}(?:Kids|Children'?s?|Junior|Teens?)\s(?:Club|Zone|Hub|Den|Lounge|Camp))\b", tn)
    if m:
        pk.add("kids_family.kids_club", m.group(1), url, as_of)
    m = re.search(r"(?:ages?|children)\s*(?:of|from|between)?\s*(\d{1,2})\s*(?:to|-|–|and)\s*(\d{1,2})\s*(?:years|yrs)", tn, re.I)
    if m:
        pk.add("kids_family.age_range", f"{m.group(1)}-{m.group(2)} years", url, as_of)
    if re.search(r"\bteen", tn, re.I):
        pk.add("kids_family.teens", "teens programme mentioned", url, as_of)
    for w in ("yoga", "meditation", "gym", "fitness centre", "fitness center", "tennis", "padel", "badminton", "beach volleyball", "pilates",
              "sound healing", "ayurveda", "hammam", "sauna", "steam", "ice bath", "cryotherapy", "wellness programme", "personal trainer"):
        if re.search(r"\b" + re.escape(w), tn, re.I):
            pk.add("wellness_fitness", w, url, as_of)
    # weddings
    if re.search(r"\bwedding", tn, re.I):
        pk.add("weddings.offered", True, url, as_of)
    if re.search(r"vow\s*renewal|renewal\s*of\s*vows|renew\s*(?:your|their)\s*vows", tn, re.I):
        pk.add("weddings.vow_renewal", True, url, as_of)
    for line in tn.splitlines():
        l = line.strip(" -•·:|")
        if 4 < len(l) < 70 and re.search(r"\b(beach|sandbank|overwater|over water|lagoon|pavilion|chapel|jetty|deck|garden|sunset)\b", l, re.I) \
                and re.search(r"\b(ceremony|wedding|venue)\b", l, re.I) and not re.search(r"\.$|,", l):
            pk.add("weddings.venues", l, url, as_of)
    for m in re.finditer(r"([A-Z][\w' ]{3,40}(?:Package|Ceremony|Celebration|Experience))\D{0,40}?(US\$|USD|\$|EUR|€)\s?([\d,]{3,7})", tn):
        pk.add("weddings.packages", {"name": m.group(1).strip(), "price": m.group(3).replace(",", ""), "currency": "USD" if "$" in m.group(2) or "USD" in m.group(2) else "EUR", "as_of": as_of}, url, as_of)
    for m in re.finditer(r"(US\$|USD|\$|EUR|€)\s?([\d,]{3,7})\D{0,60}?(wedding|ceremony|vow)", tn, re.I):
        pk.add("weddings.packages", {"name": m.group(3).title(), "price": m.group(2).replace(",", ""), "currency": "USD" if "$" in m.group(1) or "USD" in m.group(1).upper() else "EUR", "as_of": as_of}, url, as_of)
    # destination dining (romantic / honeymoon / anniversary / beach / sandbank dinners, sandbank events)
    DD_RX = r"(destination dining|private dining|romantic (?:beach |candle ?lit |sunset |private )?(?:dinner|dining)|honeymoon dinner|anniversary (?:dinner|celebration)|beach (?:dinner|bbq|barbecue)|sand ?bank (?:dinner|lunch|breakfast|picnic|escape|experience|event|celebration|party|trip)|candle ?lit dinner|dine under the stars|dinner under the stars|floating breakfast|private chef|in[- ]villa (?:dinner|bbq|barbecue|dining)|castaway (?:picnic|lunch|dinner)|lagoon (?:dinner|lunch)|jetty dinner|treetop dining|underwater (?:dining|restaurant)|chef'?s table|wine (?:pairing|dinner)|teppanyaki dinner|lobster dinner|sunset (?:cruise|dinner))"
    for m in re.finditer(DD_RX, tn, re.I):
        pk.add("destination_dining.experiences", m.group(1).lower().replace("  ", " "), url, as_of)
    for m in re.finditer(r"([A-Z][\w' ]{3,50}?(?:Dinner|Dining|Picnic|Breakfast|Barbecue|BBQ|Escape|Experience))\D{0,60}?(US\$|USD|\$|EUR|€)\s?([\d,]{2,7})", tn):
        if re.search(r"romantic|honeymoon|anniversary|beach|sand ?bank|private|destination|candle|star|sunset|lagoon|castaway|floating|jetty", m.group(1), re.I):
            pk.add("destination_dining.packages", {"name": m.group(1).strip(), "price": m.group(3).replace(",", ""), "currency": "USD" if "$" in m.group(2) or "USD" in m.group(2).upper() else "EUR", "as_of": as_of}, url, as_of)
    if re.search(r"sand ?bank", tn, re.I) and re.search(r"sand ?bank\W{0,20}(event|celebration|party|wedding|dinner|lunch|picnic|breakfast|experience|escape|trip|excursion)", tn, re.I):
        pk.add("destination_dining.sandbank_events", True, url, as_of)
    # events / MICE
    m = re.search(r"(?:up\s*to|maximum|max\.?|capacity\s*(?:of|for)?)\s*(\d{2,4})\s*(?:guests|people|persons|pax|delegates|attendees)", tn, re.I)
    if m and re.search(r"meeting|conference|event|mice|incentive|banquet", tn, re.I):
        pk.add("events_mice.capacity_max", int(m.group(1)), url, as_of)
    if re.search(r"\b(full\s*)?(island|resort)\s*buy-?out\b|exclusive\s*use\s*of\s*the\s*(island|resort)", tn, re.I):
        pk.add("events_mice.buyout", True, url, as_of)
    for line in tn.splitlines():
        l = line.strip(" -•·:|")
        if 4 < len(l) < 60 and re.search(r"\b(meeting room|conference room|boardroom|ballroom|function room|event space|events? pavilion)\b", l, re.I):
            pk.add("events_mice.venues", l, url, as_of)
    for s in ("coral restoration", "coral regeneration", "coral nursery", "marine biologist", "marine lab", "turtle rehabilitation", "solar", "plastic-free",
              "single-use plastic", "desalination", "glass bottling", "carbon neutral", "Green Globe", "EarthCheck", "Travelife", "Green Key", "organic garden",
              "hydroponic", "composting", "reef restoration", "manta trust", "Olive Ridley Project", "Blue Marine Foundation", "ISO 14001"):
        if re.search(r"\b" + re.escape(s), tn, re.I):
            pk.add("sustainability", s, url, as_of)
    # contacts
    for em in set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", tn)):
        el = em.lower().rstrip(".")
        if any(k in el for k in ("wedding", "romance", "celebrat", "event")):
            pk.add("contacts_public.weddings_email", el, url, as_of)
        elif any(k in el for k in ("reserv", "booking", "info", "stay", "sales", "res@", "hello", "enquir", "inquir")):
            pk.add("contacts_public.reservations_email", el, url, as_of)
    m = re.search(r"(\+\s?960[\s\d()-]{7,14})", tn)
    if m:
        pk.add("contacts_public.phone", re.sub(r"\s+", " ", m.group(1)).strip(), url, as_of)


def pick(pk, field, prefer_official=True):
    vals = pk.sources.get(field, [])
    if not vals:
        return None
    # newest official first
    vals = sorted(vals, key=lambda v: (0 if "official" in (v.get("src") or "official") else 1, -(int(str(v["as_of"])[:4]) if str(v["as_of"])[:4].isdigit() else 0)))
    return vals[0]["value"]


def pick_list(pk, field, limit=40):
    seen, out = set(), []
    for v in pk.sources.get(field, []):
        key = json.dumps(v["value"], sort_keys=True) if isinstance(v["value"], dict) else str(v["value"]).lower()
        if isinstance(v["value"], dict) and "name" in v["value"]:
            key = norm(v["value"]["name"])
        if key in seen:
            continue
        seen.add(key)
        out.append(v["value"])
    return out[:limit]


def build_pack(r, docs, sites):
    rid = r["resort_id"]
    pk = Pack(r)
    mine = [d for d in docs.values() if rid in (d.get("resort_ids") or [d["resort_id"]])]
    latest = {}
    for d in mine:
        if d["is_latest"] or d["doc_type"] not in latest:
            if d["is_latest"] or (d["edition_year"] or 0) >= (latest.get(d["doc_type"], {}).get("edition_year") or 0):
                latest[d["doc_type"]] = d
    # documents first (factsheet, then others), then pages
    for dt in ("factsheet", "brochure", "wedding", "events", "destination_dining", "spa_menu", "dining_menu", "dive_prices", "excursions", "kids", "villa_plans", "all_inclusive", "sustainability", "map"):
        d = latest.get(dt)
        if not d:
            continue
        text = read_doc(d)
        if text:
            extract_from_text(pk, text, d["url"], d["edition_year"] or d["checked_on"], dt)
    for ptype, url, body, st, scraped in read_pages(rid):
        extract_from_text(pk, body, url, scraped, ptype)
        if ptype == "wedding":
            pk.add("weddings.offered", True, url, scraped)
    site = sites.get(f"official:{rid}") or {}
    official_url = site.get("final_url") or site.get("start_url")
    brand = r["aliases"][0] if r["aliases"] else r["name"]
    pack = {
        "resort_id": rid, "name": r["name"], "current_name": None, "aliases": r["aliases"], "official_url": official_url,
        "official_site_status": site.get("status"),
        "operator_brand": None, "atoll": pick(pk, "atoll"), "island": pick(pk, "island"),
        "opened_or_renovated": pick(pk, "opened_or_renovated"), "star_rating": pick(pk, "star_rating"),
        "transfer": {"modes": pick_list(pk, "transfer.modes"),
                     "minutes": {m: pick(pk, f"transfer.minutes.{m}") for m in ("seaplane", "speedboat", "domestic flight", "yacht")}},
        "island_size": pick(pk, "island_size"),
        "villas": {"total": pick(pk, "villas.total"), "categories": pick_list(pk, "villas.categories", 30)},
        "dining": pick_list(pk, "dining", 30), "meal_plans": pick_list(pk, "meal_plans"),
        "all_inclusive_details": pick(pk, "all_inclusive_details"),
        "spa": {"name": pick(pk, "spa.name"), "treatment_rooms": pick(pk, "spa.treatment_rooms"), "signature_treatments": [],
                "menu_doc": latest.get("spa_menu", {}).get("url")},
        "diving_watersports": {"operator": pick(pk, "diving_watersports.operator"), "house_reef": pick(pk, "diving_watersports.house_reef"),
                               "activities": pick_list(pk, "diving_watersports.activities"), "price_list_doc": latest.get("dive_prices", {}).get("url")},
        "excursions": pick_list(pk, "excursions"),
        "kids_family": {"kids_club": pick(pk, "kids_family.kids_club"), "age_range": pick(pk, "kids_family.age_range"), "teens": pick(pk, "kids_family.teens")},
        "wellness_fitness": pick_list(pk, "wellness_fitness"),
        "weddings": {"offered": pick(pk, "weddings.offered"), "vow_renewal": pick(pk, "weddings.vow_renewal"), "venues": pick_list(pk, "weddings.venues", 12),
                     "packages": pick_list(pk, "weddings.packages", 12), "brochure_doc": latest.get("wedding", {}).get("url")},
        "destination_dining": {"experiences": pick_list(pk, "destination_dining.experiences", 25), "packages": pick_list(pk, "destination_dining.packages", 15),
                               "sandbank_events": pick(pk, "destination_dining.sandbank_events"), "doc": latest.get("destination_dining", {}).get("url")},
        "events_mice": {"venues": pick_list(pk, "events_mice.venues", 12), "capacity_max": pick(pk, "events_mice.capacity_max"),
                        "buyout": pick(pk, "events_mice.buyout"), "doc": latest.get("events", {}).get("url")},
        "sustainability": pick_list(pk, "sustainability"),
        "contacts_public": {"reservations_email": pick(pk, "contacts_public.reservations_email"), "weddings_email": pick(pk, "contacts_public.weddings_email"),
                            "phone": pick(pk, "contacts_public.phone")},
        "documents_latest": {k: (latest.get(t, {}).get("url")) for k, t in (("factsheet", "factsheet"), ("map", "map"), ("wedding", "wedding"), ("spa_menu", "spa_menu"),
                                                                           ("dining_menu", "dining_menu"), ("dive_prices", "dive_prices"), ("events", "events"), ("calendar", "calendar"), ("destination_dining", "destination_dining"))},
        "documents_count": len(mine),
        "gaps": [], "sources": {k: v for k, v in pk.sources.items()}, "last_updated": lib.TODAY,
    }
    # operator brand from known aliases/name
    for b in ("Six Senses", "Adaaran", "Joali", "Hilton", "JW Marriott", "Marriott", "Ritz-Carlton", "Ritz Carlton", "Le Méridien", "Westin", "Sheraton", "St. Regis", "W Maldives",
              "Anantara", "Avani", "NH", "Niyama", "Sun Siyam", "Siyam World", "Constance", "COMO", "Como", "Conrad", "Waldorf Astoria", "SAii", "Saii", "Park Hyatt", "Alila", "InterContinental",
              "Inter Continental", "Holiday Inn", "SO/", "Raffles", "Pullman", "Mercure", "Fairmont", "OZEN", "Ozen", "OBLU", "Oblu", "Atmosphere", "Raaya", "VARU", "Varu", "Cinnamon", "Centara",
              "Four Seasons", "Soneva", "Banyan Tree", "Angsana", "Dhawa", "Villa", "Coco", "Club Med", "Robinson", "RIU", "Riu", "Crown & Champa", "Taj", "Jumeirah", "One & Only",
              "Cheval Blanc", "Patina", "Standard", "LUX*", "Lux*", "Outrigger", "Radisson Blu", "Dusit Thani", "Heritance", "Emerald", "Diamonds", "Sandies", "Baglioni", "Hard Rock",
              "Grand Park", "Kuramathi", "Universal", "NIVA", "Pulse", "Lily", "Nautilus", "Gili Lankanfushi", "Velaa", "Milaidhoo", "Baros", "Kurumba", "Mövenpick", "Movenpick", "JA ", "Cocoon", "Noku", "Oaga", "Brennia", "Nooe", "Canareef", "Hideaway", "Furaveri", "Reethi", "Dhigali", "Kudadoo", "Hurawalhi", "Vakkaru", "Finolhu", "Amilla", "Ayada", "Kandima", "Nova"):
        if b.lower() in r["name"].lower() or any(b.lower() in a.lower() for a in r["aliases"]):
            pack["operator_brand"] = b.strip()
            break
    from build_outputs import RENAMES_KNOWN
    for a, b, c in RENAMES_KNOWN:
        if a == rid:
            pack["current_name"] = c
    # gaps
    gaps = []
    if not latest.get("factsheet"):
        gaps.append("factsheet")
    if not latest.get("wedding"):
        gaps.append("wedding brochure")
    if not latest.get("events"):
        gaps.append("events/MICE document")
    if not latest.get("destination_dining") and not pack["destination_dining"]["experiences"]:
        gaps.append("destination dining (romantic/sandbank dinners)")
    for f, v in (("villas.total", pack["villas"]["total"]), ("villa categories", pack["villas"]["categories"]), ("dining", pack["dining"]),
                 ("transfer", pack["transfer"]["modes"]), ("atoll", pack["atoll"]), ("spa", pack["spa"]["name"]), ("dive operator", pack["diving_watersports"]["operator"]),
                 ("kids club", pack["kids_family"]["kids_club"]), ("weddings", pack["weddings"]["offered"]), ("contacts", pack["contacts_public"]["reservations_email"])):
        if v in (None, [], False):
            gaps.append(f"fact: {f}")
    if not mine and not read_pages(rid):
        gaps.append("no documents or pages collected")
    pack["gaps"] = gaps
    return pack


def validate(pack):
    """Light schema validation (types / required keys)."""
    req = ["resort_id", "name", "aliases", "transfer", "villas", "dining", "meal_plans", "spa", "diving_watersports", "excursions", "kids_family",
           "wellness_fitness", "weddings", "destination_dining", "events_mice", "sustainability", "contacts_public", "documents_latest", "gaps", "last_updated"]
    for k in req:
        assert k in pack, k
    assert isinstance(pack["resort_id"], int)
    assert isinstance(pack["aliases"], list) and isinstance(pack["dining"], list) and isinstance(pack["villas"]["categories"], list)
    assert pack["villas"]["total"] is None or isinstance(pack["villas"]["total"], int)
    for c in pack["villas"]["categories"]:
        assert set(c) >= {"name", "count", "size_sqm", "max_occupancy", "pool", "overwater"}
    for p in pack["weddings"]["packages"]:
        assert set(p) >= {"name", "price", "currency", "as_of"}
    return True


def to_md(p):
    L = [f"# {p['resort_id']}. {p['name']}", ""]
    if p.get("current_name"):
        L.append(f"**Current name / alias:** {p['current_name']}  ")
    L += [f"**Official site:** {p.get('official_url') or 'n/a'} ({p.get('official_site_status')})  ", f"**Brand:** {p.get('operator_brand') or 'n/a'}  ",
          f"**Atoll:** {p.get('atoll') or 'n/a'}  **Island:** {p.get('island') or 'n/a'}  ", f"**Opened/renovated:** {p.get('opened_or_renovated') or 'n/a'}  **Rating:** {p.get('star_rating') or 'n/a'}  ",
          f"**Transfer:** {', '.join(p['transfer']['modes']) or 'n/a'}; minutes: {json.dumps({k: v for k, v in p['transfer']['minutes'].items() if v})}  ",
          f"**Island size:** {p.get('island_size') or 'n/a'}  ", "", f"## Villas ({p['villas']['total'] or '?'} total)", ""]
    for c in p["villas"]["categories"]:
        L.append(f"- {c['name']}: count {c['count'] or '?'}, {c['size_sqm'] or '?'} sqm, max {c['max_occupancy'] or '?'}" + (", pool" if c['pool'] else "") + (", overwater" if c['overwater'] else ""))
    L += ["", "## Dining", ""] + [f"- {d['name']} ({d['type']})" for d in p["dining"]] + ["", f"Meal plans: {', '.join(p['meal_plans']) or 'n/a'}"]
    if p.get("all_inclusive_details"):
        L.append(f"All-inclusive: {p['all_inclusive_details']}")
    L += ["", "## Spa & wellness", "", f"- Spa: {p['spa']['name'] or 'n/a'}; treatment rooms: {p['spa']['treatment_rooms'] or '?'}; menu: {p['spa']['menu_doc'] or 'none'}",
          f"- Wellness/fitness: {', '.join(p['wellness_fitness']) or 'n/a'}", "", "## Diving, water sports & excursions", "",
          f"- Operator: {p['diving_watersports']['operator'] or 'n/a'}", f"- House reef: {p['diving_watersports']['house_reef'] or 'n/a'}",
          f"- Activities: {', '.join(p['diving_watersports']['activities']) or 'n/a'}", f"- Price list: {p['diving_watersports']['price_list_doc'] or 'none'}",
          f"- Excursions: {', '.join(p['excursions']) or 'n/a'}", "", "## Kids & family", "",
          f"- Kids club: {p['kids_family']['kids_club'] or 'n/a'}; ages: {p['kids_family']['age_range'] or 'n/a'}; teens: {p['kids_family']['teens'] or 'n/a'}", "",
          "## Weddings", "", f"- Offered: {p['weddings']['offered']}; vow renewal: {p['weddings']['vow_renewal']}", f"- Venues: {'; '.join(p['weddings']['venues']) or 'n/a'}",
          "- Packages: " + ("; ".join("%s %s %s (%s)" % (x["name"], x["currency"], x["price"], x["as_of"]) for x in p["weddings"]["packages"]) or "n/a"),
          f"- Brochure: {p['weddings']['brochure_doc'] or 'none'}", "", "## Destination dining", "",
          f"- Experiences: {', '.join(p['destination_dining']['experiences']) or 'n/a'}",
          "- Packages: " + ("; ".join("%s %s %s (%s)" % (x["name"], x["currency"], x["price"], x["as_of"]) for x in p["destination_dining"]["packages"]) or "n/a"),
          f"- Sandbank events: {p['destination_dining']['sandbank_events']}; document: {p['destination_dining']['doc'] or 'none'}", "", "## Events / MICE", "",
          f"- Venues: {'; '.join(p['events_mice']['venues']) or 'n/a'}; capacity max: {p['events_mice']['capacity_max'] or 'n/a'}; buyout: {p['events_mice']['buyout']}",
          f"- Document: {p['events_mice']['doc'] or 'none'}", "", "## Sustainability", "", f"- {', '.join(p['sustainability']) or 'n/a'}", "", "## Public contacts", "",
          f"- Reservations: {p['contacts_public']['reservations_email'] or 'n/a'}; weddings: {p['contacts_public']['weddings_email'] or 'n/a'}; phone: {p['contacts_public']['phone'] or 'n/a'}",
          "", "## Latest documents", ""] + [f"- {k}: {v or 'none'}" for k, v in p["documents_latest"].items()] + ["", "## Gaps", ""] + [f"- {g}" for g in p["gaps"]] + \
         ["", f"_Facts extracted by rules from {len(p['sources'])} fields' sources; see the JSON `sources` map for source_url / as_of per fact. Last updated {p['last_updated']}._"]
    return "\n".join(L)


def main():
    docs = load_docs()
    sites = {s["key"]: s for s in lib.jsonl_read(os.path.join(lib.STATE, "sites.jsonl")) if str(s.get("key", "")).startswith("official:") and s["key"].count(":") == 1}
    rows = []
    for r in RESORTS:
        p = build_pack(r, docs, sites)
        validate(p)
        base = os.path.join(FP, r["folder"])
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=1)
        with open(base + ".md", "w", encoding="utf-8") as f:
            f.write(to_md(p))
        rows.append({"resort_id": r["resort_id"], "name": r["name"], "current_name": p["current_name"], "official_url": p["official_url"], "site_status": p["official_site_status"],
                     "brand": p["operator_brand"], "atoll": p["atoll"], "island": p["island"], "opened_or_renovated": p["opened_or_renovated"], "star_rating": p["star_rating"],
                     "transfer_modes": ", ".join(p["transfer"]["modes"]), "seaplane_min": p["transfer"]["minutes"]["seaplane"], "speedboat_min": p["transfer"]["minutes"]["speedboat"],
                     "island_size": p["island_size"], "villas_total": p["villas"]["total"], "villa_categories": len(p["villas"]["categories"]), "restaurants_bars": len(p["dining"]),
                     "meal_plans": ", ".join(p["meal_plans"]), "spa": p["spa"]["name"], "dive_operator": p["diving_watersports"]["operator"], "kids_club": p["kids_family"]["kids_club"],
                     "weddings": p["weddings"]["offered"], "vow_renewal": p["weddings"]["vow_renewal"], "wedding_packages": len(p["weddings"]["packages"]),
                     "destination_dining": "; ".join(p["destination_dining"]["experiences"]), "dd_packages": len(p["destination_dining"]["packages"]), "sandbank_events": p["destination_dining"]["sandbank_events"], "dd_doc": p["destination_dining"]["doc"], "mice_capacity": p["events_mice"]["capacity_max"], "buyout": p["events_mice"]["buyout"], "reservations_email": p["contacts_public"]["reservations_email"],
                     "weddings_email": p["contacts_public"]["weddings_email"], "phone": p["contacts_public"]["phone"], "factsheet": p["documents_latest"]["factsheet"],
                     "wedding_doc": p["documents_latest"]["wedding"], "events_doc": p["documents_latest"]["events"], "docs": p["documents_count"], "gaps": "; ".join(p["gaps"])})
        print(f"F {r['resort_id']:3d} {r['name'][:38]:38s} docs={p['documents_count']:3d} villas={p['villas']['total']} dining={len(p['dining'])} gaps={len(p['gaps'])}")
    with open(os.path.join(FP, "all_resorts.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    lib.run_log("F", f"fact packs for {len(rows)} resorts")


if __name__ == "__main__":
    main()
