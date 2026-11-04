# Block Clean

A small platform for San Francisco 311 **street and sidewalk cleaning** jobs a neighbor can actually finish: loose trash, bagged garbage, broken glass, an overflowing city can, or the mess after an event.

People enter an email, pick a neighborhood, and get the open cases there. Logging a before photo and an after photo puts them on a leaderboard. Shops that have joined, within 400 meters, get an email with the after photo. Reply-to is the neighbor, so the shop can offer a hand.

Official 311 cases are not closed by this app. Human waste, needles, spills, furniture, and appliances are left out on purpose.

## Run

```bash
cd block_clean
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ingest.py
python app.py
```

Open http://127.0.0.1:8000

`ingest.py` reads DataSF. Case and business coordinates come from the city datasets (311 `lat`/`long`, business `location`). A shop that signs up is placed by matching that address to the business registry, then by OpenStreetMap if it is not in the registry.

Copy `.env.example` to `.env` to use Elasticsearch, Resend, or SMTP. With those blank, cases live in `data/db.json` and shop notes are appended to `data/outbox.jsonl`.

On Elasticsearch, each business has an `about` field of type `semantic_text`, embedded with the `mistral-embeddings` endpoint (`mistral-embed`). Opening a case searches that field and keeps only businesses within 400 meters, so the list is both relevant to the cleanup and actually nearby.

## What gets stored

| Index or file | Contents |
|---|---|
| Cases | Open street-cleaning requests from the last 180 days, volunteer-safe details only, with a `geo_point` |
| Businesses | Open retail and food locations in San Francisco, with a `geo_point` |
| Volunteers | Email, display name, neighborhood |
| Shops | Shops that joined, geocoded, so they can be emailed |
| Completions | Before and after photo URLs. The leaderboard counts these. |
