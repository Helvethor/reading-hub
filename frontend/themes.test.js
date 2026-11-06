import assert from "node:assert/strict";
import {test} from "node:test";
import {JSDOM} from "jsdom";
import {applyTheme, mountThemes} from "../library/static/library/themes.js";

const theme = {theme: "dark", stylesheet: "/static/marxist/dark.css"};
const tick = () => new Promise(resolve => setTimeout(resolve, 0));

function fixture() {
  return new JSDOM(`<!doctype html><head>
    <link rel="stylesheet" href="/paper.css" data-site-theme>
    <link rel="stylesheet" href="/reading.css?style=pinned" data-reading-style></head>
    <body><main><div contenteditable="true">Unsaved correction</div>
    <form action="/theme/" data-theme-form><input name="csrfmiddlewaretoken" value="csrf">
    <select name="theme"><option value="">Default</option><option value="dark">Dark</option></select>
    <button>Apply</button><span data-theme-error hidden></span></form></main></body>`,
    {url: "http://localhost/editor"});
}

test("theme and reading sheets switch atomically without changing pending content", async () => {
  const dom = fixture();
  const doc = dom.window.document;
  const markup = doc.querySelector("[contenteditable]").innerHTML;
  const promise = applyTheme(doc, theme);
  const staged = [...doc.querySelectorAll('link[media="not all"]')];
  assert.equal(staged.length, 2);
  assert.equal(new URL(staged[1].href).searchParams.get("style"), "pinned");
  staged[0].dispatchEvent(new dom.window.Event("load"));
  await tick();
  assert.equal(doc.querySelector("link[data-site-theme]").getAttribute("href"), "/paper.css");
  staged[1].dispatchEvent(new dom.window.Event("load"));
  await promise;
  assert.equal(doc.querySelector("link[data-site-theme]").getAttribute("href"), theme.stylesheet);
  assert.equal(doc.querySelector("[contenteditable]").innerHTML, markup);
  assert.equal(doc.querySelector("select").value, "dark");
  dom.window.close();
});

test("stylesheet failure retains both old sheets and reports the failure", async () => {
  const dom = fixture();
  const doc = dom.window.document;
  const promise = applyTheme(doc, theme);
  doc.querySelector('link[media="not all"]').dispatchEvent(new dom.window.Event("error"));
  await assert.rejects(promise, /stylesheet could not load/);
  assert.equal(doc.querySelectorAll("link").length, 2);
  assert.equal(doc.querySelector("link[data-site-theme]").getAttribute("href"), "/paper.css");
  dom.window.close();
});

test("a newer reading style wins while a theme refresh is loading", async () => {
  const dom = fixture();
  const doc = dom.window.document;
  const promise = applyTheme(doc, theme);
  const reading = doc.querySelector("link[data-reading-style]");
  const newer = reading.cloneNode();
  newer.href = "/new-reading.css?style=new";
  reading.replaceWith(newer);
  for (const sheet of doc.querySelectorAll('link[media="not all"]')) {
    sheet.dispatchEvent(new dom.window.Event("load"));
  }
  await promise;
  assert.equal(doc.querySelectorAll("link[data-reading-style]").length, 1);
  assert.equal(doc.querySelector("link[data-reading-style]").href, newer.href);
  dom.window.close();
});

test("theme changes synchronize settings controls and embedded panels without navigation", async () => {
  const dom = fixture();
  const doc = dom.window.document;
  const settings = doc.createElement("form");
  settings.dataset.userSettings = "";
  settings.innerHTML = '<select name="theme"><option value="">Default</option><option value="dark">Dark</option></select>';
  doc.querySelector("main").append(settings);
  const frame = doc.createElement("iframe");
  doc.querySelector("main").append(frame);
  let message;
  frame.contentWindow.postMessage = (data, origin) => { message = {data, origin}; };
  const promise = applyTheme(doc, theme);
  for (const sheet of doc.querySelectorAll('link[media="not all"]')) {
    sheet.dispatchEvent(new dom.window.Event("load"));
  }
  await promise;
  assert.equal(settings.elements.theme.value, "dark");
  assert.deepEqual(message, {
    data: {type: "reading-hub-theme", theme}, origin: "http://localhost",
  });
  assert.equal(dom.window.location.pathname, "/editor");
  dom.window.close();
});

test("header saves via CSRF form and displays server errors without reloading", async () => {
  const dom = fixture();
  const {window: view} = dom;
  let submitted;
  view.fetch = async (url, options) => {
    submitted = {url, options};
    return {ok: false, headers: new Map([["content-type", "application/json"]]),
      json: async () => ({error: "Choose an available theme."})};
  };
  mountThemes(view.document);
  const form = view.document.querySelector("form");
  form.dispatchEvent(new view.Event("submit", {cancelable: true}));
  await tick();
  assert.equal(submitted.options.body.get("csrfmiddlewaretoken"), "csrf");
  assert.equal(form.querySelector("[data-theme-error]").textContent, "Choose an available theme.");
  assert.equal(form.querySelector("button").disabled, false);
  assert.equal(view.location.pathname, "/editor");
  dom.window.close();
});
