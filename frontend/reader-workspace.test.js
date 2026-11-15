import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";

let dom;
afterEach(() => {
  dom?.window.close();
  delete globalThis.window;
  delete globalThis.document;
  delete globalThis.Element;
  delete globalThis.ResizeObserver;
});

test("reader chrome stays in normal flow and Back to top targets the article", async () => {
  dom = new JSDOM(`<!doctype html><body>
    <header class="site-header"></header><nav class="review-navigation"></nav>
    <section class="work-context"></section><div class="reader-toolbar"></div>
    <article id="reader-article" tabindex="0"></article>
    <button id="reader-back-to-top" hidden>Back to top</button>
  </body>`, {pretendToBeVisual: true});
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.Element = dom.window.Element;
  globalThis.ResizeObserver = undefined;
  const owner = {scrollTop: 0, scrollTo(options) { this.lastScroll = options; }};
  Object.defineProperty(document, "scrollingElement", {value: owner});
  Object.defineProperty(window, "scrollY", {get: () => owner.scrollTop});
  window.scrollTo = options => {
    owner.lastScroll = options;
    owner.scrollTop = options.top;
  };
  Object.defineProperty(window, "innerHeight", {value: 800, configurable: true});
  await import(`../library/static/library/reader-workspace.js?test=${Date.now()}`);
  assert.equal(document.querySelectorAll(".reader-stack-marker").length, 0);

  owner.scrollTop = 801;
  window.dispatchEvent(new window.Event("scroll"));
  const button = document.querySelector("#reader-back-to-top");
  assert.equal(button.hidden, false);
  button.dispatchEvent(new window.MouseEvent("click", {bubbles: true, detail: 0}));
  assert.deepEqual(owner.lastScroll, {top: 0, behavior: "auto"});
  assert.equal(owner.scrollTop, 0);
  assert.equal(document.querySelector(".site-header").hasAttribute("data-compact"), false);
  assert.equal(document.querySelector(".work-context").hasAttribute("data-compact"), false);
  assert.equal(document.querySelector(".reader-toolbar").hasAttribute("data-compact"), false);
  assert.equal(button.hidden, true);
  assert.equal(document.activeElement.id, "reader-article");
});
