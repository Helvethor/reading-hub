import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {mountReadingStyles} from "../library/static/library/reading-styles.js";
import {applyTheme} from "../library/static/library/themes.js";

let dom;
afterEach(() => dom?.window.close());
function fixture({defaultsOnly = false} = {}) {
  dom = new JSDOM(`<!doctype html><head>${defaultsOnly ? "" : '<link rel="stylesheet" href="/old.css" data-reading-style>'}</head>
    <body><a href="/versions/2/download.pdf?style=old" data-reading-pdf>Download PDF</a>
    <article><h2 data-reading-marker="I. ">Exact title</h2><p>Unchanged prose.</p></article>
    <details class="reading-style-controls" data-preview-url="/reading-style/preview/"${defaultsOnly ? " data-defaults-only" : ""}>
    <form class="reading-style-settings"><select name="style_profile">
    <option value="">Custom</option><option value="marxist" selected>Marxist</option>
    <option value="1">Comfort</option></select>
    <input type="number" name="font_size" value="14" min="9" max="28" required>
    <input type="checkbox" name="italic_to_bold"><button value="apply">Apply</button></form>
    <p class="reading-style-status"></p><p class="reading-style-error" hidden></p>
    <form class="reading-style-save" action="/save/">
    <input name="csrfmiddlewaretoken" value="csrf-fixture">
    <input name="style" value="old"><select name="profile_id"><option value="">Choose</option>
    <option value="1">Comfort</option></select><input name="profile_name">
    <button name="operation" value="update">Update</button>
    <button name="operation" value="create">Save as new</button></form>
    <form class="reading-style-default" action="/default/"><select name="style_profile">
    <option value="marxist">Marxist</option><option value="1">Comfort</option></select>
    <button>Default</button></form></details></body>`, {url: "http://localhost/versions/2/"});
  const {window: view} = dom;
  const panel = view.document.querySelector("details");
  mountReadingStyles(panel);
  return {view, panel, form: panel.querySelector(".reading-style-settings"),
    pdf: view.document.querySelector("[data-reading-pdf]")};
}
const json = (data, status = 200) => ({ok: status === 200, status,
  headers: new Map([["content-type", "application/json"]]), json: async () => data});
const tick = () => new Promise(resolve => setTimeout(resolve, 5));
function change(view, input, value) {
  input.value = value;
  input.dispatchEvent(new view.Event("change", {bubbles: true}));
}
function snapshot(token, size = 18) {
  return {token, stylesheet: `/reading-style.css?style=${token}`,
    settings: {font_size: size, italic_to_bold: true}};
}
async function load(view) {
  await tick();
  const sheet = view.document.querySelector('link[media="not all"]');
  assert(sheet, "New CSS must be loaded before replacing the old display.");
  sheet.dispatchEvent(new view.Event("load"));
  await tick();
}

test("a reading style changed after a theme refresh removes the current sheet", async () => {
  const {view, form} = fixture();
  const site = view.document.createElement("link");
  site.rel = "stylesheet";
  site.href = "/paper.css";
  site.dataset.siteTheme = "";
  view.document.head.append(site);
  const changing = applyTheme(view.document, {theme: "dark", stylesheet: "/dark.css"});
  for (const sheet of view.document.querySelectorAll('link[media="not all"]')) {
    sheet.dispatchEvent(new view.Event("load"));
  }
  await changing;
  view.fetch = async () => json(snapshot("after-theme"));
  change(view, form.elements.font_size, "18");
  await load(view);
  assert.equal(view.document.querySelectorAll("link[data-reading-style]").length, 1);
  assert.equal(view.document.querySelector("[data-reading-style]").getAttribute("href"),
    "/reading-style.css?style=after-theme");
});

test("editor defaults update and save exact profiles without loading publication CSS or changing content", async () => {
  const {view, panel, form} = fixture({defaultsOnly: true});
  const original = view.document.querySelector("article").innerHTML;
  const theme = view.document.createElement("link");
  theme.rel = "stylesheet";
  theme.href = "/dark.css";
  theme.dataset.siteTheme = "";
  view.document.head.append(theme);
  view.fetch = async () => json(snapshot("editor-default", 22));
  change(view, form.elements.style_profile, "1");
  await tick();
  assert.equal(form.elements.font_size.value, "22");
  assert.equal(form.elements.italic_to_bold.checked, true);
  assert.equal(panel.querySelector('input[name=style]').value, "editor-default");
  assert.equal(view.document.querySelectorAll("link").length, 1);
  assert.equal(view.document.querySelector("[data-site-theme]"), theme);
  assert.match(panel.querySelector(".reading-style-status").textContent, /Editor appearance is unchanged/);
  const save = panel.querySelector(".reading-style-save");
  let posted;
  view.fetch = async (url, options) => {
    posted = options.body;
    return json({id: 1, name: "Comfort", default: "marxist"});
  };
  save.requestSubmit(save.querySelector("[value=update]"));
  await tick();
  assert.equal(posted.get("style"), "editor-default");
  assert.equal(posted.get("csrfmiddlewaretoken"), "csrf-fixture");
  const defaults = panel.querySelector(".reading-style-default");
  defaults.elements.style_profile.value = "1";
  view.fetch = async (url, options) => {
    posted = options.body;
    return json({default: "1"});
  };
  defaults.requestSubmit();
  await tick();
  assert.equal(posted.get("style_profile"), "1");
  assert.equal(panel.dataset.default, "1");
  assert.equal(view.document.querySelector("article").innerHTML, original);
  assert.equal(view.document.querySelectorAll("link").length, 1);
});

test("failed editor default settings preserve the previous token and expose the error", async () => {
  const {view, panel, form} = fixture({defaultsOnly: true});
  view.fetch = async () => json({error: "Invalid style"}, 400);
  change(view, form.elements.font_size, "18");
  await tick();
  assert.equal(panel.querySelector('input[name=style]').value, "old");
  assert.match(panel.querySelector(".reading-style-error").textContent, /Invalid style.*settings are unchanged/);
  assert.equal(view.document.querySelectorAll("link").length, 0);
});

test("live settings atomically bind CSS, PDF, saved snapshot and history without changing prose", async () => {
  const {view, panel, form, pdf} = fixture();
  const original = view.document.querySelector("article").innerHTML;
  let url;
  view.fetch = async request => { url = request; return json(snapshot("new")); };
  change(view, form.elements.font_size, "18");
  assert.equal(pdf.hasAttribute("href"), false);
  assert.equal(panel.querySelector("[value=create]").disabled, true);
  await tick();
  assert.equal(view.document.querySelector("[data-reading-style]").getAttribute("href"), "/old.css");
  assert.equal(new URL(url, view.location.href).searchParams.get("style_action"), "apply");
  await load(view);
  assert(pdf.href.endsWith("?style=new"));
  assert(view.document.querySelector("[data-reading-style]").href.endsWith("style=new"));
  assert.equal(panel.querySelector('input[name=style]').value, "new");
  assert.equal(form.elements.style_profile.value, "");
  assert.equal(new URL(view.location).searchParams.get("style"), "new");
  assert.equal(view.document.querySelector("article").innerHTML, original);
  assert.equal(panel.querySelector(".reading-style-error").hidden, true);
});

test("newer selections win even if an older server response arrives last", async () => {
  const {view, form, pdf} = fixture();
  const responses = [];
  view.fetch = () => new Promise(resolve => responses.push(resolve));
  change(view, form.elements.font_size, "16");
  change(view, form.elements.font_size, "20");
  responses[1](json(snapshot("latest", 20)));
  await load(view);
  responses[0](json(snapshot("stale", 16)));
  await tick();
  assert(pdf.href.endsWith("style=latest"));
  assert.equal(view.document.querySelectorAll("link").length, 1);
});

test("stylesheet or server failure preserves previous display and PDF and surfaces an error", async () => {
  const {view, panel, form, pdf} = fixture();
  view.fetch = async () => json(snapshot("failed"));
  change(view, form.elements.font_size, "18");
  await tick();
  view.document.querySelector('link[media="not all"]').dispatchEvent(new view.Event("error"));
  await tick();
  assert(pdf.href.endsWith("style=old"));
  assert.equal(view.document.querySelector("[data-reading-style]").getAttribute("href"), "/old.css");
  assert.match(panel.querySelector(".reading-style-error").textContent, /could not load/);
  view.fetch = async () => json({error: "Invalid style"}, 400);
  change(view, form.elements.font_size, "19");
  await tick();
  assert.match(panel.querySelector(".reading-style-error").textContent, /Invalid style/);
  assert(pdf.href.endsWith("style=old"));
});

test("loading a profile fills controls and explicit update/create posts bind exact snapshot and CSRF", async () => {
  const {view, panel, form} = fixture();
  view.fetch = async () => json(snapshot("profile", 22));
  change(view, form.elements.style_profile, "1");
  await load(view);
  assert.equal(form.elements.font_size.value, "22");
  assert.equal(form.elements.italic_to_bold.checked, true);
  const save = panel.querySelector(".reading-style-save");
  assert.equal(save.elements.profile_id.value, "1");
  let posted;
  view.fetch = async (url, options) => {
    posted = options.body;
    return json({id: 1, name: "Comfort", default: "marxist"});
  };
  save.requestSubmit(save.querySelector("[value=update]"));
  await tick();
  assert.equal(posted.get("operation"), "update");
  assert.equal(posted.get("profile_id"), "1");
  assert.equal(posted.get("style"), "profile");
  assert.equal(posted.get("csrfmiddlewaretoken"), "csrf-fixture");
  save.elements.profile_name.value = "New name";
  view.fetch = async (url, options) => {
    posted = options.body;
    return json({id: 2, name: "New name", default: "marxist"});
  };
  save.requestSubmit(save.querySelector("[value=create]"));
  await tick();
  assert.equal(posted.get("operation"), "create");
  assert.equal(posted.get("profile_name"), "New name");
  assert.equal(form.elements.style_profile.value, "2");
  assert.equal(save.elements.profile_id.value, "2");
  assert.equal(new URL(view.location).searchParams.get("style_profile"), "2");
});

test("choosing a per-purpose font switches to Mixed and invalid input keeps the applied PDF", async () => {
  const {view, form, pdf, panel} = fixture();
  form.insertAdjacentHTML("beforeend", '<select name="font_mode"><option value="dyslexic">All</option>' +
    '<option value="mixed">Mixed</option></select><select name="body_font">' +
    '<option value="serif">Serif</option><option value="sans">Sans</option></select>');
  let requests = 0;
  view.fetch = async url => {
    requests++;
    assert.equal(new URL(url, view.location).searchParams.get("font_mode"), "mixed");
    return json(snapshot("mixed"));
  };
  change(view, form.elements.body_font, "sans");
  await load(view);
  assert.equal(form.elements.font_mode.value, "mixed");
  change(view, form.elements.font_size, "100");
  await tick();
  assert.equal(requests, 1);
  assert(pdf.href.endsWith("style=mixed"));
  assert.match(panel.querySelector(".reading-style-error").textContent, /highlighted settings/);
});

test("failure to bind the snapshot URL leaves the old stylesheet and PDF intact", async () => {
  const {view, form, pdf, panel} = fixture();
  view.fetch = async () => json(snapshot("new"));
  view.history.replaceState = () => { throw new Error("History update refused"); };
  change(view, form.elements.font_size, "18");
  await load(view);
  assert.equal(view.document.querySelector("[data-reading-style]").getAttribute("href"), "/old.css");
  assert(pdf.href.endsWith("style=old"));
  assert.match(panel.querySelector(".reading-style-error").textContent, /History update refused/);
});

test("a delayed profile save cannot relabel a newer live style as the saved profile", async () => {
  const {view, form, panel, pdf} = fixture();
  const save = panel.querySelector(".reading-style-save");
  let finishSave;
  view.fetch = (url, options) => options.method === "POST"
    ? new Promise(resolve => { finishSave = resolve; })
    : Promise.resolve(json(snapshot("newer")));
  save.elements.profile_name.value = "Saved earlier";
  save.requestSubmit(save.querySelector("[value=create]"));
  change(view, form.elements.font_size, "18");
  await load(view);
  assert.equal(save.querySelector("[value=create]").disabled, true);
  finishSave(json({id: 2, name: "Saved earlier", default: "marxist"}));
  await tick();
  assert.equal(form.elements.style_profile.value, "");
  assert.equal(save.elements.profile_id.value, "2");
  assert(pdf.href.endsWith("style=newer"));
  assert.match(panel.querySelector(".reading-style-status").textContent, /newer unsaved/);
});
