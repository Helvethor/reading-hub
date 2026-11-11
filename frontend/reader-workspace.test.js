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

test("reader navigation compacts as a stack and Back to top targets the article", async () => {
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
  window.matchMedia = () => ({matches: false});

  const owner = {scrollTop: 0, scrollTo(options) { this.lastScroll = options; }};
  Object.defineProperty(document, "scrollingElement", {value: owner});
  Object.defineProperty(window, "innerHeight", {value: 800, configurable: true});
  const offsets = new Map([
    [".site-header", 0],
    [".review-navigation", 100],
    [".work-context", 160],
    [".reader-toolbar", 250],
  ]);
  for (const [selector, offset] of offsets) {
    const element = document.querySelector(selector);
    element.getBoundingClientRect = () => ({
      height: element.dataset.compact === "true"
        ? selector === ".site-header" ? 40 : 30
        : selector === ".site-header" ? 80 : selector === ".work-context" ? 60 : 40,
    });
  }
  const originalRect = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function() {
    const markerIndex = [...offsets.keys()].findIndex(selector =>
      document.querySelector(selector)?.nextElementSibling === this
      || document.querySelector(selector)?.previousElementSibling === this);
    if (markerIndex >= 0) {
      const offset = [...offsets.values()][markerIndex];
      return {bottom: offset - owner.scrollTop};
    }
    return originalRect.call(this);
  };

  await import(`../library/static/library/reader-workspace.js?test=${Date.now()}`);
  assert.equal(document.body.classList.contains("reader-page"), true);
  assert.equal(document.querySelectorAll(".reader-stack-marker").length, 8);

  owner.scrollTop = 300;
  window.dispatchEvent(new window.Event("scroll"));
  assert.equal(document.querySelector(".site-header").dataset.compact, "true");
  assert.equal(document.querySelector(".work-context").dataset.compact, "true");
  assert.equal(document.querySelector(".reader-toolbar").dataset.compact, "true");
  assert.equal(document.querySelector(".site-header").nextElementSibling.style.height, "40px");
  assert.equal(document.documentElement.style.getPropertyValue("--reader-stack-height"), "140px");

  owner.scrollTop = 800;
  window.dispatchEvent(new window.Event("scroll"));
  const button = document.querySelector("#reader-back-to-top");
  assert.equal(button.hidden, false);
  button.dispatchEvent(new window.MouseEvent("click", {bubbles: true, detail: 0}));
  assert.deepEqual(owner.lastScroll, {top: 0, behavior: "smooth"});
  assert.equal(document.activeElement.id, "reader-article");
});
