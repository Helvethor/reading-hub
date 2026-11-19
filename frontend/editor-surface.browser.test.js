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
