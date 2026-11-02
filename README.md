# Elastic × Mistral SF Hack Night

**What's one thing you'd make better about life in San Francisco?**

Welcome to the **Elastic × Mistral SF Hack Night**, the evening before [Elastic{ON} SF](https://www.elastic.co/events/elasticon/san-francisco-ai). Pick something you care about, like your commute, your neighborhood, or your favorite small business, and turn an idea into a working prototype with **Elastic** and **Mistral AI**.

**The challenge: build something that makes life in SF better for someone who lives here.**

A few places to start:

- **Getting around:** make transit updates easier to understand, or help people explore the city without a car.
- **Neighborhood businesses:** build tools that help local shops reach customers, translate information, or save time.
- **Public spaces:** help people discover parks, recreation facilities, public art, and neighborhood history.
- **Community:** connect neighbors with volunteer opportunities, local gatherings, or ways to help.
- **City information:** make public data and city services easier to navigate.

Start with [SF's open datasets](https://data.sf.gov/) (311 reports, business locations, parks, street trees, public art, and more; see the table below), or bring a problem you've experienced firsthand.

**Date:** November 3, 2026
**Location:** Elastic SF office, 33 New Montgomery St, 9th Floor, San Francisco, CA 94105
**Hack time:** ~2 hours

> **This is a hack about ideas, not interfaces.** We're judging who your project helps and how well you combine **Elastic** and **Mistral tech**, not how it looks. You do **not** need a polished front-end. A notebook, a Dev Tools session, a terminal script, or Kibana itself is a perfectly good way to demo. Spend your two hours on the problem and the data.

---

## Schedule

**5:00 PM – Doors open:**
Grab food and drinks, meet other attendees, and get settled.

**5:15 PM – Kickoff and demo:**
We'll introduce the challenge, walk through the tools, and share the starter resources.

**5:30 PM – Build time:**
Choose an idea and start building. Mentors from Mistral AI and Elastic will be available to help.

**7:30 PM – Show and tell:**
Share what you built with the room, no matter how finished it is. After the demos, we'll award prizes to the top projects.

---

## Judging Criteria and Presentations

Projects will be evaluated on:

| Criteria | Description |
|---|---|
| **Novelty** | A unique idea, a novel use of the data, or an interesting technical approach. |
| **Use of Elastic** | Meaningful use of Elasticsearch: search, aggregations, geo, vector/semantic search. Agent Builder is a bonus, not a requirement. |
| **Use of Mistral** | Meaningful use of Mistral: its APIs, products, creation tools like the Vibe coding CLI, or the AI capabilities behind them. |

At the end you'll present what you built, no matter how finished it is. Show it off even if it's rough; that's the spirit of the night.

Some presentation guidelines:
- **3-minute demo.** Show us **who your project helps**, **what it does**, and **how someone could use it**. No polished UI expected: a notebook, Dev Tools, a script, or Kibana is fine.
- Show the **Elastic** portion (your queries, mappings, or tools) and the **Mistral** portion (which Mistral tech you used and where). Those two, plus any accompanying tech, must be part of the demo.

**Ground rules:** you can think about ideas beforehand, but all implementation happens during the hack night. Please don't bring confidential, sensitive, or proprietary data unless you're authorized to use it.

---

## What you can build

Anything that combines **Elastic** and **Mistral** tech to make SF better for someone who lives here. There's no required architecture; approach it in the way that best suits your idea. Some starter routes:

- **Start from Elastic.** Pick a dataset from the table below, run its ingest notebook to load it into Elasticsearch, then bring in Mistral: embeddings for semantic search, a chat model for RAG, translation, OCR, vision, Voxtral audio, an agent.
- **Start from Mistral.** Build a Mistral agent, an OCR or voice pipeline, or an app you vibe-code with Mistral Vibe, then bring in Elasticsearch to search, retrieve, aggregate, or remember what your app produces.
- **Start from a problem.** Something about SF that bugs you? Find the data for it on [DataSF](https://data.sf.gov/) (the [ingest recipe](open_challenge.md#example-ingesting-any-datasf-dataset) works on any dataset there) or bring your own.

Either way, your project needs both, and how you combine them is up to you. See [open_challenge.md](open_challenge.md) for project ideas, the [Mistral guide](mistral_guide.md) for building with Mistral, and [Using Mistral in Elasticsearch](using_mistral_in_elasticsearch.md) for wiring Mistral models into Elastic.

To get set up:
- **Elastic:** use a serverless deployment from the [Elastic Cloud Serverless free trial](https://cloud.elastic.co/serverless-registration?utm_source=github&utm_medium=event&utm_campaign=2026-11-03-elastic-mistral-sf-hacknight-amer&utm_content=link).
- **Mistral:** see the [Mistral guide](mistral_guide.md).

> **Agent frameworks are optional.** Elastic [Agent Builder](https://www.elastic.co/docs/explore-analyze/ai-features/elastic-agent-builder) is a slick, no-code way to stand up a conversational agent over your indices. Mistral's [Agents API](https://docs.mistral.ai/studio/agents/introduction) gives you agents with built-in tools (web search, code interpreter, document library), function calling, and handoffs, and [Vibe Work](https://docs.mistral.ai/vibe/work/get-started) lets you run agentic tasks with MCP connectors in the browser. Use either, both, or neither. A RAG script, a semantic-search demo, or an analytics notebook counts just as much.

---

## Technical setup

You'll need two things:

1. **Elasticsearch Serverless (9.4+)** — [free trial](https://cloud.elastic.co/serverless-registration?utm_source=github&utm_medium=event&utm_campaign=2026-11-03-elastic-mistral-sf-hacknight-amer&utm_content=link). A home for your data, and where Agent Builder lives.
2. **Mistral API key(s)** — We'll hand these out at the event. Install the SDK with `pip install mistralai` (or `npm i @mistralai/mistralai`) and call Mistral's models, agents, OCR, and audio APIs directly. The same key works in Mistral Vibe.

**How Elastic is used:** Elasticsearch provides the search and retrieval layer: store an SF dataset and query it with keyword, vector, and hybrid search, aggregations, and geo queries, from a notebook, Dev Tools, your own app, or (optionally) Agent Builder.

**How Mistral is used:** Mistral provides the AI capabilities and the tooling: chat and reasoning models, agents, embeddings, OCR, vision, speech, moderation, and the Vibe coding CLI. Call Mistral directly from your own code (see the [Mistral guide](mistral_guide.md)), or register Mistral models as Elasticsearch inference endpoints (see [Using Mistral in Elasticsearch](using_mistral_in_elasticsearch.md)), whichever fits your idea.

---

## Mistral capabilities to explore

Keep it open: these are prompts, not requirements. Any of these can anchor a project, and so can anything else Mistral offers:

| Capability | Where it shines |
|---|---|
| **Vibe coding & CLI** | Build faster with the Mistral Vibe coding CLI |
| **Agents** | Mistral agents with built-in web search, code interpreter, and document library, plus your own function tools (like an Elasticsearch query) |
| **Reasoning & chat** | Multi-step analysis, planning, summarizing, and answering harder questions |
| **Translation** | SF speaks Spanish, Chinese, Tagalog, Vietnamese, Russian, and more: translate menus, event listings, city notices |
| **Function calling & structured outputs** | Turn a resident's description of a problem into clean JSON, or let a model decide which query to run |
| **Embeddings** | Meaning-based search and RAG over SF text (311 notes, inspection violations, event descriptions, landmark histories) |
| **OCR & Document AI** | Read scanned documents, like the typewritten landmark designation reports |
| **Vision** | Understand images, like 311 case photos or City Nature Challenge observations |
| **Speech & audio (Voxtral)** | Voice-driven SF assistants: "when's the next train?", read a walking tour aloud |
| **Content moderation** | Flag or filter user input and dataset text |
| **Vibe Work** | Run agentic tasks in the browser, and plug in tools through MCP connectors |

See the [Mistral guide](mistral_guide.md) for how to get started, and [Mistral's docs](https://docs.mistral.ai/) for what's available.

---

## Public SF Datasets

Suggested starting points. **You're not restricted to these; use any SF dataset you find, or bring your own.** Almost every set on [DataSF](https://data.sf.gov/) has a direct JSON/CSV API (Socrata), so it's easy to ingest (see [open_challenge.md](open_challenge.md)).

Each dataset ships with a ready-to-run ingest notebook in this repo: connect your Elastic project, run all cells, done. Starting from Mistral instead? Each notebook's data-fetch cell doesn't need Elasticsearch, so you can lift it out, process the data with Mistral first, and index the results when you're ready. Every notebook builds a `geo_point`, so you can join any two of them by distance.

| Theme | Dataset | Description | Ingest notebook |
|---|---|---|---|
| Getting around | **[Muni schedule (GTFS)](https://www.sfmta.com/reports/gtfs-transit-data)** | Every Muni bus, Metro, streetcar, and cable car stop (with geo), route, and timetable. | [muni_schedule.ipynb](muni_schedule.ipynb) |
| Getting around | **[BART real-time](https://www.bart.gov/schedules/developers/gtfs-realtime)** + Muni via [511.org](https://511.org/open-data/transit) | Live train arrivals, delays, and service alerts. BART needs no key; Muni real-time needs a free 511 token. | [bart_realtime.ipynb](bart_realtime.ipynb) |
| Neighborhood businesses | **[Registered Business Locations](https://data.sf.gov/d/g8m3-pdis)** | ~100k open businesses: name, address, start date, industry, corridor, neighborhood. | [sf_business_locations.ipynb](sf_business_locations.ipynb) |
| Neighborhood businesses | **[Restaurant Health Inspections](https://data.sf.gov/d/tvy3-wexg)** | Every food-business inspection since 2024: Pass / Conditional Pass / Closure, plus the violation text. | [sf_health_inspections.ipynb](sf_health_inspections.ipynb) |
| Public spaces | **[Street Tree Inventory](https://data.sf.gov/d/tkzw-k3nq)** | ~145k street trees: species, size, planting date, caretaker, exact location. | [sf_street_trees.ipynb](sf_street_trees.ipynb) |
| Public spaces | **[Rec & Parks properties](https://data.sf.gov/d/gtr9-ntp6)** + **[Civic Art Collection](https://data.sf.gov/d/r7bn-7v9c)** | Every park, playground, and rec center, and ~1,000 public artworks, all geo-tagged. | [sf_parks_and_public_art.ipynb](sf_parks_and_public_art.ipynb) |
| Public spaces / history | **[SF Landmarks](https://data.sf.gov/d/97yj-54sx)** | ~390 city landmarks, each with a designation report (often a typewritten scan) and a photo. A real-world **Mistral OCR** project. | [sf_landmarks.ipynb](sf_landmarks.ipynb) |
| Community | **[Our415 Events and Activities](https://data.sf.gov/d/8i3s-ih2a)** | Free and low-cost events from Rec & Park, SF Public Library, and community groups: story hours, drop-ins, classes. | [sf_community_events.ipynb](sf_community_events.ipynb) |
| City information | **[311 Cases](https://data.sf.gov/d/vw6y-z8j6)** | Every 311 request: street cleaning, graffiti, encampments, noise, trees, with resolution notes and often a **photo**. | [sf_311_cases.ipynb](sf_311_cases.ipynb) |
| Nature | **[City Nature Challenge: SF Bay Area](https://www.inaturalist.org/projects/city-nature-challenge-2026-san-francisco-bay-area)** | Tens of thousands of geo-tagged iNaturalist observations of wild plants, birds, bugs, and fungi, each with a **photo** (and sometimes **audio**). The most multimodal set here. | [sf_city_nature_challenge.ipynb](sf_city_nature_challenge.ipynb) |

Mix datasets freely: put 311 tree-maintenance requests next to the street tree inventory, find free events near a Muni stop, pair a park with the public art and landmarks within walking distance, or join health inspections with how long a business has been open.

---

## Prizes

After the demos, we'll award prizes to the top projects.

Good luck, have fun, and happy hacking! 🌉

---

## Resources

Handy documentation and references for tonight.

### Getting started
- [Elasticsearch quickstart](https://www.elastic.co/docs/solutions/search/get-started) — your first index and query
- [Connecting to Elasticsearch](https://www.elastic.co/docs/reference/elasticsearch/clients) — endpoints, API keys, and client setup

### SF data
- [DataSF](https://data.sf.gov/) — the city's open data portal ([API docs](https://dev.socrata.com/docs/queries/))
- [511.org Open Data](https://511.org/open-data) — real-time transit for every Bay Area agency (free token)
- [BART developer resources](https://www.bart.gov/schedules/developers)

### Mistral
- [Mistral guide (this repo)](mistral_guide.md) — getting started with Mistral in a hack setting
- [Mistral docs](https://docs.mistral.ai/) · [models overview](https://docs.mistral.ai/getting-started/models/models_overview/)
- SDKs: [Python](https://github.com/mistralai/client-python) · [TypeScript](https://github.com/mistralai/client-ts)
- [Agents API](https://docs.mistral.ai/agents/introduction) · [built-in tools](https://docs.mistral.ai/agents/tools/)
- [Function calling](https://docs.mistral.ai/capabilities/function_calling/) · [structured outputs](https://docs.mistral.ai/capabilities/structured_output/)
- [Document AI / OCR](https://docs.mistral.ai/capabilities/document_ai/) · [vision](https://docs.mistral.ai/capabilities/vision/) · [Voxtral audio](https://docs.mistral.ai/capabilities/audio/) · [moderation](https://docs.mistral.ai/capabilities/guardrailing/)
- [Mistral Vibe](https://docs.mistral.ai/mistral-vibe/introduction) — the coding CLI ([GitHub](https://github.com/mistralai/mistral-vibe))
- [Vibe Work](https://docs.mistral.ai/vibe/work/get-started) — agentic tasks and MCP connectors in the browser
- [Mistral cookbook](https://github.com/mistralai/cookbook) — runnable examples

### Mistral inside Elasticsearch
- [Using Mistral in Elasticsearch (this repo)](using_mistral_in_elasticsearch.md) — inference endpoints, `semantic_text`, and Agent Builder
- [Create a Mistral inference endpoint (API)](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-inference-put-mistral)

### Agent Builder (optional)
- [Agent Builder overview](https://www.elastic.co/docs/explore-analyze/ai-features/elastic-agent-builder)
- [Building custom tools](https://www.elastic.co/docs/explore-analyze/ai-features/agent-builder/tools/custom-tools)
- [Building custom agents](https://www.elastic.co/docs/explore-analyze/ai-features/agent-builder/custom-agents)
- [Using different models in Agent Builder](https://www.elastic.co/docs/solutions/search/agent-builder/models)
- [Expose agents over MCP](https://www.elastic.co/docs/explore-analyze/ai-features/agent-builder/mcp-server) — connect to Claude, Mistral Vibe, or your own app

### Search & querying
- [ES|QL reference](https://www.elastic.co/docs/explore-analyze/query-filter/languages/esql) — a concise query language for search and aggregations
- [Query DSL](https://www.elastic.co/docs/explore-analyze/query-filter/languages/querydsl) — full-text, filters, and boolean queries
- [Aggregations](https://www.elastic.co/docs/explore-analyze/query-filter/aggregations) — stats, terms, and metrics
- [Geo queries](https://www.elastic.co/docs/reference/query-languages/query-dsl/geo-queries) — "near me", within a neighborhood, sort by distance

### Vector & semantic search (great for RAG)
- [Semantic search with `semantic_text`](https://www.elastic.co/docs/solutions/search/semantic-search/semantic-search-semantic-text) — the fastest path to semantic search
- [kNN / dense vector search](https://www.elastic.co/docs/solutions/search/vector/knn)
- [Bringing your own embeddings](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/dense-vector)

### Ingesting data
- [Python Elasticsearch client](https://www.elastic.co/docs/reference/elasticsearch/clients/python) — what the notebooks use
- [Bulk API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-bulk) — efficient batch indexing
- [Upload a file in Kibana](https://www.elastic.co/docs/manage-data/ingest/upload-data-files) — no-code CSV/JSON ingest
