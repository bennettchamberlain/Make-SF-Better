# Hack Night Open Challenge

**Build something that makes life in San Francisco better for someone who lives here**, using tech from **Elasticsearch** and **Mistral**. This page has project ideas for each theme and a ready-to-run ingest example you can point at *any* dataset on [DataSF](https://data.sf.gov/).

> No polished UI required: a notebook, Dev Tools, a script, or Kibana is a perfectly good demo. We care about who it helps and how you combine Elastic and Mistral, not how it looks. Agent frameworks (Elastic Agent Builder, Mistral's Agents API) are optional, not requirements.

## Example Projects

| Project | Who it helps | Dataset | Elastic + Mistral features |
|---|---|---|---|
| **Car-Free Weekend** | Visitors and residents without a car | [Muni schedule](muni_schedule.ipynb) + [parks & art](sf_parks_and_public_art.ipynb) | A **Mistral agent** with geo-search tools: "How do I get to Lands End by transit, and what should I see on the way?" |
| **Plain-English Delays** | Commuters | [BART real-time](bart_realtime.ipynb) | Live arrivals and alerts in Elasticsearch; a Mistral model turns them into one sentence in the rider's language, read aloud with **Voxtral TTS**. |
| **Shop Translator** | Small-business owners | [Business locations](sf_business_locations.ipynb) | Mistral translates a shop's menu or notice into Spanish, Chinese, Tagalog, or Vietnamese; Elasticsearch finds the neighbors who'd want to see it. |
| **Inspection Prep** | Restaurant owners | [Health inspections](sf_health_inspections.ipynb) | Semantic search over past violations nearby with **Mistral embeddings**, then a Mistral checklist of what to fix before re-inspection. |
| **Where Should I Eat?** | Diners | [Health inspections](sf_health_inspections.ipynb) + [businesses](sf_business_locations.ipynb) | RAG chatbot combining inspection results with how long a place has been open, for a trustworthy, local recommendation. |
| **Story of My Block** | Curious neighbors | [Landmarks](sf_landmarks.ipynb) | **Mistral OCR** reads decades-old designation reports; geo search finds the landmarks closest to you; Mistral tells their story. |
| **Tree Doctor** | Neighbors and Public Works | [Street trees](sf_street_trees.ipynb) + [311 cases](sf_311_cases.ipynb) | Join tree-maintenance requests with the tree inventory; Mistral vision checks a photo of a damaged tree. |
| **What's On For Kids** | Parents | [Our415 events](sf_community_events.ipynb) | A Mistral agent that filters by age, day, price, and distance, answering in the parent's language. |
| **311, Simplified** | Anyone reporting a problem | [311 cases](sf_311_cases.ipynb) | Describe a problem in your own words (or by voice with **Voxtral**); **structured outputs** pick the right request type and Elasticsearch finds similar open cases nearby. |
| **Neighborhood Pulse** | Residents and supervisors | [311 cases](sf_311_cases.ipynb) | Aggregations by neighborhood and week, summarized by a Mistral chat model: "What is the Tenderloin asking for this month?" |
| **Pocket Naturalist** | Families, hikers | [City Nature Challenge](sf_city_nature_challenge.ipynb) | Identify a species from a photo with **Mistral vision**, compare it to the crowd ID, then map where else in SF it's been seen. |
| **City Concierge** | Anyone | any | A **Mistral agent** (Agents API) with an Elasticsearch search function as one of its tools, plus built-in web search for anything the index doesn't cover. |
| **Chat With the City** | Anyone | any | Connect **Vibe Work** or the **Vibe CLI** to Elastic Agent Builder's MCP server, and query your SF indices in plain language. |

> **Two ways to use Mistral.** Call Mistral directly with the `mistralai` SDK or API: chat and reasoning, agents, function calling, OCR, vision, Voxtral audio, moderation, and more. Then index whatever it produces into Elasticsearch. Or register Mistral models as **Elasticsearch inference endpoints**, so `semantic_text`, Agent Builder, and your own queries can use them. Mix both freely. See the [Mistral guide](mistral_guide.md) for the direct route and [Using Mistral in Elasticsearch](using_mistral_in_elasticsearch.md) for the inference-endpoint route.

## Stretch Ideas

- **Hybrid search** over 311 notes or event descriptions: combine keyword and Mistral-embedding semantic search, then filter by neighborhood and distance.
- **Cross-dataset mashup:** every notebook builds a `geo_point`. Find the free events within a block of a Muni Metro stop, or the parks with the most graffiti reports.
- **A reasoning agent** on `mistral-large-4` that plans multi-step answers ("Which neighborhoods have the fewest street trees *and* the most heat-related 311 calls?").
- **Multilingual by default:** answer in whatever language the question was asked in.
- **An MCP-connected agent** you drive from Claude, Mistral Vibe, or your own app via Agent Builder's MCP server.
- **OCR → structured data:** use Mistral Document AI to pull architect, year built, and original use out of every landmark report, then aggregate on them.
- **Then vs. now:** pair a landmark's OCR'd history with today's businesses and 311 reports on the same block.

---

## Example: Ingesting any DataSF dataset

Almost every dataset on [DataSF](https://data.sf.gov/) is served by **Socrata**, which gives you a direct JSON API: no key, no download, no CSV wrangling. The pattern below works for any of them; just change the dataset id.

Run it in a Jupyter/Colab notebook or as a plain Python script. If you'd rather not script it, you can also use the **Upload file** option in the Elasticsearch UI with a downloaded CSV.

### 1. Install dependencies

```bash
pip install elasticsearch requests
```

### 2. Find the dataset id

On any DataSF page, the id is the code at the end of the URL (e.g. Film Locations in San Francisco is `yitu-d5am`). The JSON API for a dataset is:

```
https://data.sf.gov/resource/<dataset-id>.json
```

You can append [Socrata query params](https://dev.socrata.com/docs/queries/): `$limit`, `$offset`, `$where`, `$order`, `$select`.

### 3. Fetch the data

```python
import requests

DATASET_ID = 'yitu-d5am'  # Film Locations in San Francisco
url = f'https://data.sf.gov/resource/{DATASET_ID}.json'

resp = requests.get(url, params={'$limit': 5000}, timeout=60)
resp.raise_for_status()
rows = resp.json()

print(f'{len(rows)} rows')
print('Columns:', list(rows[0].keys()))
```

### 4. Connect to Elastic Serverless

```python
from elasticsearch import Elasticsearch, helpers

# 🔑 Fill these in - Elastic Cloud Console → Your Project → Connection Details
ELASTIC_ENDPOINT = 'https://your-project.es.region.aws.elastic.cloud'
ELASTIC_API_KEY  = 'your-elastic-api-key'

es = Elasticsearch(ELASTIC_ENDPOINT, api_key=ELASTIC_API_KEY)
print(f'✅ Connected to Elasticsearch {es.info()["version"]["number"]}')
```

### 5. Bulk-index into Elasticsearch

Let Elasticsearch infer field types (dynamic mapping); that's fine for exploration. Define an explicit mapping later if you want `keyword` fields for exact filtering, `geo_point` for maps, or `semantic_text` for Mistral-powered semantic search.

```python
INDEX = 'sf_film_locations'

# Recreate the index each run so there are no duplicates
if es.indices.exists(index=INDEX):
    es.indices.delete(index=INDEX)
es.indices.create(index=INDEX)

actions = [{'_index': INDEX, '_source': r} for r in rows]
success, errors = helpers.bulk(es, actions, raise_on_error=False)
es.indices.refresh(index=INDEX)
print(f'✅ Indexed {success} documents ({len(errors)} errors)')
```

### 6. Verify

```python
resp = es.search(index=INDEX, size=3)
print(f"Total documents: {resp['hits']['total']['value']}\n")
for hit in resp['hits']['hits']:
    print(hit['_source'])
```

That's it: you now have an index you can search, aggregate, or layer AI on top of. From here, add an explicit mapping, wire up a `semantic_text` field with a **Mistral embedding endpoint** for meaning-based search ([Using Mistral in Elasticsearch](using_mistral_in_elasticsearch.md)), or call **Mistral** directly with the `mistralai` SDK: a chat model for a RAG answer, an agent that queries this index as a tool, translation, OCR, or Voxtral audio ([Mistral guide](mistral_guide.md)).

> **Big datasets:** Socrata returns pages. For anything over a few thousand rows, loop with `$limit` and `$offset` (the notebooks in this repo have a `fetch_socrata` helper that does this).

---

## Add Mistral semantic search in 3 steps

Turn any text field into meaning-aware search:

```
# 1. Create a Mistral embedding endpoint (once)
PUT _inference/text_embedding/mistral-embeddings
{ "service": "mistral", "service_settings": { "api_key": "<MISTRAL_API_KEY>", "model": "mistral-embed" } }

# 2. Create an index with a semantic_text field pointed at it
PUT sf_film_locations_semantic
{ "mappings": { "properties": { "fun_facts": { "type": "semantic_text", "inference_id": "mistral-embeddings" } } } }

# 3. Index docs normally, then search by meaning
GET sf_film_locations_semantic/_search
{ "query": { "semantic": { "field": "fun_facts", "query": "a car chase down a steep hill" } } }
```

See [using_mistral_in_elasticsearch.md](using_mistral_in_elasticsearch.md) for details, raw-vector kNN, and the full Mistral model lineup.
