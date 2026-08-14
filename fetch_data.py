#!/usr/bin/env python3
"""Pull the raw Socrata aggregations that build_data.py turns into the bundle.

Source: DOHMH New York City Restaurant Inspection Results (43nn-pn8j), one row
per violation, so every count here is count(distinct camis) -- each restaurant
once, however many times it was inspected.

Writes into data/:
  cuisine_totals.json   cuisine        -> distinct establishments
  boro_cuisine.json     boro x cuisine -> distinct establishments
  nta_cuisine.json      nta  x cuisine -> distinct establishments
  boro_totals.json      boro           -> distinct establishments
  camis_dba_nta.json    one row per establishment (name, nta, boro)
  camis_full.json       one row per establishment (address, lat/lng, cuisine)
  camis_grades.json     graded inspections, newest first

Fails loudly: an HTTP error, a non-array response, an empty result, or a
citywide establishment count that has collapsed versus the committed data all
abort before anything is overwritten. A scraper that exits 0 on an empty pull
is how a map goes stale while still looking healthy.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(D, exist_ok=True)
RES = "https://data.cityofnewyork.us/resource/43nn-pn8j.json"

# A real shrink would mean the city purged records; a small dip is just churn.
MIN_RETAINED_SHARE = 0.80


def get(params, attempts=4):
    url = RES + "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                body = r.read()
            rows = json.loads(body)
            if not isinstance(rows, list):
                raise RuntimeError(f"expected a row array, got {str(rows)[:200]}")
            return rows
        except Exception as e:                      # noqa: BLE001 - retry anything
            last = e
            wait = 5 * (i + 1)
            print(f"    retry {i + 1} in {wait}s ({e})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"giving up on {params.get('$select')}: {last}")


def paged(params, page=50000, cap=400000):
    """Socrata caps a single response; walk $offset until a short page."""
    out = []
    off = 0
    while off < cap:
        p = dict(params)
        p["$limit"] = page
        p["$offset"] = off
        rows = get(p)
        out.extend(rows)
        if len(rows) < page:
            return out
        off += page
    raise RuntimeError(f"pagination cap {cap} hit — widen it or tighten the query")


def prior_len(name):
    try:
        with open(os.path.join(D, name)) as fh:
            return len(json.load(fh))
    except Exception:
        return 0


def write(name, rows, guard=True):
    if not rows:
        raise RuntimeError(f"{name}: query returned 0 rows — refusing to write")
    was = prior_len(name)
    if guard and was and len(rows) < was * MIN_RETAINED_SHARE:
        raise RuntimeError(
            f"{name}: {len(rows)} rows vs {was} committed "
            f"(< {MIN_RETAINED_SHARE:.0%}) — looks like a truncated pull, not real churn")
    tmp = os.path.join(D, name + ".tmp")
    with open(tmp, "w") as fh:
        json.dump(rows, fh)
    os.replace(tmp, os.path.join(D, name))
    print(f"  {name}: {len(rows)} rows (was {was})")


N_DISTINCT = "count(distinct camis) as n"

print("cuisine totals...")
write("cuisine_totals.json",
      get({"$select": f"cuisine_description, {N_DISTINCT}",
           "$group": "cuisine_description", "$limit": 2000}))

print("borough x cuisine...")
write("boro_cuisine.json",
      get({"$select": f"boro, cuisine_description, {N_DISTINCT}",
           "$group": "boro, cuisine_description", "$limit": 5000}))

print("neighborhood x cuisine...")
write("nta_cuisine.json",
      get({"$select": f"nta, cuisine_description, {N_DISTINCT}",
           "$where": "nta IS NOT NULL", "$group": "nta, cuisine_description",
           "$limit": 50000}))

print("borough totals...")
write("boro_totals.json",
      get({"$select": f"boro, {N_DISTINCT}", "$group": "boro", "$limit": 100}))

# No nta filter here: the committed file carries the ~800 establishments the
# city leaves without a neighborhood code, and build_data.py is what decides to
# skip them. Filtering at the pull would quietly change the citywide totals.
print("establishments (name / neighborhood)...")
write("camis_dba_nta.json",
      paged({"$select": "camis, dba, nta, boro",
             "$group": "camis, dba, nta, boro"}))

print("establishments (address / location)...")
write("camis_full.json",
      paged({"$select": "camis, dba, building, street, zipcode, phone, "
                        "latitude, longitude, cuisine_description, nta",
             "$group": "camis, dba, building, street, zipcode, phone, "
                       "latitude, longitude, cuisine_description, nta"}))

print("graded inspections (newest first)...")
write("camis_grades.json",
      paged({"$select": "camis, grade, grade_date",
             "$where": "grade IS NOT NULL AND grade_date IS NOT NULL",
             "$order": "grade_date DESC"}))

print("done.")
