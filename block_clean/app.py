import re
import uuid
from pathlib import Path

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from catalog import BUSINESS_LIMIT, BUSINESS_RADIUS_M, NOTIFY_LIMIT, SHOP_RADIUS_M, case_business_query
from emailer import mail_mode, notify_shops, public_url, upload_file
from geo import address_key, geocode_address
from paths import STATIC, UPLOADS, ensure_dirs
from store import AlreadySolved, CaseNotFound, get_store

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_PHOTO_BYTES = 8 * 1024 * 1024
IMAGE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
}

ensure_dirs()
app = FastAPI(title="Block Clean")
store = get_store()
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")


class VolunteerIn(BaseModel):
    email: str
    display_name: str = ""
    neighborhood: str


class ShopIn(BaseModel):
    email: str
    name: str
    address: str


def _email(value):
    email = (value or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Enter a real email address")
    return email


def _display_name(value, email):
    name = re.sub(r"\s+", " ", (value or "").strip())[:40]
    return name or email.split("@")[0][:40]


def _public_case(case):
    return {
        "service_request_id": case["service_request_id"],
        "requested_at": case.get("requested_at"),
        "detail_label": case.get("detail_label"),
        "service_details": case.get("service_details"),
        "address": case.get("address"),
        "neighborhood": case.get("neighborhood"),
        "photo_url": case.get("photo_url"),
        "location": case.get("location"),
        "volunteer_status": case.get("volunteer_status"),
    }


def _public_business(business):
    return {
        "name": business.get("name"),
        "address": business.get("address"),
        "neighborhood": business.get("neighborhood"),
        "sector": business.get("sector"),
        "distance_m": business.get("distance_m"),
        "location": business.get("location"),
    }


def _save_photo(upload: UploadFile):
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    filename = (upload.filename or "").lower()
    if content_type not in IMAGE_EXT and not filename.endswith(tuple(IMAGE_EXT.values()) + (".jpeg",)):
        raise HTTPException(400, "Each proof photo needs to be an image")
    data = upload.file.read()
    if not data:
        raise HTTPException(400, "That photo is empty")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(400, "Photos need to be under 8 MB")
    ext = IMAGE_EXT.get(content_type)
    if not ext:
        ext = ".jpg" if filename.endswith((".jpg", ".jpeg")) else Path(filename).suffix.lower() or ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOADS / name).write_bytes(data)
    return f"/uploads/{name}"


def _locate_shop(name, address):
    match = store.match_business(address, name=name)
    if match and match.get("location"):
        return {
            "lat": match["location"]["lat"],
            "lon": match["location"]["lon"],
            "neighborhood": match.get("neighborhood") or "",
            "source": "sf-business-registry",
            "label": match.get("address") or address,
        }
    try:
        point = geocode_address(address)
    except requests.RequestException as exc:
        raise HTTPException(502, f"The address lookup failed: {exc}") from exc
    if not point:
        return None
    return {
        "lat": point["lat"],
        "lon": point["lon"],
        "neighborhood": store.nearest_neighborhood(point["lat"], point["lon"]) or "",
        "source": "nominatim",
        "label": point.get("label") or address,
    }


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "backend": store.backend, "mail": mail_mode(), **store.counts()}


@app.get("/api/neighborhoods")
def neighborhoods():
    return store.neighborhoods()


@app.post("/api/volunteers")
def save_volunteer(body: VolunteerIn):
    email = _email(body.email)
    name = _display_name(body.display_name, email)
    neighborhood = body.neighborhood.strip()
    if not neighborhood:
        raise HTTPException(400, "Pick a neighborhood")
    volunteer = store.upsert_volunteer(email, name, neighborhood)
    return {
        "email": volunteer["email"],
        "display_name": volunteer["display_name"],
        "neighborhood": volunteer["neighborhood"],
    }


@app.get("/api/cases")
def cases(neighborhood: str, limit: int = 1000):
    neighborhood = neighborhood.strip()
    if not neighborhood:
        raise HTTPException(400, "Pick a neighborhood")
    rows = store.cases_in_neighborhood(neighborhood, min(limit, 1000))
    return [_public_case(row) for row in rows]


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "No case with that id")
    point = case.get("location") or {}
    businesses = []
    shops = []
    if "lat" in point:
        businesses = store.nearby_businesses(
            point["lat"], point["lon"], BUSINESS_RADIUS_M, BUSINESS_LIMIT, query=case_business_query(case),
        )
        shops = store.nearby_shops(point["lat"], point["lon"], SHOP_RADIUS_M)[:NOTIFY_LIMIT]
    return {
        "case": _public_case(case),
        "businesses": [_public_business(row) for row in businesses],
        "shops": [{"name": row.get("name"), "distance_m": row.get("distance_m")} for row in shops],
    }


@app.post("/api/cases/{case_id}/complete")
def complete_case(
    case_id: str,
    email: str = Form(...),
    display_name: str = Form(""),
    before: UploadFile = File(...),
    after: UploadFile = File(...),
):
    email = _email(email)
    name = _display_name(display_name, email)
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "No case with that id")
    if case.get("volunteer_status") == "solved":
        raise HTTPException(409, "Someone already logged this one")
    before_url = _save_photo(before)
    after_url = _save_photo(after)
    store.upsert_volunteer(email, name, case.get("neighborhood") or "")
    try:
        completion = store.complete_case(case_id, email, name, before_url, after_url)
    except CaseNotFound:
        raise HTTPException(404, "No case with that id")
    except AlreadySolved:
        raise HTTPException(409, "Someone already logged this one")

    point = case.get("location") or {}
    shops = []
    businesses = []
    if "lat" in point:
        shops = store.nearby_shops(point["lat"], point["lon"], SHOP_RADIUS_M)[:NOTIFY_LIMIT]
        businesses = store.nearby_businesses(
            point["lat"], point["lon"], BUSINESS_RADIUS_M, BUSINESS_LIMIT, query=case_business_query(case),
        )
    # A person should not get a shop email about their own cleanup.
    shops = [shop for shop in shops if shop.get("email") != email]
    note = notify_shops(
        shops,
        {"email": email, "display_name": name},
        case,
        public_url(before_url),
        public_url(after_url),
        upload_file(after_url),
    )
    store.mark_notified(case_id, [row["email"] for row in note["shops"] if row["delivery"] != "failed"])
    board = store.leaderboard(limit=20, email=email)
    you = board.get("you") or {}
    return {
        "solved": you.get("solved", 1),
        "rank": you.get("rank"),
        "before_url": before_url,
        "after_url": after_url,
        "mail": mail_mode(),
        "note": {"subject": note["subject"], "text": note["text"], "reply_to": note["reply_to"]},
        "notified": note["shops"],
        "businesses": [_public_business(row) for row in businesses],
        "leaderboard": board,
    }


@app.get("/api/leaderboard")
def leaderboard(email: str = ""):
    who = email.strip().lower()
    if who and not EMAIL_RE.match(who):
        who = ""
    return store.leaderboard(limit=20, email=who or None)


@app.post("/api/shops")
def save_shop(body: ShopIn):
    email = _email(body.email)
    name = re.sub(r"\s+", " ", body.name.strip())[:80]
    address = re.sub(r"\s+", " ", body.address.strip())[:120]
    if len(name) < 2:
        raise HTTPException(400, "Enter the shop name")
    if len(address) < 4:
        raise HTTPException(400, "Enter a street address")
    located = _locate_shop(name, address)
    if not located:
        raise HTTPException(
            400,
            "We couldn't place that address in San Francisco. Try a street address like 364 9th St.",
        )
    shop = store.upsert_shop({
        "email": email,
        "name": name,
        "address": address,
        "address_key": address_key(address),
        "neighborhood": located["neighborhood"],
        "location": {"lat": located["lat"], "lon": located["lon"]},
        "source": located["source"],
    })
    return {
        "name": shop["name"],
        "email": shop["email"],
        "address": shop["address"],
        "neighborhood": shop.get("neighborhood") or "",
        "location": shop["location"],
        "source": shop["source"],
        "placed_at": located["label"],
    }


@app.get("/api/shops")
def shops():
    return [
        {
            "name": shop.get("name"),
            "address": shop.get("address"),
            "neighborhood": shop.get("neighborhood"),
            "location": shop.get("location"),
        }
        for shop in store.list_shops()
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
