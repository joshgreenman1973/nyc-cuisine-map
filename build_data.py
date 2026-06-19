#!/usr/bin/env python3
"""Build compact data bundle for the NYC cuisine map.
Reads raw Socrata aggregations in data/ and writes data/bundle.json.
All counts are DISTINCT establishments (CAMIS), not inspection rows.
"""
import json, os

D = os.path.join(os.path.dirname(__file__), "data")

def load(f):
    with open(os.path.join(D, f)) as fh:
        return json.load(fh)

cuisine_totals = load("cuisine_totals.json")
boro_cuisine   = load("boro_cuisine.json")
nta_cuisine    = load("nta_cuisine.json")
boro_totals_raw= load("boro_totals.json")
nta_pop_raw    = load("nta_population.json")
geo            = load("nta2010.min.geojson")

# NTA code -> name from the geojson itself (authoritative match to geometry)
nta_name = {ft["properties"]["NTACode"]: ft["properties"]["NTAName"]
            for ft in geo["features"]}
nta_boro = {ft["properties"]["NTACode"]: ft["properties"]["BoroName"]
            for ft in geo["features"]}

# Food-type / style buckets: categories that name a *style or item* rather than a
# country/region of origin. Everything else is treated as a named place of origin.
# (No "ethnic" label is applied anywhere — that word is deliberately avoided.)
GENERIC = {
 "American","","Coffee/Tea","Pizza","Bakery Products/Desserts","Chicken","Other",
 "Juice, Smoothies, Fruit Salads","Donuts","Hamburgers","Sandwiches","Frozen Desserts",
 "Bagels/Pretzels","New American","Sandwiches/Salads/Mixed Buffet","Salads",
 "Bottled Beverages","Steakhouse","Seafood","Vegan","Vegetarian",
 "Soups/Salads/Sandwiches","Barbecue","Pancakes/Waffles","Hotdogs","Hotdogs/Pretzels",
 "Continental","Soups","Fruits/Vegetables","Nuts/Confectionary",
 "Not Listed/Not Applicable","Hawaiian","Californian","Fusion","Tapas","Creole",
 "Cajun","Creole/Cajun","Soul Food","Southwestern","Haute Cuisine","Chimichurri",
}

def clean(c):
    return c if c else "(blank / unlabeled)"

# citywide totals
cuisines = []
for r in cuisine_totals:
    c = r.get("cuisine_description") or ""
    cuisines.append({
        "name": clean(c),
        "raw": c,
        "total": int(r["n"]),
        # True = names a country/region of origin; False = food-type or style
        "origin": c not in GENERIC and c != "",
    })

# borough x cuisine -> {raw_cuisine: {boro: n}}
boro_map = {}
for r in boro_cuisine:
    b = r.get("boro"); c = r.get("cuisine_description") or ""
    if b in (None, "0"): continue
    boro_map.setdefault(c, {})[b] = int(r["n"])

# nta x cuisine -> {raw_cuisine: {nta_code: n}}
nta_map = {}
for r in nta_cuisine:
    code = r.get("nta"); c = r.get("cuisine_description") or ""
    if code not in nta_name:  # drop codes with no matching polygon
        continue
    nta_map.setdefault(c, {})[code] = int(r["n"])

# per-nta total (all cuisines) for context / per-capita-ish normalization option
nta_total = {}
for r in nta_cuisine:
    code = r.get("nta")
    if code not in nta_name: continue
    nta_total[code] = nta_total.get(code, 0) + int(r["n"])

# borough totals (denominator for the borough cuisine-mix chart)
boro_totals = {r["boro"]: int(r["n"]) for r in boro_totals_raw if r["boro"] not in ("0", None)}
total_establishments = sum(int(r["n"]) for r in boro_totals_raw)

# ----- per-neighborhood stats: diversity, dominance, density -----
import math
nta_pop = {r["nta_code"]: int(r["population"]) for r in nta_pop_raw if r.get("population")}

# per-NTA cuisine counts (labeled only, i.e. drop blank) + a total incl. blank
nta_labeled = {}   # code -> {cuisine: n}
for r in nta_cuisine:
    code = r.get("nta"); c = r.get("cuisine_description") or ""
    if code not in nta_name or c == "":
        continue
    nta_labeled.setdefault(code, {})[c] = int(r["n"])

nta_stats = {}
for code, name in nta_name.items():
    total = nta_total.get(code, 0)
    if total == 0:
        continue
    labeled = nta_labeled.get(code, {})
    n_lab = sum(labeled.values())
    n_cuisines = len(labeled)
    # Simpson diversity over labeled restaurants: P(two random ones differ)
    simpson = 0.0
    if n_lab > 1:
        simpson = 1.0 - sum((v / n_lab) ** 2 for v in labeled.values())
    # dominance: largest single cuisine as a share of ALL restaurants in the NTA
    top_cuisine, top_n = (max(labeled.items(), key=lambda kv: kv[1]) if labeled else ("", 0))
    top_share = top_n / total if total else 0
    pop = nta_pop.get(code, 0)
    per1k = (total / pop * 1000) if pop else None
    nta_stats[code] = {
        "name": name, "boro": nta_boro.get(code, ""), "total": total,
        "n_cuisines": n_cuisines, "simpson": round(simpson, 4),
        "top_cuisine": top_cuisine, "top_share": round(top_share, 4),
        "pop": pop, "per1k": round(per1k, 1) if per1k is not None else None,
    }

# non-residential NTAs (parks, cemeteries, airports) have lowercase placeholder
# names in the 2010 scheme, e.g. "park-cemetery-etc-Manhattan" -- exclude them.
def is_real(s):
    nm = s["name"]
    return bool(nm) and nm[0].isupper() and "Airport" not in nm

def leaderboard(key, reverse=True, where=lambda s: True, n=10):
    rows = [dict(code=code, **s) for code, s in nta_stats.items() if is_real(s) and where(s)]
    rows.sort(key=lambda s: (s[key] is None, s[key] if s[key] is not None else 0), reverse=reverse)
    return rows[:n]

MIN_MIX = 50   # need enough restaurants for "mixed/least-mixed" to mean anything
MIN_DEN = 20   # and a floor for the density board
stories = {
    "most_mixed":   leaderboard("simpson", True,  lambda s: s["total"] >= MIN_MIX),
    "least_mixed":  leaderboard("top_share", True, lambda s: s["total"] >= MIN_MIX),
    "densest":      leaderboard("per1k", True,  lambda s: s["total"] >= MIN_DEN and (s["pop"] or 0) >= 500),
    "most_restaurants": leaderboard("total", True),
    "most_cuisines":    leaderboard("n_cuisines", True, lambda s: s["total"] >= MIN_DEN),
    "thresholds": {"min_mix": MIN_MIX, "min_density": MIN_DEN},
}

bundle = {
    "meta": {
        "source": "NYC DOHMH Restaurant Inspection Results (Socrata 43nn-pn8j)",
        "geography": "2010 Neighborhood Tabulation Areas (NYC Dept of City Planning)",
        "unit": "unique establishments (distinct CAMIS)",
        "total_establishments": total_establishments,
        "n_cuisines": len([c for c in cuisines if c["raw"]]),
    },
    "boro_totals": boro_totals,
    "nta_stats": nta_stats,
    "stories": stories,
    "cuisines": cuisines,
    "nta_name": nta_name,
    "nta_boro": nta_boro,
    "nta_total": nta_total,
    "boro_by_cuisine": boro_map,
    "nta_by_cuisine": nta_map,
}
with open(os.path.join(D, "bundle.json"), "w") as fh:
    json.dump(bundle, fh, separators=(",", ":"))
print("wrote bundle.json")
print("cuisines:", len(cuisines), "| NTAs:", len(nta_name))
print("origin cuisines:", sum(1 for c in cuisines if c["origin"]))
