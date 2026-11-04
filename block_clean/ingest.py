"""Pull neighbor-sized 311 cases and nearby shops, and store them with coordinates.

311 cases and registered businesses already include lat/lon from DataSF.
This script keeps those points as geo locations. It does not call a geocoder
for the city data. Shop signup geocodes an address later, when a person types one.

Which open cases count is decided by Mistral in fit.py, over the last 180 days.
"""

import sys
from datetime import datetime, timedelta

import requests

from catalog import SECTORS, SHOP_NAICS_PREFIXES, business_about
from fit import category_key, judge_categories
from geo import address_key
from store import get_store

CASES_URL = "https://data.sf.gov/resource/vw6y-z8j6.json"
BUSINESSES_URL = "https://data.sf.gov/resource/g8m3-pdis.json"
DAYS = 180
HEADERS = {"User-Agent": "block-clean-hacknight"}
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def public_photo(url):
    """Only links a browser can show. The Verint attachment pages need a city login."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    if "cloudinary" in url:
        return url
    path = url.split("?", 1)[0].lower()
    if path.endswith(IMAGE_SUFFIXES):
        return url
    return None


def fetch_socrata(url, limit, page_size=10000, **params):
    rows = []
    while len(rows) < limit:
        page = {**params, "$limit": min(page_size, limit - len(rows)), "$offset": len(rows)}
        response = requests.get(url, params=page, headers=HEADERS, timeout=120)
        response.raise_for_status()
        batch = response.json()
        rows.extend(batch)
        print(f"  fetched {len(rows)}", flush=True)
        if len(batch) < page["$limit"]:
            break
    return rows


def fetch_category_counts(since):
    params = {
        "$select": "service_name, service_subtype, service_details, count(*) as n",
        "$where": f"requested_datetime > '{since}' AND status_description = 'Open'",
        "$group": "service_name, service_subtype, service_details",
        "$limit": 5000,
    }
    response = requests.get(CASES_URL, params=params, headers=HEADERS, timeout=120)
    response.raise_for_status()
    return response.json()


def fetch_cases():
    since = (datetime.now() - timedelta(days=DAYS)).strftime("%Y-%m-%dT00:00:00")
    print(f"Classifying open 311 categories since {since[:10]}...")
    groups = fetch_category_counts(since)
    verdicts = judge_categories(groups)
    accepted = {key for key, verdict in verdicts.items() if verdict.get("neighbor_ok")}
    yes = [verdicts[key] for key in accepted]
    print(f"  {len(yes)} categories a neighbor can take, {len(verdicts) - len(yes)} left with the city")
    for verdict in sorted(yes, key=lambda item: (item.get("service_name") or "", item.get("label") or "")):
        print(f"    yes  {verdict.get('service_name')} / {verdict.get('label')}")

    where = (
        f"requested_datetime > '{since}' "
        "AND status_description = 'Open' "
        "AND lat IS NOT NULL AND long IS NOT NULL"
    )
    select = (
        "service_request_id,requested_datetime,service_name,service_subtype,"
        "service_details,address,analysis_neighborhood,media_url,lat,long"
    )
    print("Fetching open cases...")
    rows = fetch_socrata(
        CASES_URL,
        limit=50000,
        **{"$select": select, "$where": where, "$order": "requested_datetime DESC"},
    )
    docs = []
    for row in rows:
        try:
            lat, lon = float(row["lat"]), float(row["long"])
        except (KeyError, TypeError, ValueError):
            continue
        if lat == 0 or lon == 0:
            continue
        neighborhood = (row.get("analysis_neighborhood") or "").strip()
        if not neighborhood:
            continue
        name = row.get("service_name") or ""
        subtype = row.get("service_subtype") or ""
        detail = row.get("service_details") or ""
        verdict = verdicts.get(category_key(name, subtype, detail))
        if not verdict or not verdict.get("neighbor_ok"):
            continue
        photo = public_photo((row.get("media_url") or {}).get("url") or "")
        docs.append({
            "service_request_id": row["service_request_id"],
            "requested_at": row.get("requested_datetime"),
            "service_name": name,
            "service_subtype": subtype,
            "service_details": detail,
            "detail_label": verdict.get("label") or "311 request",
            "fit_why": verdict.get("why") or "",
            "address": row.get("address") or "",
            "neighborhood": neighborhood,
            "photo_url": photo,
            "location": {"lat": lat, "lon": lon},
            "volunteer_status": "open",
        })
    print(f"  {len(docs)} cases a neighbor can take")
    return docs


def fetch_businesses():
    prefixes = " OR ".join(
        f"starts_with(self_reported_naics_code, '{prefix}')" for prefix in SHOP_NAICS_PREFIXES
    )
    where = (
        "location_end_date IS NULL AND dba_end_date IS NULL "
        "AND upper(city) = 'SAN FRANCISCO' AND location IS NOT NULL "
        f"AND ({prefixes})"
    )
    select = (
        "uniqueid,dba_name,full_business_address,business_zip,"
        "neighborhoods_analysis_boundaries,self_reported_naics_code,location"
    )
    print("Fetching geocoded retail and food businesses...")
    rows = fetch_socrata(
        BUSINESSES_URL,
        limit=50000,
        **{"$select": select, "$where": where, "$order": "uniqueid"},
    )
    docs = []
    for row in rows:
        coords = (row.get("location") or {}).get("coordinates") or []
        name = (row.get("dba_name") or "").strip()
        if len(coords) != 2 or not name:
            continue
        lon, lat = coords
        naics = (row.get("self_reported_naics_code") or "").strip()
        address = (row.get("full_business_address") or "").strip()
        neighborhood = (row.get("neighborhoods_analysis_boundaries") or "").strip()
        sector = SECTORS.get(naics[:2], "")
        docs.append({
            "business_id": row["uniqueid"],
            "name": name,
            "address": address,
            "address_key": address_key(address),
            "zip": row.get("business_zip") or "",
            "neighborhood": neighborhood,
            "sector": sector,
            "about": business_about(name, sector, address, neighborhood),
            "location": {"lat": float(lat), "lon": float(lon)},
        })
    print(f"  {len(docs)} shops with a point")
    return docs


def main():
    cases_only = "--cases-only" in sys.argv
    store = get_store()
    print(f"Store: {store.backend}")
    cases = fetch_cases()
    stored_cases = store.replace_cases(cases)
    if cases_only:
        print(f"Stored {stored_cases} cases")
        return
    businesses = fetch_businesses()
    stored_businesses = store.replace_businesses(businesses)
    print(f"Stored {stored_cases} cases and {stored_businesses} businesses")


if __name__ == "__main__":
    main()
