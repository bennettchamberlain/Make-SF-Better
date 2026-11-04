"""Pull volunteer-safe 311 cases and nearby shops, and store them with coordinates.

311 cases and registered businesses already include lat/lon from DataSF.
This script keeps those points as geo locations. It does not call a geocoder
for the city data. Shop signup geocodes an address later, when a person types one.
"""

from datetime import datetime, timedelta

import requests

from catalog import SECTORS, SHOP_NAICS_PREFIXES, VOLUNTEER_DETAILS, business_about
from geo import address_key
from store import get_store

CASES_URL = "https://data.sf.gov/resource/vw6y-z8j6.json"
BUSINESSES_URL = "https://data.sf.gov/resource/g8m3-pdis.json"
DAYS = 180
HEADERS = {"User-Agent": "block-clean-hacknight"}


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


def fetch_cases():
    details = ",".join(f"'{name}'" for name in VOLUNTEER_DETAILS)
    since = (datetime.now() - timedelta(days=DAYS)).strftime("%Y-%m-%dT00:00:00")
    where = (
        f"requested_datetime > '{since}' "
        "AND service_name = 'Street and Sidewalk Cleaning' "
        "AND status_description = 'Open' "
        f"AND service_details in ({details}) "
        "AND lat IS NOT NULL AND long IS NOT NULL"
    )
    print(f"Fetching open street-cleaning cases since {since[:10]}...")
    rows = fetch_socrata(CASES_URL, limit=20000, **{"$where": where, "$order": "requested_datetime DESC"})
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
        photo = (row.get("media_url") or {}).get("url") or ""
        detail = row.get("service_details") or ""
        docs.append({
            "service_request_id": row["service_request_id"],
            "requested_at": row.get("requested_datetime"),
            "service_details": detail,
            "detail_label": VOLUNTEER_DETAILS.get(detail, detail.replace("_", " ")),
            "address": row.get("address") or "",
            "neighborhood": neighborhood,
            "photo_url": photo if photo.startswith("https://") else None,
            "location": {"lat": lat, "lon": lon},
            "volunteer_status": "open",
        })
    print(f"  {len(docs)} cases with a neighborhood and a point")
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
    store = get_store()
    print(f"Store: {store.backend}")
    cases = fetch_cases()
    businesses = fetch_businesses()
    stored_cases = store.replace_cases(cases)
    stored_businesses = store.replace_businesses(businesses)
    print(f"Stored {stored_cases} cases and {stored_businesses} businesses")


if __name__ == "__main__":
    main()
