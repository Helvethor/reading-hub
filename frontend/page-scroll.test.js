import assert from "node:assert/strict";
import {test} from "node:test";
import {JSDOM} from "jsdom";
import {
  scrollElementIntoView, visibleBand,
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
