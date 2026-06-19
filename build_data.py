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

bundle = {
    "meta": {
        "source": "NYC DOHMH Restaurant Inspection Results (Socrata 43nn-pn8j)",
        "geography": "2010 Neighborhood Tabulation Areas (NYC Dept of City Planning)",
        "unit": "unique establishments (distinct CAMIS)",
        "total_establishments": total_establishments,
        "n_cuisines": len([c for c in cuisines if c["raw"]]),
    },
    "boro_totals": boro_totals,
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
