import os
from datetime import datetime, timezone

from elasticsearch import ConflictError, Elasticsearch, NotFoundError, helpers

from catalog import INFERENCE_ID, business_about
from geo import address_key, haversine_m
from store import AlreadySolved, CaseNotFound

CASES = "block_clean_cases"
BUSINESSES = "block_clean_businesses"
VOLUNTEERS = "block_clean_volunteers"
SHOPS = "block_clean_shops"
COMPLETIONS = "block_clean_completions"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _point_mapping():
    return {"type": "geo_point"}


CASE_MAPPINGS = {"properties": {
    "service_request_id": {"type": "keyword"},
    "requested_at": {"type": "date"},
    "service_details": {"type": "keyword"},
    "detail_label": {"type": "keyword"},
    "address": {"type": "text"},
    "neighborhood": {"type": "keyword"},
    "photo_url": {"type": "keyword"},
    "location": _point_mapping(),
    "volunteer_status": {"type": "keyword"},
}}

BUSINESS_MAPPINGS = {"properties": {
    "business_id": {"type": "keyword"},
    "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
    "address": {"type": "text"},
    "address_key": {"type": "keyword"},
    "neighborhood": {"type": "keyword"},
    "sector": {"type": "keyword"},
    "about": {"type": "semantic_text", "inference_id": INFERENCE_ID},
    "location": _point_mapping(),
}}

VOLUNTEER_MAPPINGS = {"properties": {
    "email": {"type": "keyword"},
    "display_name": {"type": "keyword"},
    "neighborhood": {"type": "keyword"},
    "created_at": {"type": "date"},
}}

SHOP_MAPPINGS = {"properties": {
    "email": {"type": "keyword"},
    "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
    "address": {"type": "text"},
    "neighborhood": {"type": "keyword"},
    "location": _point_mapping(),
    "source": {"type": "keyword"},
    "created_at": {"type": "date"},
}}

COMPLETION_MAPPINGS = {"properties": {
    "service_request_id": {"type": "keyword"},
    "email": {"type": "keyword"},
    "display_name": {"type": "keyword"},
    "neighborhood": {"type": "keyword"},
    "address": {"type": "text"},
    "detail_label": {"type": "keyword"},
    "before_url": {"type": "keyword"},
    "after_url": {"type": "keyword"},
    "completed_at": {"type": "date"},
    "notified_shops": {"type": "keyword"},
    "location": _point_mapping(),
}}


class ElasticStore:
    """Same operations as the JSON store, backed by Elasticsearch geo queries."""

    backend = "elasticsearch"

    def __init__(self):
        self.es = Elasticsearch(
            os.environ["ELASTIC_ENDPOINT"],
            api_key=os.environ["ELASTIC_API_KEY"],
            request_timeout=180,
        )
        self.es.info()
        self._ensure(VOLUNTEERS, VOLUNTEER_MAPPINGS)
        self._ensure(SHOPS, SHOP_MAPPINGS)
        self._ensure(COMPLETIONS, COMPLETION_MAPPINGS)

    def _ensure(self, index, mappings, recreate=False):
        exists = bool(self.es.indices.exists(index=index))
        if recreate and exists:
            self.es.indices.delete(index=index)
            exists = False
        if not exists:
            self.es.indices.create(index=index, mappings=mappings)

    def _search(self, index, query, size=20, sort=None, source=None):
        if not self.es.indices.exists(index=index):
            return []
        response = self.es.search(index=index, query=query, size=size, sort=sort, source=source)
        return [hit["_source"] for hit in response["hits"]["hits"]]

    def counts(self):
        def total(index, query=None):
            if not self.es.indices.exists(index=index):
                return 0
            kwargs = {"index": index, "size": 0, "track_total_hits": True}
            if query:
                kwargs["query"] = query
            response = self.es.search(**kwargs)
            return response["hits"]["total"]["value"]

        return {
            "cases": total(CASES),
            "open_cases": total(CASES, {"term": {"volunteer_status": "open"}}),
            "businesses": total(BUSINESSES),
            "shops": total(SHOPS),
            "volunteers": total(VOLUNTEERS),
            "completions": total(COMPLETIONS),
        }

    def replace_cases(self, docs):
        solved = set()
        if self.es.indices.exists(index=COMPLETIONS):
            for hit in helpers.scan(
                self.es,
                index=COMPLETIONS,
                query={"query": {"match_all": {}}, "_source": ["service_request_id"]},
            ):
                solved.add(hit["_source"]["service_request_id"])
        self._ensure(CASES, CASE_MAPPINGS, recreate=True)
        actions = []
        for doc in docs:
            case = dict(doc)
            case_id = case["service_request_id"]
            case["volunteer_status"] = "solved" if case_id in solved else "open"
            actions.append({"_index": CASES, "_id": case_id, "_source": case})
        if actions:
            helpers.bulk(self.es, actions)
        self.es.indices.refresh(index=CASES)
        return len(actions)

    def replace_businesses(self, docs):
        self._ensure_embeddings()
        self._ensure(BUSINESSES, BUSINESS_MAPPINGS, recreate=True)
        actions = []
        for doc in docs:
            source = dict(doc)
            if not source.get("about"):
                source["about"] = business_about(
                    source.get("name") or "",
                    source.get("sector") or "",
                    source.get("address") or "",
                    source.get("neighborhood") or "",
                )
            actions.append({"_index": BUSINESSES, "_id": source["business_id"], "_source": source})
        # Semantic fields call Mistral while indexing, so keep chunks small enough to stay
        # under the embedding endpoint's rate limit.
        step = 80
        for start in range(0, len(actions), step):
            helpers.bulk(self.es, actions[start:start + step])
            print(f"  embedded {min(start + step, len(actions))}/{len(actions)}", flush=True)
        self.es.indices.refresh(index=BUSINESSES)
        return len(actions)

    def _ensure_embeddings(self):
        try:
            self.es.perform_request("GET", f"/_inference/text_embedding/{INFERENCE_ID}")
            return
        except NotFoundError:
            pass
        api_key = os.getenv("MISTRAL_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "The Mistral embedding endpoint is missing. Set MISTRAL_API_KEY and ingest again."
            )
        self.es.perform_request(
            "PUT",
            f"/_inference/text_embedding/{INFERENCE_ID}",
            body={
                "service": "mistral",
                "service_settings": {"api_key": api_key, "model": "mistral-embed"},
            },
        )

    def neighborhoods(self):
        if not self.es.indices.exists(index=CASES):
            return []
        response = self.es.search(index=CASES, size=0, query={"term": {"volunteer_status": "open"}}, aggs={
            "by_neighborhood": {"terms": {"field": "neighborhood", "size": 60}},
        })
        rows = [
            {"name": bucket["key"], "open_cases": bucket["doc_count"]}
            for bucket in response["aggregations"]["by_neighborhood"]["buckets"]
        ]
        rows.sort(key=lambda row: (-row["open_cases"], row["name"]))
        return rows

    def cases_in_neighborhood(self, neighborhood, limit=200):
        return self._search(
            CASES,
            {"bool": {"filter": [
                {"term": {"neighborhood": neighborhood}},
                {"term": {"volunteer_status": "open"}},
            ]}},
            size=limit,
            sort=[{"requested_at": {"order": "desc"}}],
        )

    def get_case(self, case_id):
        try:
            return self.es.get(index=CASES, id=case_id)["_source"]
        except NotFoundError:
            return None

    def nearby_businesses(self, lat, lon, meters, limit, query=None):
        geo = {"geo_distance": {
            "distance": f"{meters}m",
            "location": {"lat": lat, "lon": lon},
        }}
        if query:
            try:
                rows = self._search(
                    BUSINESSES,
                    {"bool": {
                        "must": {"semantic": {"field": "about", "query": query}},
                        "filter": geo,
                    }},
                    size=limit,
                    source={"excludes": ["about"]},
                )
                return [_with_distance(row, lat, lon) for row in rows]
            except Exception as exc:
                print(f"semantic search failed, using distance: {exc}", flush=True)
        rows = self._search(
            BUSINESSES,
            {"bool": {"filter": geo}},
            size=limit,
            sort=[{"_geo_distance": {
                "location": {"lat": lat, "lon": lon},
                "order": "asc",
                "unit": "m",
            }}],
            source={"excludes": ["about"]},
        )
        return [_with_distance(row, lat, lon) for row in rows]

    def nearby_shops(self, lat, lon, meters):
        rows = self._search(
            SHOPS,
            {"bool": {"filter": {"geo_distance": {
                "distance": f"{meters}m",
                "location": {"lat": lat, "lon": lon},
            }}}},
            size=50,
            sort=[{"_geo_distance": {
                "location": {"lat": lat, "lon": lon},
                "order": "asc",
                "unit": "m",
            }}],
        )
        return [_with_distance(row, lat, lon) for row in rows]

    def match_business(self, address, name=None):
        key = address_key(address)
        if not key:
            return None
        hits = self._search(BUSINESSES, {"term": {"address_key": key}}, size=20)
        hits = [hit for hit in hits if hit.get("location")]
        if not hits:
            return None
        if name:
            needle = name.strip().lower()
            named = [
                hit for hit in hits
                if needle and (needle in hit["name"].lower() or hit["name"].lower() in needle)
            ]
            if named:
                return named[0]
        return hits[0]

    def nearest_neighborhood(self, lat, lon):
        nearest = self.nearby_businesses(lat, lon, 1500, 1)
        if nearest and nearest[0].get("neighborhood"):
            return nearest[0]["neighborhood"]
        cases = self._search(
            CASES,
            {"bool": {"filter": {"geo_distance": {
                "distance": "2000m",
                "location": {"lat": lat, "lon": lon},
            }}}},
            size=1,
            sort=[{"_geo_distance": {
                "location": {"lat": lat, "lon": lon},
                "order": "asc",
                "unit": "m",
            }}],
        )
        if cases:
            return cases[0].get("neighborhood")
        return None

    def upsert_volunteer(self, email, display_name, neighborhood):
        current = {}
        try:
            current = self.es.get(index=VOLUNTEERS, id=email)["_source"]
        except NotFoundError:
            current = {}
        doc = {
            "email": email,
            "display_name": display_name,
            "neighborhood": neighborhood or current.get("neighborhood") or "",
            "created_at": current.get("created_at") or _now(),
        }
        self.es.index(index=VOLUNTEERS, id=email, document=doc, refresh="wait_for")
        return doc

    def upsert_shop(self, doc):
        current = {}
        try:
            current = self.es.get(index=SHOPS, id=doc["email"])["_source"]
        except NotFoundError:
            current = {}
        saved = {**doc, "created_at": current.get("created_at") or _now()}
        self.es.index(index=SHOPS, id=doc["email"], document=saved, refresh="wait_for")
        return saved

    def list_shops(self):
        return self._search(SHOPS, {"match_all": {}}, size=200, sort=["neighborhood", "name.keyword"])

    def complete_case(self, case_id, email, display_name, before_url, after_url):
        case = self.get_case(case_id)
        if not case:
            raise CaseNotFound(case_id)
        if case.get("volunteer_status") == "solved":
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
        try:
            self.es.index(
                index=COMPLETIONS,
                id=case_id,
                document=completion,
                op_type="create",
                refresh="wait_for",
            )
        except ConflictError as exc:
            raise AlreadySolved(case_id) from exc
        self.es.update(
            index=CASES,
            id=case_id,
            doc={"volunteer_status": "solved"},
            refresh="wait_for",
        )
        return completion

    def mark_notified(self, case_id, shop_emails):
        self.es.update(
            index=COMPLETIONS,
            id=case_id,
            doc={"notified_shops": shop_emails},
            refresh="wait_for",
        )

    def leaderboard(self, limit=20, email=None):
        if not self.es.indices.exists(index=COMPLETIONS):
            return {"rows": [], "you": None}
        response = self.es.search(index=COMPLETIONS, size=0, aggs={
            "by_email": {
                "terms": {"field": "email", "size": 500, "order": {"_count": "desc"}},
                "aggs": {"first_at": {"min": {"field": "completed_at"}}},
            },
        })
        buckets = response["aggregations"]["by_email"]["buckets"]
        buckets.sort(key=lambda bucket: (-bucket["doc_count"], bucket["first_at"]["value"] or 0))
        emails = [bucket["key"] for bucket in buckets]
        volunteers = {}
        if emails:
            found = self.es.mget(index=VOLUNTEERS, ids=emails)
            for doc in found["docs"]:
                if doc.get("found"):
                    volunteers[doc["_id"]] = doc["_source"]
        rows = []
        you = None
        for index, bucket in enumerate(buckets, start=1):
            who = bucket["key"]
            volunteer = volunteers.get(who, {})
            row = {
                "rank": index,
                "display_name": volunteer.get("display_name") or who.split("@")[0],
                "neighborhood": volunteer.get("neighborhood") or "",
                "solved": bucket["doc_count"],
            }
            if email and who == email:
                row["you"] = True
                you = row
            if index <= limit:
                rows.append(row)
        return {"rows": rows, "you": you}


def _with_distance(row, lat, lon):
    point = row.get("location") or {}
    distance = haversine_m(lat, lon, point["lat"], point["lon"])
    return {**row, "distance_m": round(distance)}
