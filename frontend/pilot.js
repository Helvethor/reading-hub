import "prosemirror-view/style/prosemirror.css";
import {
  applyPlainTextPaste, applyFormattedPaste, createBoundedEditor,
} from "./editor.js";
import {mountWorkspace} from "./controls.js";
import {documentParts, showDocumentPart} from "./workspace.js";
import {mountSourcePanel} from "./source-insertion.js";
import {mountMetadata} from "./metadata.js";
import {textFields} from "./metadata-fields.js";
import {mountDifferenceControls} from "./diff-controls.js";
import {mountWorkflowPanels} from "./workflow-panels.js";
import {mountEditorTabs} from "./editor-tabs.js";
import {mountWorkspaceShell} from "./workspace-shell.js";

const form = document.querySelector("#document-editor");
if (form) {
  mountEditorTabs(form);
  const initial = JSON.parse(document.querySelector("#document-editor-initial").textContent);
  const status = document.querySelector("#editor-status");
  const error = document.querySelector("#editor-error");
  const surface = document.querySelector("#editor-surface");
  const restore = document.querySelector("#editor-restore");
  const publication = document.querySelector("#editor-publication");
  const comparison = document.querySelector("#editor-comparison");
  const historyLink = document.querySelector("#editor-history");
  const markReviewed = document.querySelector("#editor-mark-reviewed");
  const title = form.elements.title;
  const metadataFields = ["author", "subtitle", "work_type", ...textFields.map(([name]) => name), "language",
    "original_language"].map(name => form.elements[name]).filter(Boolean);
  const sectionList = document.querySelector("#editor-sections");
  const pasteDialog = document.querySelector("#editor-paste");
  const pasteText = document.querySelector("#editor-paste-text");
  const pasteReplaced = document.querySelector("#editor-paste-replaced");
  const pasteNotice = document.querySelector("#editor-paste-notice");
  const pasteFormatted = document.querySelector("#editor-paste-formatted");
  const pasteFormatStatus = document.querySelector("#editor-paste-format-status");
  const pasteFormatInsert = document.querySelector("#editor-paste-insert-formatted");
  let pendingPaste = null;
  let storageKey = `${form.dataset.recoveryKey}:${initial.draft || initial.approval_digest}`;
  let editor, dirty = false, saving = false, workspaceShell = null;
  let recoverable = null;
  let structuredMetadata = null;
  let sourceTickets = [];
  let workspace = null;
  let differences = null;
  const metadata = () => {
    const result = {...initial.document.metadata};
    for (const field of metadataFields) {
      const value = field.value.trim();
      if (value) result[field.name] = field.name.endsWith("language")
        ? value.replaceAll("_", "-")
        : value;
      else delete result[field.name];
    }
    if (result.author) result.author_is_fallback = false;
    else if (initial.document.metadata.author_is_fallback === true) {
      result.author_is_fallback = true;
    } else delete result.author_is_fallback;
    return structuredMetadata ? structuredMetadata.read(result) : result;
  };
  const documentValue = () => ({
    ...initial.document, title: title.value.trim(), metadata: metadata(), html: editor.getHTML(),
  });
  const reviewValue = () => form.querySelector('[name="review"]:checked').value;
  const sectionsValue = () => [...sectionList.querySelectorAll('input[type="checkbox"]:checked')]
    .map(input => input.value);
  const formPayload = () => ({
    document: documentValue(), review: reviewValue(), verified_sections: sectionsValue(),
    editorial: form.elements.editorial.checked,
    source_tickets: sourceTickets,
  });
  function showError(message) { error.textContent = message; }
  function selectReview(value) {
    const choice = [...form.querySelectorAll('[name="review"]')]
      .find(input => input.value === value);
    if (!choice) throw new Error("Choose a valid review scope.");
    choice.checked = true;
    sectionList.hidden = value !== "sections";
  }
  function refreshSections(selected = sectionsValue()) {
    const labels = new Map();
    for (const section of documentParts(editor.state.doc)) {
      if (section.kind === "Section" && section.id && !labels.has(section.id)) {
        labels.set(section.id, `${section.label.slice(0, 100)} — #${section.id}`);
      }
    }
    const ids = [...labels.keys()];
    sectionList.replaceChildren();
    if (!ids.length) {
      const message = document.createElement("p");
      message.textContent = "This document has no identified sections to verify individually.";
      sectionList.append(message);
    }
    for (const id of ids) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = id;
      input.checked = selected.includes(id);
      input.addEventListener("change", remember);
      label.append(input, document.createTextNode(` ${labels.get(id)}`));
      sectionList.append(label);
    }
  }
  function populateMetadata(value) {
    for (const field of metadataFields) field.value = value[field.name] || "";
    structuredMetadata?.populate(value);
  }
  function updatePublication() {
    if (markReviewed) {
      markReviewed.disabled = dirty || saving || !initial.draft || initial.saved_review === "full";
    }
    if (historyLink && initial.draft) {
      const url = new URL(historyLink.href);
      url.searchParams.set("draft", initial.draft);
      historyLink.href = url.href;
    }
    if (comparison) {
      comparison.hidden = !initial.draft;
      if (!comparison.hidden) {
        const url = new URL(form.dataset.comparisonUrl, location.href);
        url.searchParams.set("draft", initial.draft);
        url.searchParams.set("to", initial.revision);
        comparison.href = url.href;
      }
    }
    publication.hidden = dirty || saving || !initial.draft || !initial.revision;
    if (!publication.hidden) {
      const url = new URL(form.dataset.publicationUrl, location.href);
      url.searchParams.set("draft", initial.draft);
      url.searchParams.set("revision", initial.revision);
      publication.href = url.href;
    }
  }
  function remember() {
    dirty = true;
    updatePublication();
    workspaceShell?.updateState({
      draft: initial.draft, revision: initial.revision, dirty,
    });
    status.textContent = "Unsaved edits. The original edition is unchanged.";
    try {
      sessionStorage.setItem(storageKey, JSON.stringify({
        revision: initial.revision, ...formPayload(),
      }));
    } catch (failure) {
      showError(`Unsaved edits remain in memory, but tab recovery failed: ${failure.message}`);
    }
  }
  try {
    editor = createBoundedEditor(surface, initial.document.html, update => {
      if (update.error) { showError(update.error); return; }
      if (update.paste) {
        showError("");
        pendingPaste = update.paste;
        pasteText.textContent = pendingPaste.text;
        pasteReplaced.textContent = pendingPaste.replacedText || "(Insertion at the cursor.)";
        pasteNotice.textContent = "Nothing is inserted until you choose an insertion option. Plain text and formatted text can differ; review the chosen preview.";
        pasteFormatted.replaceChildren();
        pasteFormatInsert.hidden = !pendingPaste.formatted;
        pasteFormatStatus.textContent = pendingPaste.formatted
          ? pendingPaste.formatted.multiBlock
            ? `${pendingPaste.formatted.paragraphs} paragraphs will be inserted between the two split halves of the current paragraph. Both halves remain, even if empty; the original paragraph ID stays on the first half. Pasted paragraphs do not inherit its styles.`
            : "Supported inline formatting is available. No surrounding styles, IDs or note targets are inherited."
          : pendingPaste.hasFormatting
            ? `Formatted paste unavailable: ${pendingPaste.formatError} You can still choose plain text.`
            : "No clipboard HTML is available. Only plain text can be inserted.";
        if (pendingPaste.formatted) {
          const preview = document.createElement("template");
          preview.innerHTML = pendingPaste.formatted.html;
          pasteFormatted.append(preview.content);
        }
        pasteDialog.showModal();
        return;
      }
      if (update.editor) {
        selectReview("partial");
        refreshSections([]);
      }
      remember();
    });
    for (const control of form.querySelectorAll("[disabled]")) control.disabled = false;
    differences = mountDifferenceControls(form, editor, initial, showError);
    mountWorkflowPanels({
      form, showError, isDirty: () => dirty,
      chooseHistory: false, historyUrl: historyLink.href,
    });
    mountSourcePanel(form, editor, showError, () => initial.draft);
    workspaceShell = mountWorkspaceShell({
      form,
      getSnapshot: () => ({
        draft: initial.draft,
        revision: initial.revision,
        document: dirty ? documentValue() : initial.document,
        source_tickets: sourceTickets,
      }),
      initialDraft: initial.draft,
      initialRevision: initial.revision,
      initialChooseHistory: initial.choose_history === true,
    });
    status.textContent = `Fidelity check passed. Saved draft revision: ${initial.revision}.`;
    function updateSavedReview() {
      document.querySelector("#editor-saved-review").textContent = initial.saved_review
        ? `Current saved revision ${initial.revision}: ${initial.saved_review}` +
          (initial.saved_verified_sections.length
            ? ` (${initial.saved_verified_sections.join(", ")})` : ".")
        : "No saved revision yet. A new revision starts as partial review.";
    }
    updateSavedReview();
    selectReview("partial");
    refreshSections([]);
    form.querySelector('[name="review"][value="partial"]').addEventListener("change", remember);
    form.querySelector('[name="review"][value="sections"]').addEventListener("change", () => {
      sectionList.hidden = false;
      remember();
    });
    form.querySelector('[name="review"][value="full"]').addEventListener("change", remember);
    form.elements.editorial.checked = initial.editorial;
    form.elements.editorial.addEventListener("change", remember);
    updatePublication();
    function metadataChanged() {
      selectReview("partial");
      refreshSections([]);
      remember();
      workspace?.refreshGenerated();
    }
    title.addEventListener("input", metadataChanged);
    for (const field of metadataFields) field.addEventListener("input", metadataChanged);
    structuredMetadata = mountMetadata(form, initial.document.metadata, metadataChanged);
    initial.sourceRevision = () => initial.revision;
    initial.registerSource = token => {
      if (saving) throw new Error("Wait for the current save before inserting source.");
      if (token) sourceTickets = [...sourceTickets, token];
    };
    initial.unregisterSource = token => {
      if (token) {
        const index = sourceTickets.lastIndexOf(token);
        if (index >= 0) sourceTickets = sourceTickets.filter((_, position) => position !== index);
      }
    };
    workspace = mountWorkspace(form, editor, showError, initial,
      () => ({title: title.value.trim(), metadata: metadata()}));
    function clearPaste() {
      pendingPaste = null;
      pasteText.textContent = "";
      pasteReplaced.textContent = "";
      pasteNotice.textContent = "";
      pasteFormatted.replaceChildren();
      pasteFormatStatus.textContent = "";
      pasteFormatInsert.hidden = true;
    }
    pasteDialog.addEventListener("close", () => {
      if (!pasteDialog.open) clearPaste();
    });
    function dismissPaste() {
      clearPaste();
      pasteDialog.close();
    }
    document.querySelector("#editor-paste-cancel").addEventListener("click", () => {
      dismissPaste();
      editor.commands.focus();
    });
    document.querySelector("#editor-paste-insert").addEventListener("click", () => {
      try {
        applyPlainTextPaste(editor, pendingPaste);
        dismissPaste();
        editor.commands.focus();
      } catch (failure) {
        dismissPaste();
        showError(failure.message);
      }
    });
    pasteFormatted.addEventListener("click", event => event.preventDefault());
    pasteFormatInsert.addEventListener("click", () => {
      try {
        applyFormattedPaste(editor, pendingPaste);
        dismissPaste();
        editor.commands.focus();
      } catch (failure) {
        dismissPaste();
        showError(failure.message);
      }
    });
    try {
      const raw = sessionStorage.getItem(storageKey);
      if (raw) {
        recoverable = JSON.parse(raw);
        restore.hidden = false;
      }
    } catch (failure) {
      showError(`Tab recovery could not be read: ${failure.message}`);
    }
    restore.addEventListener("click", () => {
      if (recoverable?.revision !== initial.revision) {
        showError("This recovery draft uses another revision. It was not applied.");
        return;
      }
      const target = document.createElement("div");
      let candidate;
      try {
        candidate = createBoundedEditor(target, recoverable.document.html);
        if (recoverable.source_tickets !== undefined &&
            (!Array.isArray(recoverable.source_tickets) ||
             recoverable.source_tickets.some(token => typeof token !== "string"))) {
          throw new Error("Invalid retained source recovery evidence.");
        }
        sourceTickets = recoverable.source_tickets || [];
        showDocumentPart(editor, null);
        editor.commands.setContent(candidate.getJSON());
        title.value = recoverable.document.title;
        populateMetadata(recoverable.document.metadata);
        structuredMetadata.restore(recoverable.document.metadata);
        workspace.refreshGenerated();
        selectReview(recoverable.review || "partial");
        refreshSections(Array.isArray(recoverable.verified_sections)
          ? recoverable.verified_sections : []);
        form.elements.editorial.checked = recoverable.editorial === true;
        restore.hidden = true;
        remember();
      } catch (failure) {
        showError(`Recovery was refused: ${failure.message}`);
      } finally {
        candidate?.destroy();
      }
    });
    markReviewed?.addEventListener("click", () => {
      if (dirty || saving || !initial.draft) return;
      selectReview("full");
      refreshSections([]);
      form.requestSubmit();
    });
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (saving) return;
      if (initial.requires_approval && !form.elements.approve_conversion.checked) {
        showError("Approve the exact legacy conversion before saving this draft.");
        return;
      }
      saving = true;
      updatePublication();
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      showError("");
      try {
        const submitted = formPayload();
        const response = await fetch(location.pathname, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": form.elements.csrfmiddlewaretoken.value,
          },
          body: JSON.stringify({
            draft: initial.draft, revision: initial.revision, ...submitted,
            conversion_approval: initial.draft ? null : initial.approval_digest,
          }),
        });
        if (!response.headers.get("Content-Type")?.includes("application/json")) {
          throw new Error(`Save failed (${response.status}); the draft remains in this tab.`);
        }
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `Save failed (${response.status}).`);
        const changedDuringSave = JSON.stringify(formPayload()) !== JSON.stringify(submitted);
        sourceTickets = sourceTickets.filter(token => !submitted.source_tickets.includes(token));
        initial.draft = result.draft;
        initial.revision = result.revision;
        // Edits made during the request stay dirty; do not overwrite them.
        dirty = changedDuringSave;
        initial.document = result.document;
        initial.saved_review = result.review;
        initial.saved_verified_sections = result.verified_sections;
        initial.editorial = result.editorial;
        differences?.refresh();
        updateSavedReview();
        if (!dirty) {
          title.value = result.document.title;
          populateMetadata(result.document.metadata);
          workspace.refreshGenerated();
          selectReview("partial");
          refreshSections([]);
        }
        workspaceShell?.updateState({
          draft: initial.draft, revision: initial.revision, dirty,
        });
        const url = new URL(location.href);
        url.searchParams.set("draft", result.draft);
        history.replaceState(null, "", url);
        try {
          sessionStorage.removeItem(storageKey);
        } catch (failure) {
          showError(`Revision saved, but recovery cleanup failed: ${failure.message}`);
        }
        storageKey = `${form.dataset.recoveryKey}:${result.draft}`;
        restore.hidden = true;
        if (dirty) remember();
        status.textContent = dirty
          ? `Saved version ${result.revision} as ${result.review}. Additional unsaved edits remain.`
          : `Saved version ${result.revision}. Review scope: ${result.review}.`;
        if (result.issues.length) showError(result.issues.join("\n"));
      } catch (failure) {
        showError(failure.message);
      } finally {
        saving = false;
        submit.disabled = false;
        updatePublication();
      }
    });
    window.addEventListener("beforeunload", event => {
      if (dirty) { event.preventDefault(); event.returnValue = ""; }
    });
    if (initial.choose_history) {
      editor.setEditable(false, false);
      form.inert = true;
      status.textContent = "Choose a working copy in Versions before editing.";
    }
  } catch (failure) {
    console.error("Editor initialization failed:", failure);
    showError(failure.message);
    status.textContent = "Editor unavailable; the original edition and drafts are unchanged.";
  }
}
