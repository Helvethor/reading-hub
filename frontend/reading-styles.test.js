import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {mountReadingStyles} from "../library/static/library/reading-styles.js";

let dom;
afterEach(() => dom?.window.close());

function fixture({
  authenticated = false, guest = {}, accountSettings = false, workType = "article",
} = {}) {
  const typeTitle = `${workType[0].toUpperCase()}${workType.slice(1)}`;
  const scope = accountSettings
    ? 'data-account-settings data-scope="account"'
    : 'data-scope="output"';
  const scopeControl = authenticated && !accountSettings
    ? `<select data-style-scope><option value="output">This version</option><option value="account">My defaults · ${typeTitle}</option></select>`
    : "";
  const type = accountSettings
    ? '<select data-style-type><option value="article" selected>Article</option><option value="other">Other</option></select>'
    : `<span data-style-type-label>Work type: ${typeTitle}</span>`;
  const guestActions = authenticated
    ? '<div class="reading-style-import" hidden><button data-import-guest>Import guest style</button></div>'
    : '<button data-clear-guest>Clear guest style</button>';
  dom = new JSDOM(`<!doctype html><head>
      <link rel="stylesheet" href="/old.css" data-reading-style>
    </head><body>
      <a href="/versions/101/pdf/" data-reading-pdf>Download PDF</a>
      <details class="reading-style-controls" data-preview-url="/reading-style/preview/"
        data-work-type="${workType}" data-rendition-id="101" data-output-id="immutable-101"
        data-authenticated="${authenticated}" data-import-guest-url="/reading-style/import-guest/"
        ${scope}>
        ${scopeControl}
        ${type}
        <form class="reading-style-settings"><input type="hidden" name="csrfmiddlewaretoken" value="csrf">
          <label><input type="number" name="font_size" value="14"></label>
          <label><input type="number" name="letter_spacing" value="0"></label>
          <label><input type="checkbox" name="italic_to_bold"></label>
          <button type="button" data-reset-setting="font_size"></button>
          <button type="button" data-reset-setting="letter_spacing"></button>
          <button type="button" data-reset-setting="italic_to_bold"></button>
        </form>
        <span data-style-origin-for="font_size"></span>
        <span data-style-origin-for="letter_spacing"></span>
        <span data-style-origin-for="italic_to_bold"></span>
        ${guestActions}
        <p class="reading-style-status"></p><p class="reading-style-error" hidden></p>
      </details>
    </body>`, {url: "http://localhost/versions/101/"});
  const {window: view} = dom;
  if (Object.keys(guest).length) {
    view.localStorage.setItem("reading-hub:reading-style:v1:immutable-101", JSON.stringify(guest));
  }
  const append = view.document.head.append.bind(view.document.head);
  view.document.head.append = (...nodes) => {
    append(...nodes);
    for (const node of nodes) {
      if (node.tagName === "LINK" && node.media === "not all") {
        queueMicrotask(() => node.dispatchEvent(new view.Event("load")));
      }
    }
  };
  const calls = [];
  view.fetch = async (url, options = {}) => {
    calls.push({url, options});
    const body = options.body ? JSON.parse(options.body) : {};
    if (url === "/reading-style/import-guest/") {
      return json({imported: true, message: "Guest style was imported."});
    }
    const layer = {...(body.guest_overrides || {})};
    Object.assign(layer, body.changes || {});
    for (const key of body.reset || []) delete layer[key];
    for (const key of ["font_size", "letter_spacing"]) {
      if (typeof layer[key] === "string") layer[key] = Number(layer[key]);
    }
    const settings = {font_size: 14, letter_spacing: 0, italic_to_bold: false, ...layer};
    const origins = Object.fromEntries(Object.keys(settings).map(key => [
      key, {source: Object.hasOwn(layer, key) ? body.scope || "output" : "built-in",
        label: Object.hasOwn(layer, key) ? "This version" : `Built-in · ${typeTitle}`},
    ]));
    const activeLayers = body.scope === "account"
      ? {output: {}, account: layer} : {output: layer, account: {}};
    return json({
      settings, origins, layers: activeLayers, layer, overridden: Object.keys(layer),
      work_type: body.work_type || workType, output_id: "immutable-101", rendition_id: 101,
      scope: body.scope || "output", token: "style-token",
      presentation: "signed-appearance-token", theme: "", persisted: authenticated,
      stylesheet: "/reading-style.css?style=style-token&theme=&v=7",
    });
  };
  const panel = view.document.querySelector(".reading-style-controls");
  const workspace = view.document.createElement("section");
  workspace.id = "unified-workspace";
  panel.before(workspace);
  mountReadingStyles(panel);
  return {
    view, panel, calls,
    form: panel.querySelector(".reading-style-settings"),
    pdf: view.document.querySelector("[data-reading-pdf]"),
    key: "reading-hub:reading-style:v1:immutable-101",
  };
}

function json(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Map([["content-type", "application/json"]]),
    json: async () => data,
  };
}

const tick = () => new Promise(resolve => setTimeout(resolve, 0));
async function settle(view) {
  await tick();
  await tick();
}

function change(view, input, value) {
  if (input.type === "checkbox") input.checked = value;
  else input.value = value;
  input.dispatchEvent(new view.Event("change", {bubbles: true}));
}

test("guest output choices persist sparsely, including false and zero, and reset one key", async () => {
  const {view, panel, form, calls, pdf, key} = fixture();
  await settle(view);
  assert.equal(panel.querySelector(".reading-style-error").hidden, true);

  change(view, form.elements.italic_to_bold, false);
  await settle(view);
  change(view, form.elements.letter_spacing, "0");
  await settle(view);
  assert.deepEqual(JSON.parse(view.localStorage.getItem(key)), {
    italic_to_bold: false, letter_spacing: 0,
  });
  const update = calls.at(-1);
  assert.equal(update.options.method, "POST");
  assert.equal(update.options.headers["X-CSRFToken"], "csrf");
  assert.equal(JSON.parse(update.options.body).changes.letter_spacing, "0");
  assert.equal(JSON.parse(update.options.body).scope, "output");
  assert.equal(new URL(pdf.href).searchParams.get("presentation"), "signed-appearance-token");
  assert.equal(new URL(pdf.href).searchParams.has("style"), false);

  panel.querySelector('[data-reset-setting="letter_spacing"]').click();
  await settle(view);
  assert.deepEqual(JSON.parse(view.localStorage.getItem(key)), {italic_to_bold: false});
  assert.equal(panel.querySelector('[data-reset-setting="letter_spacing"]').disabled, true);
  assert.equal(panel.querySelector('[data-reset-setting="italic_to_bold"]').disabled, false);
  assert.match(panel.querySelector('[data-style-origin-for="italic_to_bold"]').textContent,
    /This version/);
});

test("signed-in controls persist only changed fields in the selected private layer", async () => {
  const {view, panel, form, calls} = fixture({authenticated: true});
  await settle(view);
  const scope = panel.querySelector("[data-style-scope]");
  change(view, scope, "account");
  await settle(view);
  change(view, form.elements.font_size, "18");
  await settle(view);
  const request = JSON.parse(calls.at(-1).options.body);
  assert.equal(request.scope, "account");
  assert.equal(request.rendition_id, 101);
  assert.deepEqual(request.changes, {font_size: "18"});
  assert.deepEqual(request.reset, []);
  assert.equal(panel.querySelector(".reading-style-status").textContent,
    "My defaults are saved privately to your account.");
  panel.querySelector('[data-reset-setting="font_size"]').click();
  await settle(view);
  assert.deepEqual(JSON.parse(calls.at(-1).options.body).reset, ["font_size"]);
});

test("workspace appearance updates the work-type label and account scope option", async () => {
  const {view, panel} = fixture({authenticated: true, workType: "other"});
  await settle(view);

  assert.equal(panel.querySelector('[data-style-type-label]').textContent, "Work type: Other");
  assert.equal(panel.querySelector('option[value="account"]').textContent, "My defaults · Other");

  view.document.querySelector("#unified-workspace").dispatchEvent(
    new view.CustomEvent("reading-style-snapshot", {
      detail: {
        work_type: "article",
        settings: {font_size: 14, letter_spacing: 0, italic_to_bold: false},
        origins: {
          font_size: {source: "built-in", label: "Built-in · Article"},
          letter_spacing: {source: "built-in", label: "Built-in · Article"},
          italic_to_bold: {source: "built-in", label: "Built-in · Article"},
        },
        layers: {output: {}, account: {}},
      },
    }),
  );

  assert.equal(panel.querySelector('[data-style-type-label]').textContent, "Work type: Article");
  assert.equal(panel.querySelector('option[value="account"]').textContent, "My defaults · Article");
  assert.equal(panel.querySelector('[data-style-origin-for="font_size"]').textContent,
    "Built-in · Article");
});

test("storage failure remains visible while the in-memory style is applied", async () => {
  const {view, panel, form} = fixture();
  Object.defineProperty(view, "localStorage", {
    configurable: true,
    get() { throw new Error("storage denied"); },
  });
  await settle(view);
  change(view, form.elements.italic_to_bold, true);
  await settle(view);
  assert.match(panel.querySelector(".reading-style-error").textContent, /browser storage failed/);
  assert.match(panel.querySelector(".reading-style-status").textContent, /Applied in this tab/);
  assert.equal(view.document.querySelector("link[data-reading-style]").href
    .includes("style-token"), true);
});

test("guest settings are imported only on explicit action and errors retain local data", async () => {
  const {view, panel, calls, key} = fixture({
    authenticated: true, guest: {font_size: 18, italic_to_bold: true},
  });
  await settle(view);
  const importBox = panel.querySelector(".reading-style-import");
  assert.equal(importBox.hidden, false);
  let rejectImport = true;
  const originalFetch = view.fetch;
  view.fetch = async (url, options) => {
    if (url === "/reading-style/import-guest/" && rejectImport) {
      calls.push({url, options});
      return json({error: "Import rejected."}, 400);
    }
    return originalFetch(url, options);
  };
  importBox.querySelector("[data-import-guest]").click();
  await settle(view);
  assert.match(panel.querySelector(".reading-style-error").textContent, /Import rejected/);
  assert.notEqual(view.localStorage.getItem(key), null);

  rejectImport = false;
  importBox.querySelector("[data-import-guest]").click();
  await settle(view);
  assert.equal(view.localStorage.getItem(key), null);
  assert.equal(importBox.hidden, true);
  assert.match(panel.querySelector(".reading-style-status").textContent, /explicitly imported|imported/i);
});
