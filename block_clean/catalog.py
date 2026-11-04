"""Which businesses count as shops. Which 311 jobs a neighbor can take is decided in fit.py."""

# NAICS prefixes for storefronts a cleanup note is actually for.
# 44/45 retail, 72 food and lodging. Offices and holding companies are left out.
SHOP_NAICS_PREFIXES = ("44", "45", "72")

SECTORS = {
    "44": "Retail",
    "45": "Retail",
    "72": "Food and lodging",
}

# How close a signed-up shop has to be to get the after photo.
SHOP_RADIUS_M = 400

# How close a registered business has to be to be a semantic candidate.
BUSINESS_RADIUS_M = 400
BUSINESS_LIMIT = 8

INFERENCE_ID = "mistral-embeddings"

NOTIFY_LIMIT = 15


def business_about(name, sector, address, neighborhood):
    """Text embedded for semantic search. The name and sector are what distinguish a shop."""
    kind = (sector or "local").lower()
    where = neighborhood or "San Francisco"
    place = address or where
    return (
        f"{name} is a {kind} storefront at {place} in {where}, San Francisco. "
        "People walking this block pass the sidewalk in front of this shop."
    )


def case_business_query(case):
    """What we ask the embedding model when ranking shops for one 311 case."""
    street = ((case or {}).get("address") or "a San Francisco sidewalk").split(",")[0]
    label = (case or {}).get("detail_label") or "street and sidewalk cleaning"
    neighborhood = (case or {}).get("neighborhood") or "San Francisco"
    return (
        f"{label} on the sidewalk at {street} in {neighborhood}, San Francisco. "
        "A storefront on this block that would want the sidewalk in front of it cleaned up."
    )
