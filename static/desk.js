const TODAY = "2026-06-15";

const DEMOS = {
  "marcus-hale": ["license.txt", "registration.txt"],
  "helen-brooks": ["license.txt"],
  "injection-note": ["license.txt", "note.txt"],
};

const banner = document.querySelector("#banner");
const documentsEl = document.querySelector("#documents");
const factsEl = document.querySelector("#facts");
const memoEl = document.querySelector("#memo");
const stepsEl = document.querySelector("#steps");
const bindButton = document.querySelector("#bind");
const closeButton = document.querySelector("#close");
const closeNote = document.querySelector("#close-note");

const state = { caseId: null };

document.querySelector(".choices").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-slug]");
  if (!button) return;
  openFolder(button.dataset.slug);
});

bindButton.addEventListener("click", bindCase);
closeButton.addEventListener("click", closeCase);

async function openFolder(slug) {
  clearBanner();
  setBusy(true);
  try {
    const files = DEMOS[slug];
    const texts = await Promise.all(files.map((name) => readDossier(slug, name)));
    const created = await request("/cases", { method: "POST" });
    state.caseId = created.id;
    for (let index = 0; index < files.length; index += 1) {
      await request(`/cases/${state.caseId}/documents`, {
        method: "POST",
        body: { name: files[index], body_text: texts[index] },
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
    bindButton.disabled = false;
    closeButton.disabled = false;
  } catch (error) {
    showBanner(error.message);
  } finally {
    setBusy(false);
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
  const headline = element("p", "memo-line", `${memo.recommendation} · ${money(memo.premium)}`);
  const carrier = element("p", "meta", memo.carrier || "No carrier");
  memoEl.replaceChildren(headline, carrier);
  for (const reason of memo.reasons || []) {
    memoEl.append(element("p", "", reason));
  }
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
  for (const button of document.querySelectorAll(".choices button")) {
    button.disabled = busy;
  }
}
