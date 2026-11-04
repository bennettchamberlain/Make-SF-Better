# Block Clean pitch

Read straight through. About two minutes if you keep moving.

---

This is Block Clean. We take open San Francisco 311 requests and keep the ones a neighbor can finish on foot. Graffiti on a hydrant. Posters on a pole. Litter in front of a shop. Needles, human waste, and encampments stay with the city.

Three sources, and the product is the join. DataSF 311 gives every open case from the last 180 days, already geocoded, with a neighborhood and a request type. DataSF registered businesses gives every open retail and food storefront, also geocoded. Those files share no id. A tagged pole and the cafe on that block are not linked. The third source is OpenStreetMap. A shop types an address. We use the city's point if the registry has it. If not, Nominatim places it, and Elastic picks the nearest neighborhood from the index.

The city never says a person can do the job. About 700 combinations of service name, subtype, and detail. Mistral small returns a strict yes or no, a short label, and one sentence. Seventy-seven categories came back as work for one adult with a bag and a scraper. A safety list still vetoes needles, waste, and encampments, even if the model says yes.

Elastic is the query. Five indexes: cases, businesses, joined shops, volunteers, and completions. The neighborhood menu is an aggregation over open cases. Each business is a semantic_text field, embedded with mistral-embed. Opening a case runs that semantic search and a 400 meter geo filter in the same query. You see storefronts that are close and that match the cleanup. A before photo and an after photo go to every joined shop inside that radius, reply-to set to the neighbor. The leaderboard is an aggregation, and the completion write is create-only, so two people can't claim the same case.

Without Mistral, you hand-label hundreds of city codes, and the ones that sound small and aren't slip through. Without Elastic, "shops on this block that would care" is a guess. The open data has points and categories. It does not have that question.
