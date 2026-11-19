import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {mkdtempSync, readFileSync, rmSync, writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {pathToFileURL} from "node:url";
import test from "node:test";
import {JSDOM} from "jsdom";

// Run with node --test frontend/editor-surface.browser.test.js (requires Chromium).
test("the editor surface scrolls inside its desktop frame and follows the page in compact layouts", () => {
  const source = readFileSync(new URL("../library/templates/library/document_editor.html", import.meta.url), "utf8");
  const {document} = new JSDOM(source).window;
  const stage = document.querySelector(".editor-workspace-body");
  const css = ["reader.css", "workspace.css", "editor-pilot.css"].map(name =>
    readFileSync(new URL(`../library/static/library/${name}`, import.meta.url), "utf8")).join("\n");
  const cases = [
    {width: 1200, height: 800, count: 60},
    {width: 1200, height: 800, count: 1},
    {width: 761, height: 521, count: 60},
    {width: 760, height: 800, count: 60, natural: true},
    {width: 1200, height: 520, count: 60, natural: true},
  ];
  const fixture = ({count}, index) => {
    stage.querySelector("#editor-surface").innerHTML =
      `<div class="tiptap" contenteditable="true"><section class="editor-section-boundary">${
        "<p>Synthetic editor paragraph.</p>".repeat(count)
      }</section></div><article class="editor-generated-page">Metadata</article>`;
    return `<!doctype html><meta charset="utf-8"><style>${css}</style>${stage.outerHTML}<script>
      const stage = document.querySelector('.editor-workspace-body');
      const canvas = stage.querySelector('.editor-canvas');
      const frame = canvas.querySelector('.editor-surface-frame');
      const surface = frame.querySelector('#editor-surface');
      const metadata = surface.lastElementChild;
      const before = frame.getBoundingClientRect();
      const surfaceBounds = surface.getBoundingClientRect();
      const pageBefore = scrollY;
      surface.querySelector('[contenteditable]').focus({preventScroll: true});
      const focusedFrame = () => {
        const overlay = getComputedStyle(frame, '::after');
        return frame.matches(':focus-within') && overlay.borderTopWidth === '2px' &&
          overlay.pointerEvents === 'none' && frame.getBoundingClientRect().top === before.top;
      };
      const frameAtStart = focusedFrame();
      surface.scrollTop = (surface.scrollHeight - surface.clientHeight) / 2;
      const frameAtMiddle = focusedFrame();
      surface.scrollTop = surface.scrollHeight;
      const scrolled = surface.scrollTop > 0;
      const pageStayed = scrollY === pageBefore;
      const stationary = frameAtStart && frameAtMiddle && focusedFrame();
      if (!scrolled) metadata.scrollIntoView({block: 'end'});
      const limit = Math.min(innerHeight, surface.getBoundingClientRect().bottom);
      frameElement.dataset.result = JSON.stringify({
        index: ${index}, stage: stage.clientHeight, canvas: canvas.clientHeight,
        frame: frame.clientHeight, client: surface.clientHeight, scroll: surface.scrollHeight,
        contained: surfaceBounds.top >= before.top - 1 && surfaceBounds.bottom <= before.bottom + 1,
        overflow: getComputedStyle(surface).overflowY, scrolled, pageStayed, stationary,
        reached: metadata.getBoundingClientRect().bottom <= limit + 1, pageScrolled: scrollY > pageBefore,
      });
    </script>`;
  };
  const temp = mkdtempSync(join(tmpdir(), "reading-hub-geometry-"));
  try {
    const page = join(temp, "geometry.html");
    const escape = value => value.replaceAll("&", "&amp;").replaceAll('"', "&quot;");
    writeFileSync(page, "<!doctype html>" + cases.map((entry, index) =>
      `<iframe width="${entry.width}" height="${entry.height}" srcdoc="${escape(fixture(entry, index))}"></iframe>`
    ).join(""));
    const output = execFileSync(process.env.CHROMIUM || "chromium", [
      "--headless", "--disable-background-networking", `--user-data-dir=${join(temp, "profile")}`,
      "--dump-dom", pathToFileURL(page).href,
    ], {encoding: "utf8", timeout: 30000, stdio: ["ignore", "pipe", "ignore"]});
    const results = [...new JSDOM(output).window.document.querySelectorAll("iframe")]
      .map(frame => JSON.parse(frame.dataset.result));
    assert.equal(results.length, cases.length);
    for (const result of results) {
      const {index} = result;
      const {width, height, count, natural} = cases[index];
      const label = `${width}x${height}, ${count} paragraphs: ${JSON.stringify(result)}`;
      assert(result.contained && result.reached, label);
      if (natural) {
        assert(result.overflow === "visible" && !result.scrolled && result.pageScrolled, label);
      } else {
        assert.equal(result.stage, height - 16, label);
        assert(result.overflow === "auto" && result.stationary && result.pageStayed, label);
        assert.equal(result.scrolled, count > 1, label);
        assert.equal(result.scroll > result.client, count > 1, label);
      }
    }
  } finally {
    rmSync(temp, {recursive: true, force: true});
  }
});

test("surface block gaps and section insets share one spacing at 100% and 200% zoom", () => {
  const css = ["reader.css", "workspace.css", "editor-pilot.css"].map(name =>
    readFileSync(new URL(`../library/static/library/${name}`, import.meta.url), "utf8")).join("\n");
  const page = `<!doctype html><meta charset="utf-8"><style>
    ${css}
    body { margin: 0; }
    #editor-surface { width: 900px; }
  </style><main id="editor-surface">
    <section class="editor-generated-page" id="title">Title</section>
    <section class="editor-generated-page" id="toc"><span class="editor-page-break" role="separator" aria-label="Page break before table of contents">Page break</span>Contents</section>
    <div class="tiptap" contenteditable="true"><section class="editor-section-boundary"><span class="editor-section-edge editor-section-start">Section: One</span><h2>One</h2><p>First paragraph.</p><span class="editor-section-edge editor-section-end">End section: One</span></section><section class="editor-section-boundary"><span class="editor-section-edge editor-section-start">Section: Two</span><h2>Two</h2><p>Second paragraph.</p><span class="editor-section-edge editor-section-end">End section: Two</span></section></div>
    <section class="editor-generated-page" id="metadata">Metadata</section>
  </main><script>
    const surface = document.querySelector('#editor-surface');
    const results = [1, 2].map(zoom => {
      document.body.style.zoom = zoom;
      const currentPages = ['title', 'toc', 'metadata'].map(id =>
        document.querySelector('#' + id).getBoundingClientRect());
      const currentSections = [...document.querySelectorAll('.editor-section-boundary')]
        .map(section => section.getBoundingClientRect());
      const currentSurface = surface.getBoundingClientRect();
      const marker = document.querySelector('.editor-page-break');
      const gap = (before, after) => (after.top - before.bottom) / zoom;
      return {
        zoom,
        markerText: marker.textContent,
        markerLine: getComputedStyle(marker, '::before').borderTopStyle,
        gaps: [
          gap(currentPages[0], currentPages[1]),
          gap(currentPages[1], currentSections[0]),
          gap(currentSections[0], currentSections[1]),
          gap(currentSections[1], currentPages[2]),
        ],
        insets: [
          (currentPages[0].left - currentSurface.left) / zoom,
          (currentSections[0].left - currentSurface.left) / zoom,
        ],
      };
    });
    document.documentElement.dataset.results = JSON.stringify(results);
  </script>`;
  const temp = mkdtempSync(join(tmpdir(), "reading-hub-layout-"));
  try {
    const file = join(temp, "layout.html");
    writeFileSync(file, page);
    const output = execFileSync(process.env.CHROMIUM || "chromium", [
      "--headless", "--disable-background-networking", `--user-data-dir=${join(temp, "profile")}`,
      "--dump-dom", pathToFileURL(file).href,
    ], {encoding: "utf8", timeout: 30000, stdio: ["ignore", "pipe", "ignore"]});
    const result = JSON.parse(new JSDOM(output).window.document.documentElement.dataset.results);
    assert.deepEqual(result.map(entry => entry.zoom), [1, 2]);
    for (const entry of result) {
      assert.equal(entry.markerText, "Page break");
      assert.equal(entry.markerLine, "dashed");
      for (const distance of [...entry.gaps, ...entry.insets]) {
        assert(Math.abs(distance - 16) <= 1,
          `${entry.zoom * 100}% zoom should measure 16px, got ${distance}px in ${JSON.stringify(entry)}.`);
      }
    }
  } finally {
    rmSync(temp, {recursive: true, force: true});
  }
});

test("page-break markers sit outside page boxes and inside enclosing sections at 100% and 200% zoom", () => {
  const css = ["reader.css", "workspace.css", "editor-pilot.css"].map(name =>
    readFileSync(new URL(`../library/static/library/${name}`, import.meta.url), "utf8")).join("\n");
  const page = `<!doctype html><meta charset="utf-8"><style>
    ${css}
    body { margin: 0; }
    #editor-surface { width: 900px; }
    #editor-surface .tiptap { min-height: 20rem; }
  </style><main id="editor-surface">
    <section class="editor-generated-page" id="title">Title</section>
    <span class="editor-page-break editor-page-break-before-page" id="toc-break">Page break</span>
    <section class="editor-generated-page" id="toc">Contents</section>
    <div class="tiptap" contenteditable="true">
      <section class="editor-section-boundary" id="first"><h2>First</h2><p>Opening.</p></section>
      <span class="editor-page-break" id="section-break">Page break</span>
      <section class="editor-section-boundary" id="second">
        <span class="editor-page-break" id="heading-break">Page break</span>
        <h2 id="heading">Second</h2><p>Body.</p>
      </section>
    </div>
  </main><script>
    const surface = document.querySelector('#editor-surface');
    const results = [1, 2].map(zoom => {
      document.body.style.zoom = zoom;
      const rect = selector => document.querySelector(selector).getBoundingClientRect();
      const page = rect('#toc'), pageMarker = rect('#toc-break');
      const section = rect('#second'), sectionMarker = rect('#section-break');
      const content = rect('#heading'), headingMarker = rect('#heading-break');
      const scale = value => value / zoom;
      return {
        zoom,
        pageMarkerOutside: !document.querySelector('#toc-break').contains(document.querySelector('#toc')) &&
          document.querySelector('#toc-break').parentElement === surface,
        headingMarkerInside: document.querySelector('#heading-break').parentElement ===
          document.querySelector('#second'),
        pageAlignment: [scale(pageMarker.left - page.left), scale(pageMarker.right - page.right)],
        sectionAlignment: [scale(sectionMarker.left - section.left), scale(sectionMarker.right - section.right)],
        headingAlignment: [scale(headingMarker.left - content.left), scale(headingMarker.right - content.right)],
      };
    });
    document.documentElement.dataset.results = JSON.stringify(results);
  </script>`;
  const temp = mkdtempSync(join(tmpdir(), "reading-hub-break-geometry-"));
  try {
    const file = join(temp, "geometry.html");
    writeFileSync(file, page);
    const output = execFileSync(process.env.CHROMIUM || "chromium", [
      "--headless", "--disable-background-networking", `--user-data-dir=${join(temp, "profile")}`,
      "--dump-dom", pathToFileURL(file).href,
    ], {encoding: "utf8", timeout: 30000, stdio: ["ignore", "pipe", "ignore"]});
    const results = JSON.parse(new JSDOM(output).window.document.documentElement.dataset.results);
    assert.deepEqual(results.map(entry => entry.zoom), [1, 2]);
    for (const result of results) {
      assert(result.pageMarkerOutside && result.headingMarkerInside);
      for (const distance of [...result.pageAlignment, ...result.sectionAlignment, ...result.headingAlignment]) {
        assert(Math.abs(distance) <= 1,
          `${result.zoom * 100}% zoom marker alignment: ${JSON.stringify(result)}`);
      }
    }
  } finally {
    rmSync(temp, {recursive: true, force: true});
  }
});
