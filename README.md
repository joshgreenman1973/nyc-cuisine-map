# New York City restaurant cuisines, by neighborhood

An interactive map of how New York City's restaurants break down by cuisine, by
borough and by neighborhood. Pick a cuisine and the map shades each neighborhood
by either the raw number of restaurants or that cuisine's share of the
neighborhood's restaurants.

## Data source

- **Restaurants:** NYC Department of Health and Mental Hygiene, *DOHMH New York
  City Restaurant Inspection Results* — NYC Open Data dataset
  [`43nn-pn8j`](https://data.cityofnewyork.us/Health/DOHMH-New-York-City-Restaurant-Inspection-Results/43nn-pn8j).
- **Neighborhoods:** 2010 Neighborhood Tabulation Areas, NYC Department of City
  Planning (geometry simplified for display).

## How the city defines "cuisine"

It largely doesn't. Per the dataset's own data dictionary, the cuisine field is
*"This field describes the entity (restaurant) cuisine. Optional field provided by
restaurant owner/manager."* In other words the label is **self-reported and
optional** — the owner or manager picks one value from a fixed list of about 90
choices the city maintains when the restaurant is permitted. The Health Department
publishes no written definition distinguishing one category from another and does
not vet the choice. That is why the categories are uneven (some name a country,
some a food, some a style), why roughly 3,500 establishments are left blank, and
why labels like "Spanish" (here meaning Spanish-Caribbean/Latino food) can mislead.

## How the numbers are built

- The inspection dataset has **one row per violation**. Each establishment has a
  unique `CAMIS` id. Every count here is **distinct `CAMIS`** — each restaurant
  counted once, no matter how many inspections or violations it has.
- "Cuisine" is the single coarse label the city assigns each establishment.
- Borough and neighborhood are taken from the establishment's own record in the
  dataset.
- **Share of neighborhood** = a cuisine's establishments divided by all
  establishments (any cuisine) in that neighborhood.

Aggregations are pulled live from the Socrata API with `count(distinct camis)`
grouped by `cuisine_description`, `boro` and `nta`. See `build_data.py`.

## Honest limitations

- **"Cuisine" is coarse and self/inspector-assigned.** "Chinese" flattens every
  regional Chinese cuisine; "Spanish" in this dataset means
  Spanish-Caribbean/Latino food, not food from Spain.
- **The two groupings are an editorial call.** The build script splits categories
  into "place of origin" (Chinese, Italian, Mexican...) vs. "food types & styles"
  (pizza, coffee, "American," "New American," "Fusion," etc.). The word "ethnic"
  is deliberately avoided. Where a category names a style rather than a country,
  the call is a judgment, not a fact. You can map any category either way.
- **Neighborhood boundaries are statistical, not colloquial.** Some are large and
  blur famous enclaves (Koreatown straddles two; Little Italy sits inside a big
  SoHo-TriBeCa zone).
- **Counts slightly overstate "open right now"** — the dataset retains some
  recently-closed establishments.
- ~3,500 establishments have a blank cuisine field; ~600 are "Other."

## Files

- `index.html` — the map (Leaflet, no build step).
- `build_data.py` — turns raw Socrata pulls into `data/bundle.json`.
- `data/` — raw API pulls, the 2010 NTA geometry, and the compact bundle.

## Rebuild the data

```bash
# raw pulls (cuisine totals, borough x cuisine, neighborhood x cuisine)
# are saved in data/*.json; regenerate the bundle with:
python3 build_data.py
```

## Run locally

```bash
python3 -m http.server 8531
# open http://localhost:8531
```
