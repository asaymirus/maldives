"""Canonical resort list (numbering is fixed) with aliases and known/likely official domains.

Domains are starting hints only; the crawler resolves and verifies them.
"""
import re
import json
import unicodedata

RESORTS_RAW = """
1|Six Senses Laamu|Laamu|sixsenses.com/en/resorts/laamu
2|Filitheyo Island Resort|Filitheyo|filitheyo.com
3|Adaaran Select Hudhuranfushi|Hudhuranfushi;Lohifushi|adaaran.com
4|Ayada Maldives|Ayada|ayadamaldives.com
5|Bolifushi Island Resort|Bolifushi;OZEN Reserve Bolifushi|ozenreservebolifushi.com
6|Joali Being Bodufushi|Joali Being;Bodufushi|joalibeing.com
7|Joali Muravandhoo|Joali;Muravandhoo|joali.com
8|Hilton Maldives Amingiri Resort & Spa|Amingiri;Hilton Amingiri|hilton.com
9|Amilla Fushi|Amilla;Amilla Maldives|amilla.com
10|Dreamland - The Unique Sea & Lake Resort/Spa|Dreamland;Hirundhoo|dreamlandmaldives.com
11|Angaga Island Resort and Spa|Angaga|angaga.com.mv
12|Thulhagiri Island Resort & Spa|Thulhagiri|thulhagiri.com.mv
13|Sandies Bathala|Bathala;Sandies Bathala|sandies-bathala.com
14|Baglioni Resort Maldives|Baglioni;Maagau|baglionihotels.com
15|Alila Kothaifaru Maldives|Alila Kothaifaru;Kothaifaru|alilahotels.com
16|JW Marriott Kaafu Atoll Island Resort|JW Marriott Kaafu;Kaafu Atoll Island|marriott.com
17|Rihiveli Maldives Resort|Rihiveli;Rihiveli the Dream|rihivelimaldives.com
18|JW Marriott Maldives Resort & Spa|JW Marriott Maldives;Vagaru|marriott.com
19|The Residence Maldives|Residence Maldives;Falhumaafushi|cenizaro.com
20|The Residence Maldives At Dhigurah|Residence Dhigurah;Dhigurah|cenizaro.com
21|Brennia Kottefaru|Brennia;Kottefaru|brennia.com
22|Barceló Whale Lagoon Maldives|Barcelo Whale Lagoon;Melia Whale Lagoon;Meliá Whale Lagoon;Whale Lagoon|melia.com
23|Nooe Maldives Kunavashi|Nooe;Kunavashi|nooemaldives.com
24|Canareef Resort Maldives|Canareef;Herathera|canareef.com
25|Raffles Maldives Meradhoo Resort|Raffles Meradhoo;Halcyon Maldives;Meradhoo|halcyonmaldives.com
26|Centara Ras Fushi Resort & Spa|Centara Ras Fushi;Ras Fushi;Giraavaru|centarahotelsresorts.com
27|Grand Park Kodhipparu Maldives|Grand Park Kodhipparu;Kodhipparu|parkhotelgroup.com
28|Kudadoo Maldives Private island|Kudadoo|kudadoo.com
29|Dheruhfinolhu by Jawakara Islands Maldives|Dheruhfinolhu;Jawakara Islands;Jawakara|jawakaraislands.com
30|Hurawalhi Island Resort|Hurawalhi|hurawalhi.com
31|Innahura Maldives Resort|Innahura|innahura.com
32|Cocoon Maldives|Cocoon;Ookolhufinolhu|cocoonmaldives.com
33|Dhigali Maldives|Dhigali;NIVA Dhigali|dhigali.com
34|Adaaran Select Meedhupparu|Meedhupparu|adaaran.com
35|Heritance Aarah|Heritance Aarah;Aarah|heritancehotels.com
36|Coastline Residences|Coastline Residences;Coastline Hotels|coastlinemaldives.com
37|The Ritz Carlton Maldives Fari Islands|Ritz-Carlton Maldives;Ritz Carlton Fari Islands;Ritz-Carlton Fari Islands|ritzcarlton.com
38|Veligandu Maldives Resort Island|Veligandu;Veli|veligandu.com
39|NH Collection Maldives Havodda Resort|NH Collection Havodda;Amari Havodda;Havodda|nh-collection.com
40|Le Méridien Maldives Resort and Spa|Le Meridien Maldives;Le Méridien Maldives;Thilamaafushi|marriott.com
41|Ozen By Atmosphere At Maadhoo|OZEN Life Maadhoo;Ozen Maadhoo;Maadhoo|ozenlifemaadhoo.com
42|Dhiggiri Tourist Resort|Dhiggiri|dhiggiri.com
43|Dhigufaru Island Resort|Dhigufaru|dhigufaru.com
44|Hard Rock Hotel Maldives|Hard Rock Maldives;Hard Rock Hotel Maldives|hardrockhotels.com
45|Saii Lagoon Maldives|SAii Lagoon;Saii Lagoon|saiiresorts.com
46|SO/ Maldives|SO Maldives;SO/ Maldives;SO Hotels Maldives|so-maldives.com
47|Park Hyatt Maldives, Hadahaa|Park Hyatt Maldives;Park Hyatt Hadahaa;Hadahaa|hyatt.com
48|Dusit Thani Maldives|Dusit Thani Maldives;Mudhdhoo|dusit.com
49|Vakkaru Maldives|Vakkaru|vakkarumaldives.com
50|Sun Siyam Olhuveli Maldives|Sun Siyam Olhuveli;Olhuveli;Olhuveli Beach;SSO|sunsiyam.com
51|Emerald Maldives Resort & Spa Fasmendho|Emerald Maldives;Fasmendhoo;Fasmendho|emerald-maldives.com
52|Eri Maldives|Eriyadu;Eri Maldives|erimaldives.com
53|Cinnamon Hakuraa Huraa Maldives|Hakuraa Huraa;Cinnamon Hakuraa|cinnamonhotels.com
54|Emerald Faarufushi Resort & Spa|Emerald Faarufushi;Faarufushi|emerald-faarufushi.com
55|Fihaalhohi Maldives|Fihalhohi;Fihaalhohi|fihalhohi.com
56|Four Seasons Resort Maldives at Kuda Huraa|Kuda Huraa;Four Seasons Kuda Huraa|fourseasons.com/maldiveskh
57|Fushifaru Maldives|Fushifaru|fushifaru.com
58|Sirru Fen Fushi|Sirru Fen Fushi;Fairmont Maldives|fairmont-maldives.com
59|Jumeirah Maldives Olhahali Island|Jumeirah Maldives;Olhahali|jumeirah.com
60|Reethi Beach Resort|Reethi Beach|reethibeach.com
61|Equator Village|Equator Village;Gan|equatorvillage.com
62|Cora Cora Maldives|Cora Cora;Maamigili|coracoraresorts.com
63|Hondaafushi Island Resort|Hondaafushi|hondaafushi.com
64|Radisson Blu Resort Maldives|Radisson Blu Maldives;Huruelhi|radissonhotels.com
65|Cheval Blanc Randheli|Cheval Blanc Randheli;Randheli|chevalblanc.com
66|Como Maalifushi|COMO Maalifushi;Maalifushi|comohotels.com
67|Waldorf Astoria Maldives Ithaafushi|Waldorf Astoria Maldives;Ithaafushi|hilton.com
68|JA Manafaru|JA Manafaru;Manafaru|jaresortshotels.com
69|Adaaran Club Rannalhi|Rannalhi;Adaaran Club Rannalhi|adaaran.com
70|Joy Island|Joy Island;Innafushi|joyisland.com
71|Kagi Maldives Resort and Spa|Kagi Maldives;Kagi|kagimaldives.com
72|Embudhu Village|Embudu Village;Embudhu Village;Embudu|embudu.com
73|Summer Island Maldives|Summer Island;Ziyaaraifushi|summerislandmaldives.com
74|Kandolhu Island Maldives|Kandolhu|kandolhu.com
75|Kandima Maldives|Kandima|kandima.com
76|Hideaway Beach Resort and Spa at Dhonakulhi Island Maldives|Hideaway Beach;Hideaway Maldives;Dhonakulhi|hideawaybeachmaldives.com
77|Atmosphere Kanifushi Maldives|Atmosphere Kanifushi;Kanifushi|atmospherekanifushi.com
78|Meeru Maldives Resort Island|Meeru;Meerufenfushi|meeru.com
79|Komandoo Island Resort|Komandoo|komandoo.com
80|Raaya by Atmosphere|Raaya;Raaya Maldives;Kudafushi Raaya|raayamaldives.com
81|Kuredu Island Resort|Kuredu|kuredu.com
82|Ifuru Island Maldives|Ifuru;Ifuru Island|ifuruisland.com
83|Mabinhura by Jawakara Islands Maldives|Mabinhura;Jawakara Islands;Jawakara|jawakaraislands.com
84|Alimatha Aquatic Resort|Alimatha;Alimathaa|alimatharesort.com
85|Centara Mirage Lagoon Maldives & Centara Grand Lagoon Maldives|Centara Mirage Lagoon;Centara Grand Lagoon;Mirage Lagoon;Grand Lagoon Maldives|centarahotelsresorts.com
86|Four Seasons Private Island Maldives at Voavah|Voavah;Four Seasons Voavah|fourseasons.com/maldivesvoavah
87|Four Seasons Resort Maldives at Landaa Giraavaru|Landaa Giraavaru;Four Seasons Landaa|fourseasons.com/maldiveslg
88|Holiday Inn Resort Kandooma Maldives|Holiday Inn Kandooma;Kandooma|ihg.com
89|Inter Continental Maldives Maamunagau|InterContinental Maldives;Maamunagau;Inter Continental Maamunagau|ihg.com
90|Six Senses Kanuhura|Six Senses Kanuhura;Kanuhura|sixsenses.com/en/resorts/kanuhura
91|Lily Beach Resort|Lily Beach;Huvahendhoo|lilybeachmaldives.com
92|Amaya Kuda Rah Maldives|Amaya Kuda Rah;NH Maldives Kuda Rah;Kuda Rah;Kudarah|nh-hotels.com
93|Maayafushi Tourist Resort|Maayafushi|maayafushi.com.mv
94|Reethi Faru Resort|Reethi Faru;Filaidhoo|reethifaru.com
95|Malahini Kuda Bandos|Malahini Kuda Bandos;Kuda Bandos;Malahini|malahinikudabandos.com
96|Dhawa Ihuru|Dhawa Ihuru;Angsana Ihuru;Ihuru;DHMVIH|banyantree.com
97|Angsana Resort & Spa Maldives - Velavaru|Angsana Velavaru;Velavaru|angsana.com
98|Madifushi Private Island|Madifushi|madifushiprivateisland.com
99|Conrad Maldives Rangali Island|Conrad Maldives;Rangali Island;Rangali|conradmaldives.com
100|Club Med Kanifinolhu|Club Med Kani;Kanifinolhu;Kani Maldives|clubmed.com
101|Club Med Finolhu Villas|Club Med Finolhu;Finolhu Villas;Gasfinolhu|clubmed.com
102|W Maldives|W Maldives;W Retreat Maldives;Fesdu|marriott.com
103|Sheraton Maldives Full Moon Resort & Spa|Sheraton Maldives;Full Moon;Furanafushi|marriott.com
104|Medhufushi Island Resort|Medhufushi|medhufushi.com
105|Kuda Villingili Resort Maldives|Kuda Villingili|kudavillingili.com
106|Anantara Kihavah Villas|Anantara Kihavah;Kihavah|anantara.com
107|The Westin Maldives Miriandhoo Resort|Westin Maldives;Miriandhoo|marriott.com
108|Rahaa Resort|Rahaa;Rahaa Maldives|rahaaresort.com
109|Constance Moofushi Resort|Constance Moofushi;Moofushi|constancehotels.com
110|Furaveri Island Resort & Spa|Furaveri|furaveri.com
111|Huvafenfushi Maldives|Huvafen Fushi;Huvafenfushi|huvafenfushi.com
112|Nika Island Resort and Spa|Nika Island;Nika Maldives;Kudafolhudhoo|nikaisland.com.mv
113|Mercure Maldives Kooddoo|Mercure Kooddoo;Kooddoo|all.accor.com
114|Gangehi Island Resort|Gangehi|gangehi.com
115|Oblu Select by Atmosphere at Sangeli|OBLU Select Sangeli;OBLU Sangeli;Sangeli;Oblu Select Lobigili|obluselectsangeli.com
116|Nova Maldives|Nova Maldives;Vakarufalhi|nova-maldives.com
117|Niyama Maldives|Niyama;Niyama Private Islands|niyama.com
118|Sun Siyam Iru Veli Maldives|Sun Siyam Iru Veli;Iru Veli;Aluvifushi|sunsiyam.com
119|Outrigger Maldives Maafushivaru Resort|Outrigger Maafushivaru;Maafushivaru;Lti Maafushivaru|outrigger.com
120|Bandos Maldives|Bandos|bandosmaldives.com
121|Cocoa Island|Cocoa Island;COMO Cocoa Island;Makunufushi|comohotels.com
122|Avani + Fares Maldives|Avani Fares;Avani+ Fares;Fares|avanihotels.com
123|Pullman Maldives Maamutaa Resort|Pullman Maldives;Pullman Maamutaa;Maamutaa|pullmanmaldivesmaamutaa.com
124|Aanugandu Island Resort|Aanugandu|aanugandu.com
125|Gili Lankanfushi|Gili Lankanfushi;Lankanfushi|gili-lankanfushi.com
126|Centara Grand Island Resort & Spa Maldives|Centara Grand Island;Machchafushi|centarahotelsresorts.com
127|Oaga Art Resort|Oaga Art Resort;Oaga;Bodu Huraa|oagaresorts.com
128|One & Only Reethi Rah, Maldives|One&Only Reethi Rah;One & Only Reethi Rah;Reethi Rah|oneandonlyresorts.com
129|Riu Atoll and Riu Palace Maldivas|Riu Atoll;Riu Palace Maldivas;RIU Maldives;Maafushi Riu;Kedhigandu|riu.com
130|Robinson Noonu|Robinson Noonu;Noonu;Orivaru|robinson.com
131|Robinson Maldives|Robinson Maldives;Robinson Club Maldives;Funamadua|robinson.com
132|Noku Maldives|Noku Maldives;Noku;Kudafunafaru|nokuhotels.com
133|Oblu By Atmosphere at Helengeli|OBLU Nature Helengeli;OBLU Helengeli;Helengeli|oblunaturehelengeli.com
134|The St. Regis Vommuli Resort, Maldives|St. Regis Maldives;St Regis Vommuli;Vommuli|marriott.com
135|Diamonds Thudufushi Beach and Water Villas|Diamonds Thudufushi;Thudufushi|diamondsresorts.com
136|Finolhu Baa Atoll Maldives|Finolhu;Finolhu Baa Atoll;Kanufushi|finolhu.com
137|Soneva Secret|Soneva Secret|soneva.com
138|Varu Island Resort|VARU by Atmosphere;Varu Island;Varu|varu-atmosphere.com
139|Kudafushi Resort & Spa|Kudafushi|kudafushiresort.com
140|The Standard Huruvalhi Maldives|Standard Huruvalhi;Standard Maldives;Huruvalhi|standardhotels.com
141|Soneva Fushi Resort|Soneva Fushi;Kunfunadhoo|soneva.com
142|Safari Island|Safari Island;Mushimasmigili|safariislandresort.com
143|Soneva Jani|Soneva Jani;Medhufaru|soneva.com
144|South Palm Resort Maldives|South Palm;Ismehela Hera|southpalmmaldives.com
145|Anantara Resort and Spa Maldives|Anantara Dhigu;Anantara Dhigu Maldives;Dhigufinolhu;Dhigu|anantara.com
146|Anantara Veli and Naladhu|Anantara Veli;Naladhu Private Island;Naladhu;Veligandu Huraa|anantara.com
147|Sun Siyam Vilu Reef Maldives|Sun Siyam Vilu Reef;Vilu Reef;Meedhuffushi|sunsiyam.com
148|Sun Siyam Iru Fushi Maldives|Sun Siyam Iru Fushi;Iru Fushi;Irufushi;TSSI|sunsiyam.com
149|Biyaadhoo Island Resort|Biyadhoo;Biyaadhoo|biyadhoo.com
150|Coco Bodu Hithi|Coco Bodu Hithi;Bodu Hithi|cococollection.com
151|Coco Palm Dhunikolhu|Coco Palm Dhuni Kolhu;Dhuni Kolhu;Dhunikolhu|cococollection.com
152|Makunudu Island|Makunudu;Makunudhoo|makunudu.com
153|Taj Coral Reef Resort and Spa|Taj Coral Reef;Hembadhu|tajhotels.com
154|Taj Exotica Resort & Spa Maldives|Taj Exotica;Emboodhu Finolhu|tajhotels.com
155|Constance Halaveli Resort|Constance Halaveli;Halaveli;CHRG|constancehotels.com
156|Drift Theluveliga Retreat|Drift Theluveliga;Theluveliga|driftmaldives.com
157|The Nautilus Maldives|Nautilus Maldives;Thiladhoo|thenautilusmaldives.com
158|Patina Maldives, Fari Islands|Patina Maldives;Patina Fari Islands|patinahotels.com
159|Cinnamon Dhonveli Maldives|Cinnamon Dhonveli;Dhonveli;Kanuhuraa|cinnamonhotels.com
160|Cinnamon Velifushi Maldives|Cinnamon Velifushi;Velifushi;Aarah Vaavu|cinnamonhotels.com
161|Ellaidhoo Maldives By Cinnamon|Ellaidhoo|cinnamonhotels.com
162|The Marina at Crossroads Maldives|Marina at Crossroads;Crossroads Maldives;CROSSROADS|crossroadsmaldives.com
163|Adaaran Prestige Vadoo|Vadoo;Adaaran Prestige Vadoo|adaaran.com
164|Baros Maldives|Baros|baros.com
165|Velassaru Maldives|Velassaru;NIVA Velassaru|velassaru.com
166|Kuramathi Maldives|Kuramathi|kuramathi.com
167|Milaidhoo Island Maldives|Milaidhoo|milaidhoo.com
168|You & Me Maldives|You & Me Maldives;You and Me Maldives;You & Me by Cocoon;Uthurumaafaru|youandmemaldives.com
169|Banyan Tree Maldives Vabbinfaru|Banyan Tree Vabbinfaru;Vabbinfaru|banyantree.com
170|Cocogiri Island Resort|Cocogiri|cocogiri.com
171|Velaa Private Island Maldives|Velaa Private Island;Velaa|velaaprivateisland.com
172|Mirihi Island Resort|Mirihi|mirihi.com
173|Kurumba Maldives|Kurumba;Vihamanaafushi|kurumba.com
174|Vilamendhoo Island Resort|Vilamendhoo|vilamendhoo.com
175|Villa Nautica Paradise Island|Villa Nautica;Paradise Island Resort;Paradise Island;Lankanfinolhu|villanautica.com
176|Villa Park Sun Island|Villa Park;Sun Island Resort;Sun Island;Nalaguraidhoo|villapark.com.mv
177|Royal Island Resort and Spa|Royal Island;Horubadhoo|royal-island.com
178|Diamonds Athuruga Beach & Water Villas|Diamonds Athuruga;Athuruga|diamondsresorts.com
179|Siyam World Maldives|Siyam World;Dhigurah Noonu|sunsiyam.com
180|Lux* South Ari Atoll, Maldives|LUX* South Ari Atoll;LUX South Ari;LUX* Maldives;Dhidhoofinolhu|luxresorts.com
181|Yash Nature Resort|Yash Nature Resort;Yash Maldives|yashmaldives.com
182|Kuredhivaru Resort and Spa|Kuredhivaru;Mövenpick Kuredhivaru;Movenpick Kuredhivaru;Kuredhivaru Resort|kuredhivaru.com
"""

# words that never discriminate a property on their own
GENERIC_ALIAS_STOP = {"maldives", "resort", "island", "spa", "veli", "dhigu", "gan", "fares", "varu", "noonu"}


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def load_resorts():
    out = []
    for line in RESORTS_RAW.strip().splitlines():
        num, name, aliases, domain = line.split("|")
        aliases = [a.strip() for a in aliases.split(";") if a.strip()]
        rid = int(num)
        out.append({
            "resort_id": rid,
            "name": name,
            "slug": slugify(name)[:50].rstrip("-"),
            "folder": f"{rid:03d}_{slugify(name)[:50].rstrip('-')}",
            "aliases": aliases,
            "domain_hint": domain,
        })
    assert len(out) == 182
    return out


RESORTS = load_resorts()
BY_ID = {r["resort_id"]: r for r in RESORTS}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _match_terms(r):
    """Return list of (term, strength) for a resort: strong terms are unique island/brand words."""
    terms = []
    terms.append((norm(r["name"]), 3))
    for a in r["aliases"]:
        n = norm(a)
        if not n:
            continue
        if n in GENERIC_ALIAS_STOP or len(n) < 4:
            continue
        terms.append((n, 2))
    return terms


MATCH_TERMS = {r["resort_id"]: _match_terms(r) for r in RESORTS}

# Resorts whose aliases need extra care: a hit on a weak alias alone is "needs-review"
AMBIGUOUS_TERMS = {"veli", "finolhu", "dhigurah", "kanifushi", "kudafushi", "residence maldives", "dhigu", "paradise island", "sun island"}


def match_resort(text, hint_ids=None):
    """Find resort ids whose name/alias appears in text.

    Returns (best_ids, review) where review is True when ambiguous.
    hint_ids: resort ids suggested by the source (e.g. the page we found it on).
    """
    t = " " + norm(text) + " "
    tc = t.replace(" ", "")
    scores = {}
    for rid, terms in MATCH_TERMS.items():
        best = 0
        for term, strength in terms:
            if f" {term} " in t or (len(term) >= 4 and term not in GENERIC_ALIAS_STOP and term.replace(" ", "") in tc):
                w = strength + (len(term) / 20.0)
                if term in AMBIGUOUS_TERMS:
                    w -= 1.5
                best = max(best, w)
        if best:
            scores[rid] = best
    if not scores:
        return [], False
    if hint_ids:
        for h in hint_ids:
            if h in scores:
                scores[h] += 1
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top = ranked[0][1]
    winners = [rid for rid, s in ranked if s >= top - 0.6]
    # Jawakara twin islands share documents
    if set(winners) <= {29, 83} and len(winners) == 1 and "jawakara" in t:
        winners = [29, 83]
    review = len(winners) > 1 and not set(winners) <= {29, 83}
    return winners, review


FOREIGN_SISTER_HINTS = [
    "angkor", "siem reap", "osaka", "istanbul", "seychelles", "hua hin", "bangkok", "phuket", "koh samui",
    "dubai", "abu dhabi", "doha", "bali", "mauritius", "sri lanka", "colombo", "zanzibar", "oman", "tunisia",
    "vietnam", "hoi an", "singapore", "tokyo", "kyoto", "jakarta", "bora bora", "fiji", "tahiti", "madrid",
    "lisbon", "sicily", "tuscany", "kenya", "mozambique", "cambodia", "chiang mai", "krabi", "samui", "pattaya",
    "koh lanta", "goa", "rajasthan", "udaipur", "jaipur", "chennai", "kerala", "bhutan", "nepal", "london", "paris",
    "new york", "miami", "cancun", "punta cana", "riviera maya", "jamaica", "aruba", "bahamas", "hong kong", "macau",
    "hainan", "sanya", "turkey", "antalya", "bodrum", "egypt", "red sea", "sharm", "hurghada", "jeddah", "riyadh",
    "cyprus", "greece", "crete", "mallorca", "ibiza", "tenerife", "canary", "gran canaria", "lanzarote", "fuerteventura",
    "cape verde", "sal", "boa vista", "sardinia", "capri", "amalfi", "rome", "venice", "milan", "lake como",
]


# Properties that are NOT in the list but share sources/groups with listed ones; their files go to "Extra resorts".
EXTRA_RESORT_TERMS = ["nala maldives", "nalamaldives", "kihaa", "ailafushi", "rah gili", "oblu xperience", "sun siyam pasikudah",
                      "siyam pasikudah", "olhuveli beach", "kanuhura sri", "ritz carlton langkawi", "cinnamon bentota", "cinnamon lakeside",
                      "hudhuranfushi surf", "amari havodda sri"]


def is_extra_resort(text):
    t = norm(text).replace(" ", "")
    return [e for e in EXTRA_RESORT_TERMS if e.replace(" ", "") in t]


def looks_foreign(text, url=""):
    t = norm(text)[:4000] + " " + norm(url)
    hits = [h for h in FOREIGN_SISTER_HINTS if f" {h} " in f" {t} "]
    maldives = "maldives" in t or "maldive" in t or "maldiv" in t
    return bool(hits) and not maldives, hits


if __name__ == "__main__":
    print(json.dumps(RESORTS[:3], indent=1))
    print(match_resort("FactSheetKuredu110125103126.pdf"))
    print(match_resort("Anantara Angkor Resort factsheet"))
    print(match_resort("Jawakara Islands Maldives Dheruhfinolhu factsheet"))
    print(match_resort("Kudadoo Maldives Private Island Factsheet 2025"))
