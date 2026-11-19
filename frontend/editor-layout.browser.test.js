import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {mkdtemp, rm, writeFile} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {fileURLToPath, pathToFileURL} from "node:url";
import {test} from "node:test";

const root = fileURLToPath(new URL("../", import.meta.url));
const browser = process.env.CHROMIUM_BIN || "chromium";
const widths = [1440, 640, 390];

function stylesheetHref(relativePath) {
  return pathToFileURL(path.join(root, relativePath)).href;
}

function fixture(themePath) {
  const stylesheets = [
    "library/static/library/app.css",
    "library/static/library/workspace.css",
    "library/static/library/editor-pilot.css",
    themePath,
    "profiles/static/marxist/square-ui.css",
  ].map(file => `<link rel="stylesheet" href="${stylesheetHref(file)}">`).join("");
  const formatButtons = Array.from({length: 19}, (_, index) =>
    `<button type="button"${index === 0 ? ' disabled' : ""}>Format ${index + 1}</button>`,
  ).join("");
  const outlineButtons = [
    "Add / restore section…",
    "New empty section…",
    "Move section…",
    "Section boundary…",
    "Target ID…",
    "Use work-type layout defaults",
    "Expand outline",
  ].map(label => `<button type="button">${label}</button>`).join("");

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">${stylesheets}</head>
<body><main class="page-container editor-page">
  <div class="editor-workspace" data-editor-tab="editor">
    <div class="editor-pilot-toolbar workspace-command-bar"><button type="button">Editor action</button></div>
    <div class="editor-command-area"><div class="editor-command-panels">
      <div class="editor-command-panel" id="format">
        <div class="editor-format-toolbar workspace-command-bar workspace-joined-controls" role="group">${formatButtons}</div>
      </div>
      <div class="editor-command-panel" id="outline" hidden>
        <div class="editor-outline-toolbar workspace-command-bar workspace-joined-controls" role="group">${outlineButtons}</div>
      </div>
      <div class="editor-command-panel" id="diff" hidden>
        <div class="editor-diff-controls workspace-command-bar" role="group"><button type="button">Diff</button><label>Compare with <select><option>Starting version</option></select></label><span id="editor-diff-status"></span></div>
      </div>
    </div></div>
  </div>
</main>
<pre id="browser-result"></pre>
<script>
window.addEventListener("load", () => {
  const px = value => Number.parseFloat(value);
  const box = element => {
    const rect = element.getBoundingClientRect();
    return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, height: rect.height};
  };
  const rows = element => {
    const groups = [];
    for (const button of element.querySelectorAll("button")) {
      const rect = box(button);
      let row = groups.find(candidate => Math.abs(candidate.top - rect.top) < 0.1);
      if (!row) {
        row = {top: rect.top, bottom: rect.bottom, buttons: []};
        groups.push(row);
      }
      row.bottom = Math.max(row.bottom, rect.bottom);
      row.buttons.push(rect);
    }
    return groups.sort((left, right) => left.top - right.top).map(row => ({
      top: row.top,
      bottom: row.bottom,
      gaps: row.buttons.slice(1).map((button, index) => button.left - row.buttons[index].right),
    }));
  };
  const commandBars = [...document.querySelectorAll(".editor-command-panel")].map(panel => {
    panel.hidden = false;
    const toolbar = panel.querySelector(".workspace-command-bar");
    const style = getComputedStyle(toolbar);
    const padding = ["Top", "Right", "Bottom", "Left"].map(side => px(style["padding" + side]));
    const measurement = {
      id: panel.id,
      wrapperPadding: ["Top", "Right", "Bottom", "Left"].map(side =>
        px(getComputedStyle(panel)["padding" + side])),
      padding,
    };
    if (panel.id !== "diff") {
      measurement.gap = px(getComputedStyle(toolbar).gap);
      measurement.alignItems = getComputedStyle(toolbar).alignItems;
      measurement.rows = rows(toolbar);
    }
    return measurement;
  });
  const pilot = getComputedStyle(document.querySelector(".editor-pilot-toolbar"));
  const result = {
    width: document.documentElement.clientWidth,
    pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    pilotPadding: ["Top", "Right", "Bottom", "Left"].map(side => px(pilot["padding" + side])),
    commandBars,
  };
  document.querySelector("#browser-result").textContent = JSON.stringify(result);
});
</script></body></html>`;
}

async function measure(themePath, width) {
  const directory = await mkdtemp(path.join(os.tmpdir(), "reading-hub-editor-layout-"));
  try {
    const htmlPath = path.join(directory, "fixture.html");
    await writeFile(htmlPath, fixture(themePath));
    const run = spawnSync(browser, [
      "--headless",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-dev-shm-usage",
      "--allow-file-access-from-files",
      `--window-size=${width},900`,
      "--dump-dom",
      pathToFileURL(htmlPath).href,
    ], {encoding: "utf8", timeout: 30000});
    assert.equal(run.error, undefined, `Unable to run ${browser}: ${run.error?.message}`);
    assert.equal(run.status, 0, `Chromium failed: ${run.stderr}`);
    const serialized = run.stdout.match(/<pre id="browser-result">([^<]*)<\/pre>/)?.[1];
    assert.ok(serialized, `Chromium did not return layout measurements: ${run.stdout}`);
    return JSON.parse(serialized);
  } finally {
    await rm(directory, {recursive: true, force: true});
  }
}

function assertThreePixelGaps(rows, context, expectWrap) {
  if (expectWrap) {
    assert.ok(rows.length > 1,
      `${context} should wrap onto multiple rows; rendered rows: ${JSON.stringify(rows)}`);
  }
  assert.ok(rows.some(row => row.gaps.length > 0), `${context} needs adjacent controls to measure`);
  for (const [rowIndex, row] of rows.entries()) {
    for (const [gapIndex, gap] of row.gaps.entries()) {
      assert.ok(Math.abs(gap - 3) < 0.1,
        `${context} row ${rowIndex + 1} gap ${gapIndex + 1} was ${gap}px`);
    }
    if (rowIndex > 0) {
      const verticalGap = row.top - rows[rowIndex - 1].bottom;
      assert.ok(Math.abs(verticalGap - 3) < 0.1,
        `${context} row gap ${rowIndex} was ${verticalGap}px`);
    }
  }
}

for (const [theme, themePath] of [
  ["Marxist Paper", "profiles/static/marxist/theme.css"],
  ["Marxist Dark", "profiles/static/marxist/dark.css"],
]) {
  test(`${theme} editor command bars keep measured spacing and insets`, async () => {
    for (const width of widths) {
      const result = await measure(themePath, width);
      assert.equal(result.pageOverflow, false, `${theme} page overflowed at ${width}px`);
      assert.deepEqual(result.pilotPadding, [8, 8, 8, 8]);
      assert.deepEqual(result.commandBars.map(bar => bar.wrapperPadding), [
        [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0],
      ]);
      for (const bar of result.commandBars) {
        assert.deepEqual(bar.padding, [8, 8, 8, 8], `${bar.id} padding at ${width}px`);
        assert.deepEqual(bar.padding, result.pilotPadding,
          `${bar.id} content inset differs from the editor command bar at ${width}px`);
      }
      for (const bar of result.commandBars.filter(candidate => candidate.id !== "diff")) {
        assert.equal(bar.gap, 3, `${bar.id} gap at ${width}px`);
        assert.equal(bar.alignItems, "stretch", `${bar.id} alignment at ${width}px`);
      }
      for (const bar of result.commandBars.filter(candidate => candidate.id !== "diff")) {
        assertThreePixelGaps(bar.rows, `${theme} ${bar.id} at ${width}px`, width < 700);
      }
    }
  });
}
