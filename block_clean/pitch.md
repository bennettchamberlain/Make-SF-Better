# Block Clean pitch

Read straight through. About a minute and a half.

---

Block Clean keeps the open 311 jobs a neighbor can finish on foot. Graffiti on a hydrant. Posters on a pole. Litter in front of a shop.

We use two city datasets that were never built to meet. DataSF 311 is every open case from the last 180 days: a point, a neighborhood, and a request type. DataSF businesses is every open retail and food storefront: a point, and what the shop is. A tagged pole and the cafe on that corner share no id. When a shop signs up, we place them on the city's point, or with OpenStreetMap if the registry doesn't have the address.

Mistral is how a request type becomes a job. About 700 category combinations, and the city never says which ones a person can do. The model returns a yes or no. Seventy-seven stayed. Needles, waste, and encampments are vetoed even if the model says yes.

Elastic is how those two maps become one question. Each shop description is embedded with Mistral. Opening a case runs that semantic search and a 400 meter geo filter together. You only get storefronts on that block whose description matches the cleanup. The before and after photos go to the shops that joined inside that radius.

The open data already had the points. It did not have "safe for one person," or "the cafe on this block that would care." That question is what these two make possible.
