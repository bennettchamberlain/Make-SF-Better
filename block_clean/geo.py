import math
import re

import requests

SF_BOX = {
    "south": 37.70,
    "north": 37.84,
    "west": -122.55,
    "east": -122.35,
}

_SUFFIXES = (
    (" STREET", " ST"),
    (" AVENUE", " AVE"),
    (" BOULEVARD", " BLVD"),
    (" ROAD", " RD"),
    (" DRIVE", " DR"),
    (" LANE", " LN"),
    (" PLACE", " PL"),
    (" COURT", " CT"),
    (" TERRACE", " TER"),
)


def haversine_m(lat1, lon1, lat2, lon2):
    radius = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def in_san_francisco(lat, lon):
    return SF_BOX["south"] <= lat <= SF_BOX["north"] and SF_BOX["west"] <= lon <= SF_BOX["east"]


def address_key(value):
    """Fold a street address so '364 9th Street' matches the city's '364 9th St'."""
    text = (value or "").upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[.,#]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for long, short in _SUFFIXES:
        text = text.replace(long, short)
    text = re.sub(r"\bSAN FRANCISCO\b.*", "", text)
    text = re.sub(r"\bCALIFORNIA\b", "", text)
    text = re.sub(r"\bCA\b", "", text)
    text = re.sub(r"\b9\d{4}(?:-\d{4})?\b", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text


def geocode_address(address):
    """Turn a street address into a point inside San Francisco.

    Uses OpenStreetMap Nominatim. Shop signup falls back to this when the
    address is not already in the city business registry.
    """
    query = address.strip()
    if "san francisco" not in query.lower():
        query = f"{query}, San Francisco, CA"
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "us",
            "viewbox": f"{SF_BOX['west']},{SF_BOX['north']},{SF_BOX['east']},{SF_BOX['south']}",
            "bounded": 1,
        },
        headers={"User-Agent": "BlockClean/0.1 (San Francisco neighborhood cleanup)"},
        timeout=20,
    )
    response.raise_for_status()
    hits = response.json()
    if not hits:
        return None
    lat, lon = float(hits[0]["lat"]), float(hits[0]["lon"])
    if not in_san_francisco(lat, lon):
        return None
    return {"lat": lat, "lon": lon, "label": hits[0].get("display_name") or query}
