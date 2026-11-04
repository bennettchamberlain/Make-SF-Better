"""Ask Mistral which 311 categories a neighbor can finish.

The model sees each service name, subtype, and detail. A short hazard list
still overrides a yes: needles, human waste, and encampments stay with the city
even if the model says otherwise.
"""

import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

from paths import DATA, ROOT, ensure_dirs

MODEL = "mistral-small-latest"
PROMPT_REV = "v2"
CACHE_PATH = DATA / "job_fit.json"
API_URL = "https://api.mistral.ai/v1/chat/completions"
BATCH = 20

# Detail codes the model sometimes marks as a hand job even though they are not.
# The match is on the city's category text, after the model has answered.
CREW_TOKENS = (
    "liner_issue",
    "remove_garbage_can",
    "toters_left_out",
    "abandoned_toter",
    "auto_accident",
    "shrubbery",
    "pruning",
    "backfill",
    "empty_tree_basin",
    "horticultural",
    "on_ground",
    "port_a_potty",
    "inspection",
)

# These stay with the city no matter what the model says.
HAZARD_RE = re.compile(
    r"needle|syringe|sharps|human_waste|urine|feces|biohazard|"
    r"encampment|dead_animal|hazardous|bodily_fluid|\bblood\b",
    re.I,
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["jobs"],
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "neighbor_ok", "label", "why"],
                "properties": {
                    "id": {"type": "integer"},
                    "neighbor_ok": {"type": "boolean"},
                    "label": {"type": "string"},
                    "why": {"type": "string"},
                },
            },
        }
    },
}

SYSTEM = """You decide which San Francisco 311 categories a regular neighbor can finish.

The neighbor is one adult on foot, in one visit. They have gloves, bags, a broom, a dustpan, a scraper, and a litter picker. They are not a city crew. No truck, no ladder, no power tools, and no entering private property.

Say yes only for work they can finish by hand in public space:
- picking up loose litter, bagged trash, glass, or the mess after an event
- bagging overflow from a public trash can, or standing a tipped public can back up
- wiping graffiti or stickers off a public pole, meter, mailbox, hydrant, sidewalk, or signal box
- pulling illegal posters off public poles and signs
- pulling weeds in a public tree basin or park edge

Say no for everything else, including:
- mattresses, appliances, furniture, shopping carts, construction plates, benches, or anything that needs a truck or two people
- moving scooters, bikes, or cars
- repairing, replacing, installing, or removing city equipment, including trash cans, signs, racks, and lights
- damaged, bent, or missing traffic signs (cleaning a sticker is not the same as taking the sign down)
- trees, limbs, pavement, curbs, sewers, and anything electrical
- human or animal waste, needles, blood, chemicals, spills, and electronics
- encampments or anything involving people living outside
- private buildings
- parking, towing, noise, feedback, lost and found, volunteer signups, and requests whose only action is filing a report

label: a short name a neighbor would understand, under 60 characters.
why: one sentence.
"""


def category_key(name, subtype, details):
    return "\t".join([(name or "").strip(), (subtype or "").strip(), (details or "").strip()])


def _hazard_text(name, subtype, details):
    return " ".join(part for part in (name, subtype, details) if part)


def safety_reason(name, subtype, details):
    """A neighbor-sized yes the model should not have given."""
    blob = _hazard_text(name, subtype, details).lower()
    if (name or "") == "Blocked Street and Sidewalk":
        return "A blocked sidewalk can be a vehicle, a potty, or a rack. Those stay with the city."
    if (name or "") == "Shared Spaces Request" and "graffiti" not in blob:
        return "An unspecified obstruction can be heavy or structural. That stays with the city."
    if any(token in blob for token in CREW_TOKENS):
        return "This needs a city crew or a truck, or it is only a report."
    return ""


def load_cache():
    if not CACHE_PATH.exists():
        return {}
    payload = json.loads(CACHE_PATH.read_text())
    if payload.get("model") != MODEL or payload.get("prompt") != PROMPT_REV:
        return {}
    return payload.get("categories") or {}


def save_cache(categories):
    ensure_dirs()
    CACHE_PATH.write_text(json.dumps({
        "model": MODEL,
        "prompt": PROMPT_REV,
        "categories": categories,
    }, indent=2))


def _client_key():
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")
    key = os.getenv("MISTRAL_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is missing")
    return key


def _ask(api_key, batch):
    numbered = []
    for item in batch:
        numbered.append(
            f"{item['id']}. service_name={item['service_name'] or 'none'}; "
            f"service_subtype={item['subtype'] or 'none'}; "
            f"service_details={item['details'] or 'none'}"
        )
    response = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Judge each category.\n" + "\n".join(numbered)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "neighbor_jobs", "strict": True, "schema": SCHEMA},
            },
        },
        timeout=120,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return {row["id"]: row for row in parsed["jobs"]}


def _decide(item, row):
    text = _hazard_text(item["service_name"], item["subtype"], item["details"])
    label = (row.get("label") or "").strip()[:80] or "311 request"
    why = (row.get("why") or "").strip()
    ok = bool(row.get("neighbor_ok"))
    veto = False
    if ok and HAZARD_RE.search(text):
        ok = False
        veto = True
        why = "Left with the city. This category can involve a hazard or people living outside."
    crew = safety_reason(item["service_name"], item["subtype"], item["details"])
    if ok and crew:
        ok = False
        veto = True
        why = crew
    if ok and label.lower().startswith("remove defaced"):
        label = "Wipe graffiti off a public sign"
    return {
        "neighbor_ok": ok,
        "label": label,
        "why": why,
        "veto": veto,
        "service_name": item["service_name"],
        "service_subtype": item["subtype"],
        "service_details": item["details"],
    }


def _rescore(cache):
    changed = False
    for key, row in cache.items():
        name, subtype, details = (key.split("\t") + ["", "", ""])[:3]
        reason = safety_reason(name, subtype, details)
        if reason and row.get("neighbor_ok"):
            row["neighbor_ok"] = False
            row["veto"] = True
            row["why"] = reason
            changed = True
        elif row.get("neighbor_ok") and str(row.get("label") or "").lower().startswith("remove defaced"):
            row["label"] = "Wipe graffiti off a public sign"
            changed = True
    return changed


def judge_categories(groups):
    """groups: iterable of dicts with service_name, service_subtype, service_details.

    Returns a dict keyed by category_key.
    """
    cache = load_cache()
    if _rescore(cache):
        save_cache(cache)
    pending = []
    for group in groups:
        name = group.get("service_name") or ""
        subtype = group.get("service_subtype") or ""
        details = group.get("service_details") or ""
        key = category_key(name, subtype, details)
        if key in cache:
            continue
        pending.append({
            "key": key,
            "service_name": name,
            "subtype": subtype,
            "details": details,
        })

    if not pending:
        return cache

    api_key = _client_key()
    batches = []
    for start in range(0, len(pending), BATCH):
        chunk = pending[start:start + BATCH]
        for offset, item in enumerate(chunk):
            item["id"] = offset
        batches.append(chunk)

    print(f"Asking {MODEL} about {len(pending)} categories in {len(batches)} batches...", flush=True)

    def run(chunk):
        last_error = None
        for _ in range(3):
            try:
                return chunk, _ask(api_key, chunk)
            except (requests.RequestException, KeyError, json.JSONDecodeError, ValueError) as error:
                last_error = error
        raise RuntimeError(f"Mistral batch failed: {last_error}")

    done = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run, chunk) for chunk in batches]
        for future in as_completed(futures):
            chunk, rows = future.result()
            with lock:
                for item in chunk:
                    row = rows.get(item["id"]) or {
                        "neighbor_ok": False,
                        "label": "311 request",
                        "why": "Mistral did not return a decision for this category.",
                    }
                    cache[item["key"]] = _decide(item, row)
                done += len(chunk)
                save_cache(cache)
                print(f"  judged {done}/{len(pending)}", flush=True)
    return cache
