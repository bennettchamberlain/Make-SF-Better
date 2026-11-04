const state = {
  email: localStorage.getItem("bc_email") || "",
  displayName: localStorage.getItem("bc_name") || "",
  neighborhood: localStorage.getItem("bc_neighborhood") || "",
  cases: [],
  selectedId: null,
  map: null,
  markers: [],
  businessMarkers: [],
};

const $ = (id) => document.getElementById(id);

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (value != null) node.setAttribute(key, value);
  }
  for (const child of children || []) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === "string" ? detail : "Something went wrong";
    throw new Error(message);
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[ch]));
}

function street(address) {
  return (address || "Unknown address").split(",")[0];
}

function setStatus(message, isError) {
  const node = $("status");
  node.textContent = message || "";
  node.classList.toggle("warn", Boolean(isError));
}

async function loadNeighborhoods() {
  const rows = await api("/api/neighborhoods");
  const select = $("neighborhood");
  select.replaceChildren(el("option", { value: "" }, ["Pick a neighborhood"]));
  for (const row of rows) {
    const option = el("option", { value: row.name }, [`${row.name} (${row.open_cases})`]);
    if (row.name === state.neighborhood) option.selected = true;
    select.append(option);
  }
}

async function loadHealth() {
  const health = await api("/api/health");
  const open = health.open_cases ?? 0;
  $("citywide").textContent = open
    ? `${open.toLocaleString()} open jobs a neighbor can take`
    : "No cases loaded yet. Run python ingest.py";
}

async function loadBoard() {
  const query = state.email ? `?email=${encodeURIComponent(state.email)}` : "";
  const board = await api(`/api/leaderboard${query}`);
  const list = $("board");
  list.replaceChildren();
  if (!board.rows.length) {
    list.append(el("li", {}, ["No cleanups logged yet."]));
    return;
  }
  for (const row of board.rows) {
    const place = row.neighborhood ? ` · ${row.neighborhood}` : "";
    const item = el("li", { class: row.you ? "you" : "" }, [
      `${row.rank}. ${row.display_name} — ${row.solved} ${row.solved === 1 ? "case" : "cases"}${place}`,
    ]);
    list.append(item);
  }
  if (board.you && board.you.rank > 20) {
    list.append(el("li", { class: "you" }, [
      `${board.you.rank}. ${board.you.display_name} — ${board.you.solved} cases`,
    ]));
  }
}

async function loadShops() {
  const shops = await api("/api/shops");
  const list = $("shop-list");
  list.replaceChildren();
  for (const shop of shops) {
    const where = [shop.address, shop.neighborhood].filter(Boolean).join(" · ");
    list.append(el("li", {}, [`${shop.name} — ${where}`]));
  }
}

function clearMarkers(list) {
  for (const marker of list) state.map.removeLayer(marker);
  list.length = 0;
}

function ensureMap() {
  if (state.map || !window.L) {
    if (!window.L) $("map").textContent = "The map didn’t load. The list still works.";
    return;
  }
  state.map = L.map("map").setView([37.76, -122.44], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap",
  }).addTo(state.map);
}

function showCasesOnMap() {
  if (!state.map) return;
  clearMarkers(state.markers);
  clearMarkers(state.businessMarkers);
  const bounds = [];
  for (const item of state.cases) {
    const point = item.location;
    if (!point) continue;
    const selected = item.service_request_id === state.selectedId;
    const marker = L.circleMarker([point.lat, point.lon], {
      radius: selected ? 9 : 6,
      color: selected ? "#164e32" : "#1f6b45",
      fillColor: selected ? "#164e32" : "#3d9a68",
      fillOpacity: 0.9,
      weight: 1,
    }).addTo(state.map);
    marker.bindPopup(`<strong>${escapeHtml(street(item.address))}</strong><br>${escapeHtml(item.detail_label)}`);
    marker.on("click", () => selectCase(item.service_request_id));
    state.markers.push(marker);
    bounds.push([point.lat, point.lon]);
  }
  if (bounds.length) state.map.fitBounds(bounds, { padding: [24, 24], maxZoom: 15 });
  state.map.invalidateSize();
  setTimeout(() => state.map && state.map.invalidateSize(), 50);
}

function renderList() {
  const list = $("case-list");
  $("list-title").textContent = state.cases.length
    ? `${state.neighborhood} · ${state.cases.length} open`
    : state.neighborhood;
  list.replaceChildren();
  if (!state.cases.length) {
    list.append(el("p", { class: "hint" }, ["Nothing open in this neighborhood right now."]));
    return;
  }
  for (const item of state.cases) {
    const button = el("button", {
      type: "button",
      class: item.service_request_id === state.selectedId ? "case selected" : "case",
      onclick: () => selectCase(item.service_request_id),
    }, [
      el("strong", {}, [street(item.address)]),
      el("span", {}, [item.detail_label]),
    ]);
    list.append(button);
  }
}

async function selectCase(caseId) {
  state.selectedId = caseId;
  renderList();
  showCasesOnMap();
  const detail = $("detail");
  detail.hidden = false;
  detail.replaceChildren(el("p", {}, ["Loading that block…"]));
  try {
    const data = await api(`/api/cases/${encodeURIComponent(caseId)}`);
    renderDetail(data);
    showNearbyBusinesses(data.businesses || []);
  } catch (error) {
    detail.replaceChildren(el("p", { class: "warn" }, [error.message]));
  }
}

function showNearbyBusinesses(businesses) {
  if (!state.map) return;
  clearMarkers(state.businessMarkers);
  for (const business of businesses) {
    const point = business.location;
    if (!point) continue;
    const marker = L.circleMarker([point.lat, point.lon], {
      radius: 5,
      color: "#a15c07",
      fillColor: "#e8a317",
      fillOpacity: 0.85,
      weight: 1,
    }).addTo(state.map);
    marker.bindPopup(`<strong>${escapeHtml(business.name)}</strong><br>${escapeHtml(business.address || "")}`);
    state.businessMarkers.push(marker);
  }
}

function renderDetail(data) {
  const item = data.case;
  const detail = $("detail");
  const photos = el("div", { class: "photos" });
  if (item.photo_url) {
    photos.append(el("img", { src: item.photo_url, alt: "Photo filed with the 311 case" }));
  }
  const businesses = el("ul", { class: "shops-near" });
    if (!(data.businesses || []).length) {
    businesses.append(el("li", {}, ["No retail or food businesses within 400 meters."]));
  }
  for (const business of data.businesses || []) {
    const sector = business.sector ? ` · ${business.sector}` : "";
    businesses.append(el("li", {}, [`${business.name} · ${business.distance_m} m${sector}`]));
  }
  const joined = (data.shops || []).length;
  const form = el("form", { class: "proof", onsubmit: (event) => submitProof(event, item.service_request_id) }, [
    el("label", {}, ["Before", el("input", { name: "before", type: "file", accept: "image/*", required: "required" })]),
    el("label", {}, ["After", el("input", { name: "after", type: "file", accept: "image/*", required: "required" })]),
    el("button", { type: "submit" }, ["Mark this cleaned"]),
  ]);
  detail.replaceChildren(
    el("div", {}, [
      el("h2", {}, [street(item.address)]),
      el("p", { class: "meta" }, [
        `${item.detail_label} · ${item.neighborhood}. Wear gloves. Skip needles, human waste, or anything that looks hazardous — those stay with the city.`,
      ]),
    ]),
    el("div", { class: "detail-grid" }, [
      el("div", {}, [
        photos.childNodes.length ? el("p", { class: "hint" }, ["Photo from the original 311 report. You still add your own before and after."]) : el("p", { class: "hint" }, ["No city photo on this case."]),
        photos,
        el("h3", {}, ["Your proof"]),
        form,
        el("p", { class: "hint" }, ["Both photos are required. We don’t review them. Logging this here does not close the official 311 case."]),
      ]),
      el("div", {}, [
        el("h3", {}, ["Relevant shops nearby"]),
        businesses,
        el("p", { class: "hint" }, [
          joined
            ? `${joined} ${joined === 1 ? "shop that has joined" : "shops that have joined"} within 400 meters will get the after photo.`
            : "No joined shops within 400 meters yet, so this cleanup won’t send email until one signs up.",
        ]),
      ]),
    ]),
  );
}

async function submitProof(event, caseId) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  button.disabled = true;
  button.textContent = "Saving…";
  const body = new FormData(form);
  body.set("email", state.email);
  body.set("display_name", state.displayName);
  try {
    const result = await api(`/api/cases/${encodeURIComponent(caseId)}/complete`, { method: "POST", body });
    state.cases = state.cases.filter((item) => item.service_request_id !== caseId);
    state.selectedId = null;
    renderList();
    showCasesOnMap();
    renderSuccess(result);
    await loadBoard();
    await loadHealth();
  } catch (error) {
    button.disabled = false;
    button.textContent = "Mark this cleaned";
    form.append(el("p", { class: "warn" }, [error.message]));
  }
}

function renderSuccess(result) {
  const detail = $("detail");
  const mailed = result.notified || [];
  const list = el("ul", { class: "shops-near" });
  if (!mailed.length) {
    list.append(el("li", {}, ["No joined shop was close enough to email."]));
  }
  for (const shop of mailed) {
    const how = shop.delivery === "failed" ? `not sent (${shop.error || "error"})` : shop.delivery;
    list.append(el("li", {}, [`${shop.name} · ${shop.email} · ${how}`]));
  }
  const images = el("div", { class: "photos" }, [
    el("img", { src: result.before_url, alt: "Before" }),
    el("img", { src: result.after_url, alt: "After" }),
  ]);
  const rank = result.rank ? ` You’re #${result.rank} with ${result.solved}.` : "";
  detail.replaceChildren(
    el("h2", {}, ["Logged"]),
    el("p", {}, [`Both photos are in.${rank}`]),
    images,
    el("h3", {}, ["Note sent to shops"]),
    list,
    el("pre", { class: "note" }, [result.note ? result.note.text : ""]),
    result.mail === "gmail" || (result.notified || []).some((shop) => shop.delivery === "gmail")
      ? el("p", { class: "hint" }, ["Sent from your Gmail, with both photos attached. Replies come back to you."])
      : el("p", { class: "hint" }, ["No Gmail app password is saved, so these notes were kept locally instead of sent."]),
  );
  detail.hidden = false;
}

async function showJobs(event) {
  if (event) event.preventDefault();
  state.email = $("email").value.trim().toLowerCase();
  state.displayName = $("display-name").value.trim();
  if ($("neighborhood").value) state.neighborhood = $("neighborhood").value;
  if (!state.neighborhood) {
    setStatus("Pick a neighborhood", true);
    return;
  }
  localStorage.setItem("bc_email", state.email);
  localStorage.setItem("bc_name", state.displayName);
  localStorage.setItem("bc_neighborhood", state.neighborhood);
  setStatus("Saving…");
  try {
    const saved = await api("/api/volunteers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: state.email,
        display_name: state.displayName,
        neighborhood: state.neighborhood,
      }),
    });
    state.displayName = saved.display_name;
    const appPassword = $("app-password").value;
    let mailReady = saved.mail_ready;
    if (appPassword.trim()) {
      const mail = await api("/api/mail", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: state.email, app_password: appPassword }),
      });
      mailReady = mail.mail_ready;
      $("app-password").value = "";
    }
    state.cases = await api(`/api/cases?neighborhood=${encodeURIComponent(state.neighborhood)}`);
    state.selectedId = null;
    $("work").hidden = false;
    $("detail").hidden = true;
    ensureMap();
    renderList();
    showCasesOnMap();
    const mailNote = mailReady ? " Gmail will send the note with your photos." : " Add a Gmail app password when you want the note to come from you.";
    setStatus(`${state.cases.length} open jobs in ${state.neighborhood}.${mailNote}`);
    await loadBoard();
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function saveShop(event) {
  event.preventDefault();
  const status = $("shop-status");
  status.textContent = "Placing that address…";
  status.classList.remove("warn");
  try {
    const saved = await api("/api/shops", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("shop-name").value,
        email: $("shop-email").value,
        address: $("shop-address").value,
      }),
    });
    const via = saved.source === "sf-business-registry" ? "city business registry" : "address lookup";
    status.textContent = `${saved.name} is on the map in ${saved.neighborhood || "San Francisco"} (${via}).`;
    $("shop-form").reset();
    await loadShops();
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("warn");
  }
}

function restoreForm() {
  $("email").value = state.email;
  $("display-name").value = state.displayName;
  if (state.neighborhood) $("neighborhood").value = state.neighborhood;
}

$("join").addEventListener("submit", showJobs);
$("shop-form").addEventListener("submit", saveShop);

loadHealth().catch((error) => { $("citywide").textContent = error.message; });
loadBoard().catch(() => {});
loadShops().catch(() => {});
loadNeighborhoods()
  .then(() => {
    restoreForm();
    if (state.email && state.neighborhood) return showJobs();
  })
  .catch((error) => setStatus(error.message, true));
