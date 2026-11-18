import assert from "node:assert/strict";
import {test} from "node:test";
import {JSDOM} from "jsdom";
import {
  focusWithViewportReveal, isInViewport, preservePagePosition, scrollElementIntoView, visibleBand,
} from "./page-scroll.js";

test("content targets scroll their marked pane without moving the page or reserving chrome", () => {
  const dom = new JSDOM(`<section id="unified-workspace">
    <div id="pane" data-workspace-scroll-pane><h2 id="target">Target</h2></div>
  </section>`);
  const {document, window} = dom.window;
  const pane = document.querySelector("#pane");
  const target = document.querySelector("#target");
  Object.defineProperties(window, {
    innerHeight: {value: 600, configurable: true},
    scrollY: {value: 0, configurable: true},
  });
  let pageScrolls = 0;
  window.scrollTo = () => { pageScrolls++; };
  Object.defineProperties(pane, {
    clientHeight: {value: 300},
    clientTop: {value: 0},
  });
  pane.getBoundingClientRect = () => ({top: 100, bottom: 400, height: 300});
  target.getBoundingClientRect = () => ({top: 450, bottom: 500, height: 50});
  pane.scrollTop = 10;

  scrollElementIntoView(target, 8);

  assert.equal(pane.scrollTop, 118);
  assert.equal(pageScrolls, 0);
  assert.deepEqual(visibleBand(pane), {top: 100, bottom: 400});
  dom.window.close();
});

test("a pane itself scrolls into the viewport without a stack offset", () => {
  const dom = new JSDOM(`<section id="unified-workspace">
    <div id="pane" data-workspace-scroll-pane></div>
  </section>`);
  const {document, window} = dom.window;
  const pane = document.querySelector("#pane");
  Object.defineProperty(window, "scrollY", {value: 20, configurable: true});
  let pageTop;
  window.scrollTo = ({top}) => { pageTop = top; };
  pane.getBoundingClientRect = () => ({top: 300, bottom: 600, height: 300});

  scrollElementIntoView(pane, 8);

  assert.equal(pageTop, 312);
  dom.window.close();
});

test("focus does not scroll an already visible target but permits native reveal otherwise", () => {
  const dom = new JSDOM(
    '<div data-workspace-scroll-pane><button>Tab</button></div>',
  );
  const {document, window} = dom.window;
  const pane = document.querySelector("[data-workspace-scroll-pane]");
  const target = document.querySelector("button");
  Object.defineProperties(window, {
    innerWidth: {value: 600, configurable: true},
    innerHeight: {value: 400, configurable: true},
  });
  Object.defineProperties(pane, {
    clientHeight: {value: 400, configurable: true},
    clientWidth: {value: 600, configurable: true},
  });
  pane.getBoundingClientRect = () => ({
    top: 0, bottom: 400, left: 0, right: 600, height: 400, width: 600,
  });
  let options;
  target.focus = value => { options = value; };
  target.getBoundingClientRect = () => ({
    top: 20, bottom: 60, left: 30, right: 100,
  });
  focusWithViewportReveal(target);
  assert.deepEqual(options, {preventScroll: true});

  target.getBoundingClientRect = () => ({
    top: 420, bottom: 460, left: 30, right: 100,
  });
  focusWithViewportReveal(target);
  assert.deepEqual(options, {preventScroll: false});

  pane.getBoundingClientRect = () => ({
    top: 100, bottom: 300, left: 50, right: 450, height: 200, width: 400,
  });
  Object.defineProperties(pane, {
    clientHeight: {value: 200, configurable: true},
    clientWidth: {value: 400, configurable: true},
  });
  target.getBoundingClientRect = () => ({
    top: 80, bottom: 110, left: 60, right: 100,
  });
  assert.equal(isInViewport(target), false, "Pane clipping counts as offscreen.");
  focusWithViewportReveal(target);
  assert.deepEqual(options, {preventScroll: false});
  dom.window.close();
});

test("page preservation restores a feasible offset and leaves a native clamp alone", () => {
  const dom = new JSDOM("<main></main>");
  const {window} = dom;
  const page = {top: 500, max: 1000, calls: []};
  Object.defineProperty(window, "scrollY", {get: () => page.top});
  window.scrollTo = ({top}) => {
    page.calls.push(top);
    page.top = Math.max(0, Math.min(top, page.max));
  };

  preservePagePosition(window, () => { page.top = 300; });
  assert.equal(page.top, 500);
  assert.deepEqual(page.calls, [500]);

  page.top = 760;
  page.max = 240;
  preservePagePosition(window, () => { page.top = Math.min(page.top, page.max); });
  assert.equal(page.top, 240);
  assert.deepEqual(page.calls, [500, 760]);
  page.max = 1200;
  assert.equal(page.top, 240);
  dom.window.close();
});

test("start navigation top-aligns both visible and offscreen targets in the pane", () => {
  const dom = new JSDOM(`<div data-workspace-scroll-pane><h2>Target</h2></div>`);
  const {document, window} = dom.window;
  const pane = document.querySelector("div");
  const target = document.querySelector("h2");
  Object.defineProperties(pane, {
    clientHeight: {value: 300},
    clientTop: {value: 2},
  });
  window.scrollTo = () => assert.fail("An onscreen pane must not move the page.");
  let frame;
  window.requestAnimationFrame = callback => { frame = callback; };
  pane.getBoundingClientRect = () => ({top: 100, bottom: 404, height: 304});
  for (const targetTop of [180, 700]) {
    pane.scrollTop = 40;
    const contentOffset = targetTop + pane.scrollTop;
    target.getBoundingClientRect = () => ({
      top: contentOffset - pane.scrollTop,
      bottom: contentOffset - pane.scrollTop + 20,
      height: 20,
    });
    scrollElementIntoView(target, 0, "start");
    assert.equal(target.getBoundingClientRect().top, 102);
    frame();
    assert.equal(target.getBoundingClientRect().top, 102);
  }
  dom.window.close();
});
