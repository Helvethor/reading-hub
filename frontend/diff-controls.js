import {createBoundedEditor} from "./editor.js";
import {showDocumentDifferences, currentDifferences} from "./document-diffs.js";

export function mountDifferenceControls(form, editor, initial, showError) {
  const owner = form.ownerDocument;
  const toggle = form.querySelector("#editor-diff-toggle");
  const revision = form.querySelector("#editor-diff-revision");
  const status = form.querySelector("#editor-diff-status");
  const announcement = form.querySelector("#editor-diff-announcement");
  if (!toggle || !revision || !status || !announcement) {
    for (const control of [toggle, revision]) {
      if (control) control.disabled = true;
    }
    showError("Content differences are unavailable because the editor page and JavaScript " +
      "do not match. Restart the web server to reload its cached templates, then reload " +
      "this page. Other editing remains available; saved editions and drafts are unchanged.");
    return null;
  }
  let baseline, baselineRevision = 0, pending = 0, diffEnabled = false;
  const baselineLabel = number => number === 0
    ? "the pinned starting document" : `saved revision ${number}`;
  function parse(value) {
    const candidate = createBoundedEditor(owner.createElement("div"), value.html);
    try { return editor.schema.nodeFromJSON(candidate.state.doc.toJSON()); }
    finally { candidate.destroy(); }
  }
  baseline = parse(initial.baseline_document || initial.document);
  function updateToggle() {
    const action = diffEnabled ? "Show result" : "Show differences";
    toggle.setAttribute("aria-label", action);
    toggle.title = action;
    toggle.setAttribute("aria-pressed", String(diffEnabled));
  }
  function report(announce = false) {
    const selected = Number(revision.value);
    if (baselineRevision === null) {
      status.textContent = `Comparison with ${baselineLabel(selected)} is not loaded.`;
    } else {
      const differences = currentDifferences(editor);
      const selectedNotice = selected === baselineRevision ? "" :
        ` Selected ${baselineLabel(selected)} is not loaded.`;
      status.textContent = `Loaded baseline: ${baselineLabel(baselineRevision)}.${selectedNotice} ` +
        (diffEnabled ? `${differences.length} changed range(s).` : "Result view; differences are off.");
    }
    if (announce) announcement.textContent = status.textContent;
  }
  function apply(announce = false) {
    showDocumentDifferences(editor, baseline, diffEnabled);
    updateToggle();
    report(announce);
  }
  toggle.addEventListener("click", () => {
    diffEnabled = !diffEnabled;
    apply(true);
  });
  revision.addEventListener("change", async () => {
    const number = Number(revision.value);
    if (!Number.isInteger(number) || number < 0 || number > initial.revision ||
        revision.value === "") {
      showError(`Choose a saved baseline revision from 0 to ${initial.revision}.`);
      return;
    }
    if (number === baselineRevision) {
      apply(true);
      return;
    }
    if (!initial.draft) {
      if (number !== 0) {
        showError("Save a corrected version before selecting another baseline.");
        revision.value = String(baselineRevision);
        return;
      }
      baseline = parse(initial.baseline_document || initial.document);
      baselineRevision = 0;
      showError("");
      apply(true);
      return;
    }
    const request = ++pending;
    const draft = initial.draft;
    baseline = null;
    baselineRevision = null;
    showDocumentDifferences(editor, null, false);
    status.textContent = `Loading ${baselineLabel(number)}…`;
    revision.setAttribute("aria-busy", "true");
    announcement.textContent = status.textContent;
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
      if (request !== pending || initial.draft !== draft || Number(revision.value) !== number) return;
      baseline = parse(value.document);
      baselineRevision = number;
      showError("");
      apply(true);
    } catch (failure) {
      if (request !== pending || Number(revision.value) !== number) return;
      baseline = null;
      baselineRevision = null;
      showDocumentDifferences(editor, null, false);
      report(true);
      showError(failure.message);
    } finally {
      if (request === pending) revision.removeAttribute("aria-busy");
    }
  });
  editor.on("update", () => report());
  function refresh() {
    const selected = Number(revision.value);
    const lastRevision = initial.draft ? initial.revision : 0;
    revision.replaceChildren(new owner.defaultView.Option("Pinned starting version", "0"));
    for (let number = 1; number <= lastRevision; number++) {
      revision.add(new owner.defaultView.Option(`Saved version ${number}`, String(number)));
    }
    revision.value = String(Number.isInteger(selected) && selected <= lastRevision ? selected : 0);
    report();
  }
  refresh();
  updateToggle();
  return {refresh};
}
