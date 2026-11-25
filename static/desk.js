const TODAY = "2026-06-15";

const FIELDS = [
  "insured_name",
  "license_number",
  "license_issued_on",
  "license_expires_on",
  "vin",
  "plate",
  "vehicle_year",
  "prior_policy_expires_on",
  "sdip_points",
  "line_of_business",
];

const DEMOS = {
  "marcus-hale": ["license.txt", "registration.txt"],
  "helen-brooks": ["license.txt"],
  "injection-note": ["license.txt", "note.txt"],
};

const banner = document.querySelector("#banner");
const form = document.querySelector("#file-form");
const documentsEl = document.querySelector("#documents");
const factsEl = document.querySelector("#facts");
const memoEl = document.querySelector("#memo");
const stepsEl = document.querySelector("#steps");
const bindButton = document.querySelector("#bind");
const closeButton = document.querySelector("#close");
const closeNote = document.querySelector("#close-note");
const readButton = document.querySelector("#read-folder");

const state = { caseId: null };

form.addEventListener("submit", (event) => {
  event.preventDefault();
  readTypedFolder();
});

document.querySelector(".choices").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-slug]");
  if (!button) return;
  openSample(button.dataset.slug);
});

bindButton.addEventListener("click", bindCase);
closeButton.addEventListener("click", closeCase);

async function readTypedFolder() {
  const lines = [];
  for (const name of FIELDS) {
    const value = form.elements[name].value.trim();
    if (value) lines.push(`${name}: ${value}`);
  }
  if (!lines.length) {
    showBanner("Type at least one field.");
    return;
  }
  const files = [{ name: "application.txt", body_text: lines.join("\n") }];
  const note = form.elements.note.value.trim();
  if (note) files.push({ name: "note.txt", body_text: note });
  await runDocuments(files);
}

async function openSample(slug) {
  clearBanner();
  setBusy(true);
  try {
    const names = DEMOS[slug];
    const texts = await Promise.all(names.map((name) => readDossier(slug, name)));
    const files = names.map((name, index) => ({ name, body_text: texts[index] }));
    await runDocuments(files, { alreadyBusy: true });
  } catch (error) {
    showBanner(error.message);
  } finally {
    setBusy(false);
  }
}

async function runDocuments(files, options = {}) {
  if (!options.alreadyBusy) {
    clearBanner();
    setBusy(true);
  }
  bindButton.disabled = true;
  closeButton.disabled = true;
  try {
    const created = await request("/cases", { method: "POST" });
    state.caseId = created.id;
    for (const file of files) {
      await request(`/cases/${state.caseId}/documents`, {
        method: "POST",
        body: { name: file.name, body_text: file.body_text },
      });
    }
    const run = await request(`/cases/${state.caseId}/run?today=${TODAY}`, { method: "POST" });
    const folder = await request(`/cases/${state.caseId}`);
    const bodies = await Promise.all(folder.documents.map((item) => {
      return request(`/cases/${state.caseId}/documents/${item.id}`);
    }));
    const trace = await request(`/runs/${run.run_id}`);
    renderDocuments(bodies);
    renderFacts(folder.facts);
    renderMemo(folder.memo);
    renderSteps(trace.steps);
    bindButton.disabled = !folder.memo || folder.memo.recommendation !== "quote";
    closeButton.disabled = false;
  } catch (error) {
    showBanner(error.message);
  } finally {
    if (!options.alreadyBusy) setBusy(false);
  }
}

async function bindCase() {
  clearBanner();
  try {
    const policy = await request(`/cases/${state.caseId}/bind?today=${TODAY}`, { method: "POST" });
    showBanner(`Bound ${policy.carrier} at ${money(policy.premium)}. The term ends ${policy.expires_on}, and that day is not covered.`);
  } catch (error) {
    showBanner(error.message);
  }
}

async function closeCase() {
  clearBanner();
  try {
    const closed = await request(`/cases/${state.caseId}/close`, {
      method: "POST",
      body: { note: closeNote.value },
    });
    showBanner(`Closed. ${closed.note}`);
    bindButton.disabled = true;
    closeButton.disabled = true;
  } catch (error) {
    showBanner(error.message);
  }
}

async function readDossier(slug, name) {
  const response = await fetch(`/dossiers/${slug}/documents/${name}`);
  if (!response.ok) throw new Error("The sample folder could not be read.");
  return response.text();
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    method: options.method || "GET",
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    const message = typeof detail === "string" ? detail : "The desk could not complete that step.";
    throw new Error(message);
  }
  return payload;
}

function renderDocuments(documents) {
  documentsEl.replaceChildren(...documents.map((document) => {
    const card = element("article", "card");
    card.append(element("h3", "", document.name));
    card.append(element("pre", "", document.body_text));
    return card;
  }));
}

function renderFacts(facts) {
  if (!facts.length) {
    factsEl.replaceChildren(element("p", "empty", "No facts stored."));
    return;
  }
  factsEl.replaceChildren(...facts.map((fact) => {
    const card = element("article", "fact");
    card.append(element("h3", "", fact.name));
    card.append(element("p", "", fact.value));
    const quote = document.createElement("blockquote");
    quote.textContent = fact.quote;
    card.append(quote);
    return card;
  }));
}

function renderMemo(memo) {
  if (!memo) {
    memoEl.replaceChildren(element("p", "empty", "No memo."));
    return;
  }
  memoEl.replaceChildren(element("p", "memo-line", sentence(memo)));
  for (const reason of memo.reasons || []) {
    memoEl.append(element("p", "", reason));
  }
  if (memo.missing && memo.missing.length) {
    memoEl.append(element("p", "meta", memo.missing.join(", ")));
  }
}

function sentence(memo) {
  const premium = money(memo.premium);
  if (memo.recommendation === "quote") {
    return `This file can be quoted. ${memo.carrier} at ${premium}. You can bind it.`;
  }
  if (memo.recommendation === "refer") {
    return "A person has to look at this file before anyone binds it.";
  }
  if (memo.recommendation === "decline") {
    return "Do not bind this file.";
  }
  if (memo.recommendation === "incomplete") {
    return "The folder is not complete.";
  }
  if (memo.recommendation === "out_of_scope") {
    return "This is not an auto file.";
  }
  return memo.recommendation;
}

function renderSteps(steps) {
  if (!steps.length) {
    stepsEl.replaceChildren(element("p", "empty", "No steps."));
    return;
  }
  stepsEl.replaceChildren(...steps.map((step) => {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `${step.position}. ${step.kind} · ${step.name}`;
    details.append(summary);
    details.append(element("h3", "", "Request"));
    details.append(element("pre", "", JSON.stringify(step.request, null, 2)));
    details.append(element("h3", "", "Response"));
    details.append(element("pre", "", JSON.stringify(step.response, null, 2)));
    return details;
  }));
}

function money(value) {
  if (value === null || value === undefined) return "none";
  return Number(value).toFixed(2);
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function showBanner(message) {
  banner.hidden = false;
  banner.textContent = message;
}

function clearBanner() {
  banner.hidden = true;
  banner.textContent = "";
}

function setBusy(busy) {
  readButton.disabled = busy;
  for (const button of document.querySelectorAll(".choices button")) {
    button.disabled = busy;
  }
}
