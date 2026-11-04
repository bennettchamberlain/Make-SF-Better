import json
import threading
from collections import Counter
from datetime import datetime, timezone

from geo import address_key, haversine_m
from paths import DB_PATH, ensure_dirs


def _now():
    return datetime.now(timezone.utc).isoformat()


def _empty():
    return {
        "cases": {},
        "businesses": {},
        "volunteers": {},
        "shops": {},
        "completions": {},
    }


class LocalStore:
    """JSON file used when Elasticsearch credentials are not set."""

    backend = "local"

    def __init__(self, path=DB_PATH):
        ensure_dirs()
        self.path = path
        self._lock = threading.Lock()
        self.db = self._load()

    def _load(self):
        if not self.path.exists():
            return _empty()
        data = json.loads(self.path.read_text())
        for key, value in _empty().items():
            data.setdefault(key, value)
        return data

    def _save(self):
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.db, separators=(",", ":")))
        tmp.replace(self.path)

    def counts(self):
        cases = self.db["cases"].values()
        return {
            "cases": len(self.db["cases"]),
            "open_cases": sum(1 for case in cases if case.get("volunteer_status") == "open"),
            "businesses": len(self.db["businesses"]),
            "shops": len(self.db["shops"]),
            "volunteers": len(self.db["volunteers"]),
            "completions": len(self.db["completions"]),
        }

    def replace_cases(self, docs):
        with self._lock:
            solved = set(self.db["completions"])
            cases = {}
            for doc in docs:
                case = dict(doc)
                case_id = case["service_request_id"]
                case["volunteer_status"] = "solved" if case_id in solved else "open"
                cases[case_id] = case
            self.db["cases"] = cases
            self._save()
            return len(cases)

    def replace_businesses(self, docs):
        with self._lock:
            self.db["businesses"] = {doc["business_id"]: dict(doc) for doc in docs}
            self._save()
            return len(self.db["businesses"])

    def neighborhoods(self):
        counts = Counter(
            case["neighborhood"]
            for case in self.db["cases"].values()
            if case.get("volunteer_status") == "open" and case.get("neighborhood")
        )
        rows = [{"name": name, "open_cases": count} for name, count in counts.items()]
        rows.sort(key=lambda row: (-row["open_cases"], row["name"]))
        return rows

    def cases_in_neighborhood(self, neighborhood, limit=200):
        rows = [
            case for case in self.db["cases"].values()
            if case.get("volunteer_status") == "open" and case.get("neighborhood") == neighborhood
        ]
        rows.sort(key=lambda case: case.get("requested_at") or "", reverse=True)
        return rows[:limit]

    def get_case(self, case_id):
        return self.db["cases"].get(case_id)

    def nearby_businesses(self, lat, lon, meters, limit, query=None):
        found = []
        for business in self.db["businesses"].values():
            point = business.get("location") or {}
            if "lat" not in point:
                continue
            distance = haversine_m(lat, lon, point["lat"], point["lon"])
            if distance <= meters:
                found.append({**business, "distance_m": round(distance)})
        found.sort(key=lambda row: row["distance_m"])
        return found[:limit]

    def nearby_shops(self, lat, lon, meters):
        found = []
        for shop in self.db["shops"].values():
            point = shop.get("location") or {}
            if "lat" not in point:
                continue
            distance = haversine_m(lat, lon, point["lat"], point["lon"])
            if distance <= meters:
                found.append({**shop, "distance_m": round(distance)})
        found.sort(key=lambda row: row["distance_m"])
        return found

    def match_business(self, address, name=None):
        key = address_key(address)
        if not key:
            return None
        hits = [
            business for business in self.db["businesses"].values()
            if business.get("address_key") == key and business.get("location")
        ]
        if not hits:
            return None
        if name:
            needle = name.strip().lower()
            named = [
                business for business in hits
                if needle and (needle in business["name"].lower() or business["name"].lower() in needle)
            ]
            if named:
                return named[0]
        return hits[0]

    def nearest_neighborhood(self, lat, lon):
        nearest = self.nearby_businesses(lat, lon, 1500, 1)
        if nearest and nearest[0].get("neighborhood"):
            return nearest[0]["neighborhood"]
        best = None
        best_distance = None
        for case in self.db["cases"].values():
            point = case.get("location") or {}
            if "lat" not in point or not case.get("neighborhood"):
                continue
            distance = haversine_m(lat, lon, point["lat"], point["lon"])
            if best_distance is None or distance < best_distance:
                best = case["neighborhood"]
                best_distance = distance
        return best

    def upsert_volunteer(self, email, display_name, neighborhood):
        with self._lock:
            current = self.db["volunteers"].get(email, {})
            self.db["volunteers"][email] = {
                "email": email,
                "display_name": display_name,
                "neighborhood": neighborhood or current.get("neighborhood") or "",
                "created_at": current.get("created_at") or _now(),
            }
            self._save()
            return self.db["volunteers"][email]

    def upsert_shop(self, doc):
        with self._lock:
            current = self.db["shops"].get(doc["email"], {})
            saved = {**doc, "created_at": current.get("created_at") or _now()}
            self.db["shops"][doc["email"]] = saved
            self._save()
            return saved

    def list_shops(self):
        rows = list(self.db["shops"].values())
        rows.sort(key=lambda shop: (shop.get("neighborhood") or "", shop.get("name") or ""))
        return rows

    def complete_case(self, case_id, email, display_name, before_url, after_url):
        with self._lock:
            case = self.db["cases"].get(case_id)
            if not case:
                raise CaseNotFound(case_id)
            if case_id in self.db["completions"] or case.get("volunteer_status") == "solved":
                raise AlreadySolved(case_id)
            completion = {
                "service_request_id": case_id,
                "email": email,
                "display_name": display_name,
                "neighborhood": case.get("neighborhood") or "",
                "address": case.get("address") or "",
                "detail_label": case.get("detail_label") or "",
                "before_url": before_url,
                "after_url": after_url,
                "completed_at": _now(),
                "notified_shops": [],
                "location": case.get("location"),
            }
            self.db["completions"][case_id] = completion
            case["volunteer_status"] = "solved"
            self._save()
            return completion

    def mark_notified(self, case_id, shop_emails):
        with self._lock:
            completion = self.db["completions"].get(case_id)
            if not completion:
                return
            completion["notified_shops"] = shop_emails
            self._save()

    def leaderboard(self, limit=20, email=None):
        counts = Counter()
        first_at = {}
        for completion in self.db["completions"].values():
            who = completion["email"]
            counts[who] += 1
            stamp = completion.get("completed_at") or ""
            if who not in first_at or stamp < first_at[who]:
                first_at[who] = stamp
        ranked = sorted(counts, key=lambda who: (-counts[who], first_at[who]))
        rows = []
        you = None
        for index, who in enumerate(ranked, start=1):
            volunteer = self.db["volunteers"].get(who, {})
            row = {
                "rank": index,
                "display_name": volunteer.get("display_name") or who.split("@")[0],
                "neighborhood": volunteer.get("neighborhood") or "",
                "solved": counts[who],
            }
            if email and who == email:
                row["you"] = True
                you = row
            if index <= limit:
                rows.append(row)
        return {"rows": rows, "you": you}
