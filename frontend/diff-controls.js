import {createBoundedEditor} from "./editor.js";
import {showDocumentDifferences, currentDifferences} from "./document-diffs.js";

export function mountDifferenceControls(form, editor, initial, showError) {
  const owner = form.ownerDocument;
  const filter = form.querySelector("#editor-result-filter");
  const revision = form.querySelector("#editor-diff-revision");
  const load = form.querySelector("#editor-diff-baseline");
  const status = form.querySelector("#editor-diff-status");
  if (!filter || !revision || !load || !status) {
    for (const control of [filter, revision, load]) {
      if (control) control.disabled = true;
    }
    showError("Content differences are unavailable because the editor page and JavaScript " +
      "do not match. Restart the web server to reload its cached templates, then reload " +
      "this page. Other editing remains available; saved editions and drafts are unchanged.");
    return null;
  }
  let baseline, baselineRevision = 0, pending = 0;
  function parse(value) {
    const candidate = createBoundedEditor(owner.createElement("div"), value.html);
    try { return editor.schema.nodeFromJSON(candidate.state.doc.toJSON()); }
    finally { candidate.destroy(); }
  }
  baseline = parse(initial.baseline_document || initial.document);
  function report() {
    const differences = currentDifferences(editor);
    status.textContent = filter.value === "result"
      ? "Result view. Differences never change saved content."
      : `Content differences against ${baselineRevision === 0 ? "the pinned starting document" :
        `saved revision ${baselineRevision}`}. ${differences.length} changed range(s). ` +
        "Green = added; red = removed. Restoration is an unsaved, undoable edit. " +
        "Metadata comparison is available in Saved comparison.";
  }
  function apply() {
    showDocumentDifferences(editor, baseline, filter.value === "diffs");
    report();
  }
  filter.addEventListener("change", () => {
    try { apply(); }
    catch (failure) { filter.value = "result"; showDocumentDifferences(editor, baseline, false); showError(failure.message); }
  });
  load.addEventListener("click", async () => {
    const number = Number(revision.value);
    if (!Number.isInteger(number) || number < 0 || number > initial.revision || revision.value === "") {
      showError(`Choose a saved baseline revision from 0 to ${initial.revision}.`);
      return;
    }
    if (!initial.draft) {
      if (number === 0) { baselineRevision = 0; apply(); }
      else showError("Save a corrected version before selecting another baseline.");
      return;
    }
    const request = ++pending;
    const draft = initial.draft;
    load.disabled = true;
    try {
      const url = new URL(form.dataset.baselineUrl, location.href);
      url.searchParams.set("draft", draft);
      url.searchParams.set("revision", number);
      const response = await fetch(url, {headers: {Accept: "application/json"}});
      if (!response.headers.get("Content-Type")?.includes("application/json")) {
        throw new Error(`Baseline could not be loaded (${response.status}).`);
      }
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || `Baseline could not be loaded (${response.status}).`);
      if (request !== pending || initial.draft !== draft) return;
      baseline = parse(value.document);
      baselineRevision = number;
      showError("");
      apply();
    } catch (failure) { showError(failure.message); }
    finally { if (request === pending) load.disabled = false; }
  });
  editor.on("update", report);
  function refresh() {
    revision.max = String(initial.revision);
    report();
  }
  refresh();
  return {refresh};
}
