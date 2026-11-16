import {undo, redo} from "@tiptap/pm/history";
import {NodeSelection, TextSelection} from "@tiptap/pm/state";
import {
  canMoveTextBlock, moveTextBlock, isInlineStyleActive, toggleInlineStyle,
  canAlignTextBlock, textBlockAlignment, alignTextBlock,
  selectedImage, prepareImageEdit, applyImageEdit,
  selectedLink, prepareLinkEdit, applyLinkEdit, applyLinkRemoval,
  canInsertLink, prepareLinkInsertion,
  documentLinkTargets, canMarkCitation, markCitation, canMarkInlineQuotation,
  markInlineQuotation, matchingInlineQuotationMarks, inlineSemanticTargets,
  removeInlineSemantic, changeInlineSemantic,
} from "./editor.js";
import {
  canEditFigure, canWrapInFigure, canRemoveFigure, prepareFigure, buildFigure, applyFigure,
  removeFigure, wrapInFigure,
} from "./figures.js";
import {
  prepareQuotationInsertion, buildQuotationInsertion, applyQuotationInsertion, checkQuotationInsertion,
} from "./quotation-insertion.js";
import {
  canConvertSelectionToQuote, canRemoveQuotation, prepareSelectionQuote, applySelectionQuote,
  removeQuotation,
} from "./quotations.js";
import {
  canInsertTable, canEditTable, tableCaptionAction, tableHeaderAction,
  prepareTableInsertion, buildTableInsertion, applyTableInsertion, prepareTableEdit,
  buildTableEdit, applyTableEdit,
} from "./tables.js";
import {semanticDOM} from "./semantic-structure.js";
import {applyList, listState, mountListEditing} from "./lists.js";
import {insertHorizontalRule} from "./horizontal-rule.js";
import {
  documentParts, foldedDocumentParts, showDocumentPart, showBlockLabels, visiblePart,
  workspaceContext, setWorkspaceContext,
} from "./workspace.js";
import {mountDynamicOutline} from "./outline.js";
import {revealStart, scrollElementIntoView} from "./page-scroll.js";
import {movableSections, mountSectionMoves} from "./section-moves.js";
import {mountContentMoves} from "./content-moves.js";
import {mountSectionCreation} from "./section-creation.js";
import {mountSectionBoundaries} from "./section-boundaries.js";
import {mountTargets} from "./targets.js";
import {mountSectionManagement} from "./section-management.js";
import {mountSectionExcerpts} from "./section-excerpts.js";
import {BlockSelection} from "./block-selection.js";
import {mountBookViews} from "./book-views.js";
import {isTocNumberingChange, tocMarker, tocNumberingEntries} from "./toc-numbering.js";
import {mountNoteRepairs} from "./note-repairs.js";
import {attachContextualPanel} from "./contextual-panels.js";

export function mountWorkspace(form, editor, showError, initial = {}, readDocument = () => ({
  title: form.querySelector('[name="title"]')
    ? form.querySelector('[name="title"]').value : initial.document?.title || "",
  metadata: initial.document?.metadata || {},
})) {
  const owner = form.ownerDocument;
  const surface = form.querySelector("#editor-surface");
  const partSelect = form.querySelector("#editor-part");
  const outline = form.querySelector("#editor-outline-items");
  const path = form.querySelector("#editor-selection-path");
  const menu = form.querySelector("#editor-context-menu");
  attachContextualPanel(form, menu);
  const trigger = form.querySelector("#editor-tools");
  const imageDialog = owner.querySelector("#editor-image");
  const linkDialog = owner.querySelector("#editor-link");
  const inlineQuotationDialog = owner.querySelector("#editor-inline-q");
  const quotationDialog = owner.querySelector("#editor-quotation");
  const tableDialog = owner.querySelector("#editor-table");
  let quotationProposal = null;
  let quotationApplied = false;
  let tableProposal = null, tableAction = null, tableNeedsConfirmation = false;
  const figureHelp = quotationDialog?.querySelector("#editor-quotation-help").textContent;
  let linkProposal = null;
  let inlineQuotationProposal = null;
  let linkTargets = [];
  let imageProposal = null;
  let parts = [], menuTarget = null;
  const bookViews = mountBookViews(form, editor, readDocument, index => navigatePart(index), showError,
    initial.presentation);
  const sectionFilter = bookViews.filter;
  let context = workspaceContext(editor.state.doc, readDocument(), initial.structure || {});
  setWorkspaceContext(editor, context);
  const dynamicOutline = mountDynamicOutline(editor, outline, surface, showError,
    () => bookViews.expandNavigation(), () => bookViews.targets());
  mountSectionBoundaries(form, editor, showError, initial.structure?.parts || []);
  mountTargets(form, editor, showError);
  const noteRepairs = form.ownerDocument.querySelector("#editor-note-repair")
    ? mountNoteRepairs(form, editor, showError) : null;
  mountListEditing(editor, showError, readDocument);

  function figureOptions() {
    return {
      caption: quotationDialog.querySelector("#editor-figure-caption").value,
      text: quotationDialog.querySelector("#editor-quotation-attribution").value,
      body: quotationDialog.querySelector("#editor-quotation-body").value,
      title: quotationDialog.querySelector("#editor-figure-title").value,
      removeCites: quotationDialog.querySelector("#editor-figure-uncite").checked,
    };
  }
  function previewFigure() {
    const options = figureOptions();
    quotationDialog.querySelector("#editor-figure-new").hidden = options.caption !== "new";
    const preview = quotationDialog.querySelector("#editor-figure-preview");
    preview.replaceChildren();
    try {
      if (quotationProposal?.insertion) {
        const built = buildQuotationInsertion(editor, quotationProposal, {
          ...options, text: options.caption === "new" ? options.text : "",
        });
        preview.append(semanticDOM(editor.schema.nodes.doc.create(null, built.figure), owner));
        quotationDialog.querySelector('[role="alert"]').textContent = "";
        quotationDialog.querySelector("#editor-quotation-apply").disabled = false;
        return;
      }
      const built = buildFigure(editor, quotationProposal, options);
      const grouped = built.figure.type.name === "figure";
      const quote = grouped && built.figure.firstChild.type.name === "blockquote"
        ? built.figure.firstChild : built.figure.type.name === "blockquote" ? built.figure : null;
      const caption = grouped && ["figcaption", "figcaptionText"].includes(built.figure.lastChild.type.name)
        ? built.figure.lastChild : null;
      const main = owner.createElement("div");
      const heading = owner.createElement("strong");
      heading.textContent = quotationProposal.kind === "quotation" ? "QUOTE" : "IMAGE";
      main.append(heading);
      if (quotationProposal.kind === "quotation") {
        quote.forEach(node => {
          const paragraph = owner.createElement("p");
          paragraph.textContent = node.textContent;
          main.append(paragraph);
        });
      } else {
        let image;
        built.figure.descendants(node => {
          if (!image && ["img", "imgBlock"].includes(node.type.name)) image = node;
        });
        if (image && /^\/assets\/[0-9a-f]{64}\/$/.test(image.attrs.src)) {
          const thumbnail = owner.createElement("img");
          thumbnail.src = image.attrs.src;
          thumbnail.alt = image.attrs.alt || "";
          main.append(thumbnail);
        }
        const unchanged = owner.createElement("p");
        unchanged.textContent = "Retained image unchanged; alternative text and credit are preserved.";
        main.append(unchanged);
      }
      const relation = owner.createElement("p");
      relation.textContent = caption ? `CAPTION / ATTRIBUTION: ${caption.textContent}` : "CAPTION: none";
      const sources = [];
      built.figure.descendants(node => {
        if (node.isText && node.marks.some(mark => mark.attrs.tag === "cite")) sources.push(node.text);
      });
      const source = owner.createElement("p");
      source.textContent = `SOURCE TITLE (cite): ${sources.join("") || "not marked"}`;
      preview.append(main, relation, source);
      if (built.detached.length) {
        const notice = owner.createElement("p");
        notice.textContent = "The previous caption will remain as ordinary text after the figure. Nothing is deleted.";
        preview.append(notice);
      }
      quotationDialog.querySelector('[role="alert"]').textContent = "";
      quotationDialog.querySelector("#editor-quotation-apply").disabled = false;
    } catch (failure) {
      quotationDialog.querySelector('[role="alert"]').textContent = failure.message;
      quotationDialog.querySelector("#editor-quotation-apply").disabled = true;
    }
  }
  function tableOptions() {
    return {
      rows: Number(tableDialog.querySelector("#editor-table-rows").value),
      columns: Number(tableDialog.querySelector("#editor-table-columns").value),
      header: tableDialog.querySelector("#editor-table-header").checked,
      caption: tableDialog.querySelector("#editor-table-caption").value,
    };
  }
  function previewTable() {
    const preview = tableDialog.querySelector("#editor-table-preview");
    const alert = tableDialog.querySelector('[role="alert"]');
    const apply = tableDialog.querySelector("#editor-table-apply");
    preview.replaceChildren();
    tableNeedsConfirmation = false;
    try {
      let built, table, detached = [];
      if (tableAction === "insert-table") {
        built = buildTableInsertion(editor, tableProposal, tableOptions());
        table = built.table;
      } else {
        built = buildTableEdit(editor, tableProposal, tableAction,
          tableAction === "add-caption" ? {caption: tableDialog.querySelector("#editor-table-caption").value} : {});
        if (built.confirmation) {
          tableNeedsConfirmation = true;
          const notice = owner.createElement("p");
          notice.textContent = `This removes content from ${built.confirmation.length} cell(s): ${built.confirmation.join("; ")}. Confirm deletion to continue.`;
          preview.append(notice);
          built = buildTableEdit(editor, tableProposal, tableAction, {confirmed: true});
        }
        table = built.table;
        detached = built.detached;
      }
      preview.append(semanticDOM(editor.schema.nodes.doc.create(null, [table, ...detached]), owner));
      alert.textContent = "";
      apply.disabled = false;
      apply.textContent = tableNeedsConfirmation ? "Confirm deletion" :
        tableAction === "insert-table" ? "Insert table" : "Apply";
    } catch (failure) {
      alert.textContent = failure.message;
      apply.disabled = true;
    }
  }
  function openTableDialog(action) {
    if (!tableDialog) throw new Error("Table tools are unavailable in this editor view.");
    tableAction = action;
    tableProposal = action === "insert-table"
      ? prepareTableInsertion(editor, readDocument) : prepareTableEdit(editor, readDocument);
    tableDialog.querySelector("#editor-table-heading").textContent =
      action === "insert-table" ? "Insert simple table" :
        action.replaceAll("-", " ").replace(/^./, letter => letter.toUpperCase());
    const insertion = action === "insert-table";
    const tableNode = tableProposal.node;
    const identity = tableNode?.attrs.id ? ` #${tableNode.attrs.id}` : " without a target ID";
    tableDialog.querySelector("#editor-table-target").textContent = insertion
      ? `Insert at the captured prose caret (${tableProposal.offset} of ${tableProposal.paragraph.content.size}).`
      : `Table${identity}${tableProposal.cell
        ? `; row ${tableProposal.cell.rowIndex + 1}, column ${tableProposal.cell.columnIndex + 1}.`
        : "."}`;
    tableDialog.querySelector("#editor-table-insert-fields").hidden = !insertion;
    tableDialog.querySelector("#editor-table-caption-field").hidden =
      !insertion && action !== "add-caption";
    tableDialog.querySelector("#editor-table-rows").value = "2";
    tableDialog.querySelector("#editor-table-columns").value = "2";
    tableDialog.querySelector("#editor-table-header").checked = false;
    tableDialog.querySelector("#editor-table-caption").value = "";
    tableDialog.querySelector('[role="alert"]').textContent = "";
    previewTable();
    tableDialog.showModal();
    (insertion ? tableDialog.querySelector("#editor-table-rows") :
      action === "add-caption" ? tableDialog.querySelector("#editor-table-caption") :
        tableDialog.querySelector("#editor-table-apply")).focus();
  }
  function refreshLinkTargets() {
    const query = linkDialog.querySelector("#editor-link-search").value.trim().toLowerCase();
    const matches = linkTargets.filter(target =>
      `${target.id} ${target.kind} ${target.label}`.toLowerCase().includes(query));
    const list = linkDialog.querySelector("#editor-link-targets");
    list.replaceChildren();
    const scope = visiblePart(editor);
    for (const target of matches.slice(0, 50)) {
      const button = owner.createElement("button");
      button.type = "button";
      const hidden = scope && (target.position < scope.from || target.position >= scope.to);
      button.textContent = `#${target.id} - ${target.kind}${hidden ? " (outside current part)" : ""}` +
        (target.label ? `: ${target.label}` : "");
      button.addEventListener("click", () => {
        if (editor.state.doc !== linkProposal?.doc) {
          linkDialog.querySelector('[role="alert"]').textContent =
            "The document changed while link details were open. Select the link again.";
          return;
        }
        linkDialog.querySelector("#editor-link-href").value = `#${encodeURIComponent(target.id)}`;
        linkDialog.querySelector('[role="alert"]').textContent = "";
        linkDialog.querySelector("#editor-link-href").focus();
      });
      list.append(button);
    }
    linkDialog.querySelector("#editor-link-target-count").textContent = matches.length > 50
      ? `Showing 50 of ${matches.length} targets. Refine the search to find more.`
      : `${matches.length} matching target${matches.length === 1 ? "" : "s"} in the whole document.`;
  }

  function closeMenu(focus = false) {
    menu.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    menuTarget = null;
    if (focus) editor.commands.focus();
  }
  function refreshOutline() {
    const currentParts = documentParts(editor.state.doc, context);
    const numbering = tocNumberingEntries(editor.state.doc, currentParts);
    parts = currentParts.map((part, index) => {
      const original = initial.structure?.parts?.find(source => source.id === part.id);
      return {...part, role: part.role || original?.role, marker: tocMarker(numbering[index])};
    });
    const sections = movableSections(editor.state.doc, context);
    const scope = visiblePart(editor);
    if (scope && bookViews.view !== "sections") bookViews.show("sections");
    sectionFilter.replaceChildren(new Option("All sections", ""));
    outline.replaceChildren();
    let matched = !scope;
    const choices = [{label: "Whole book", depth: 0}, ...parts];
    for (const [index, part] of choices.entries()) {
      const value = index ? String(index - 1) : "";
      const current = index ? scope?.from === part.from && scope?.to === part.to : !scope;
      const title = `${part.marker ? `${part.marker} ` : ""}${part.label}`;
      const label = index
        ? `${"  ".repeat(Math.min(part.depth, 8))}${part.displayKind || part.kind}: ${title}`
        : title;
      if (index) sectionFilter.add(new Option(label, value));
      if (current) sectionFilter.value = value;
      if (current) matched = true;
      const button = owner.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.dataset.part = value;
      button.title = part.label;
      if (current) button.setAttribute("aria-current", "true");
      if (index) outline.append(button);
      const sectionIndex = index ? sections.findIndex(section =>
        section.from + 1 === part.from && section.to - 1 === part.to) : -1;
      if (sectionIndex >= 0) {
        button.draggable = true;
        button.dataset.sectionMove = String(sectionIndex);
        button.setAttribute("aria-haspopup", "menu");
        button.setAttribute("aria-expanded", "false");
        button.title = `${part.label} — Right-click or Shift+F10 for section actions`;
      }
    }
    if (!matched) {
      const option = new Option(`Focused range: ${scope.label}`, "focused-range");
      option.disabled = true;
      sectionFilter.add(option);
      sectionFilter.value = option.value;
    }
    dynamicOutline.render(parts);
    bookViews.navigation(outline);
    bookViews.refresh(parts);
  }
  function choosePart(value) {
    try {
      showError("");
      closeMenu();
      bookViews.show("sections");
      showDocumentPart(editor, value === "" ? null : parts[Number(value)]);
      revealStart(surface);
      editor.commands.focus();
    } catch (failure) {
      showError(failure.message);
    }
    refreshOutline();
  }
  function chooseView(value) {
    try {
      showError("");
      closeMenu();
      bookViews.show(value);
      showDocumentPart(editor, null);
      revealStart(surface);
      refreshOutline();
    } catch (failure) { showError(failure.message); }
  }
  partSelect.addEventListener("change", () => chooseView(partSelect.value));
  sectionFilter.addEventListener("change", () => choosePart(sectionFilter.value));
  function navigatePart(index) {
    try {
      showError("");
      closeMenu();
      const part = parts[index];
      if (!["book", "sections"].includes(bookViews.view)) bookViews.show("sections");
      showDocumentPart(editor, part, {filter: false});
      refreshOutline();
      const target = editor.view.nodeDOM(part.kind === "Section" ? part.from - 1 : part.from);
      if (target instanceof owner.defaultView.HTMLElement) scrollElementIntoView(target, 0);
      editor.view.focus();
    } catch (failure) { showError(failure.message); }
  }
  // Book-level rows navigate like section rows: reveal and scroll within a view that
  // contains them; the View select isolates a generated page or the sections.
  function navigateBook(value) {
    try {
      showError("");
      closeMenu();
      if (![value, "book"].includes(bookViews.view)) bookViews.show(value === "sections" ? "sections" : "book");
      if (visiblePart(editor)) showDocumentPart(editor, null);
      refreshOutline();
      const target = bookViews.target(value);
      if (!target) revealStart(surface);
      else scrollElementIntoView(target, 0);
      dynamicOutline.schedule();
      outline.querySelector(`[data-book-view="${value}"]`)?.focus({preventScroll: true});
    } catch (failure) { showError(failure.message); }
  }
  outline.addEventListener("click", event => {
    const view = event.target.closest("[data-book-view]");
    if (view) {
      navigateBook(view.dataset.bookView);
      return;
    }
    const button = event.target.closest("[data-part]");
    if (!button) return;
    navigatePart(Number(button.dataset.part));
  });
  form.querySelector("#editor-block-labels").addEventListener("change", event => {
    showBlockLabels(editor, event.target.checked);
  });
  function updateTools() {
    const prose = ["book", "sections"].includes(bookViews.view);
    trigger.disabled = !prose;
    const {selection} = editor.state;
    const textSelection = selection instanceof TextSelection;
    const blockSelection = selection instanceof BlockSelection ||
      selection instanceof NodeSelection && selection.node.isBlock;
    const completeTextBlocks = textSelection && !selection.empty &&
      selection.$from.parent.isTextblock && selection.$to.parent.isTextblock &&
      selection.$from.parentOffset === 0 &&
      selection.$to.parentOffset === selection.$to.parent.content.size &&
      selection.$from.depth === selection.$to.depth &&
      selection.$from.depth > 1 &&
      selection.$from.node(selection.$from.depth - 1) === selection.$to.node(selection.$to.depth - 1);
    function available(button, applicable, enabled = applicable) {
      button.hidden = !applicable || !prose;
      button.disabled = !enabled || !prose;
    }
    const contentMove = form.querySelector("#editor-content-move-open");
    if (contentMove) available(contentMove, !selection.empty && (textSelection || blockSelection));
    const excerpt = form.querySelector("#editor-section-excerpt-open");
    const excerptParent = blockSelection ? selection.$from.parent :
      completeTextBlocks ? selection.$from.node(selection.$from.depth - 1) : null;
    if (excerpt) available(excerpt, (blockSelection || completeTextBlocks) &&
      excerptParent?.type.name === "section");
    for (const button of form.querySelectorAll("[data-quotation]")) {
      available(button, button.dataset.quotation === "insert" || canEditFigure(editor));
    }
    const quotationActions = {
      convert: canConvertSelectionToQuote(editor),
      wrap: canWrapInFigure(editor),
      "remove-quote": canRemoveQuotation(editor),
      "remove-figure": canRemoveFigure(editor),
    };
    for (const button of form.querySelectorAll("[data-quote-action]")) {
      available(button, quotationActions[button.dataset.quoteAction]);
    }
    for (const button of form.querySelectorAll("[data-table-action]")) {
      const action = button.dataset.tableAction;
      const applicable = action === "insert-table" ? canInsertTable(editor) :
        action === "add-caption" || action === "remove-caption"
          ? tableCaptionAction(editor) === action :
            action === "make-header" || action === "make-data"
              ? tableHeaderAction(editor) === action : canEditTable(editor);
      available(button, applicable);
    }
    for (const button of form.querySelectorAll("[data-rule-insert]")) available(button, true);
    const lists = listState(editor);
    const listHelp = {
      indent: "Indent item: requires a preceding sibling.",
      outdent: "Outdent item: available only in a nested list.",
      up: "Move item up: requires a preceding sibling.",
      down: "Move item down: requires a following sibling.",
    };
    for (const button of form.querySelectorAll("[data-list]")) {
      const action = button.dataset.list, format = ["ul", "ol"].includes(action);
      available(button, true, format || lists[action]);
      if (format) {
        button.setAttribute("aria-checked", String(lists.type === action));
        if (button.hasAttribute("aria-pressed")) button.setAttribute("aria-pressed", String(lists.type === action));
      } else button.title = listHelp[action];
    }
    for (const button of form.querySelectorAll("[data-mark]")) {
      available(button, textSelection);
      const active = isInlineStyleActive(editor, button.dataset.mark);
      button.setAttribute("aria-checked", String(active));
      if (button.hasAttribute("aria-pressed")) button.setAttribute("aria-pressed", String(active));
    }
    for (const button of form.querySelectorAll("[data-inline-mark]")) {
      const target = button.dataset.inlineMark;
      const allowed = target === "cite" ? canMarkCitation(editor) : canMarkInlineQuotation(editor);
      available(button, !selection.empty && allowed);
    }
    const inlineTargets = inlineSemanticTargets(editor);
    const inlineTargetList = menu.querySelector("[data-inline-targets]");
    if (inlineTargetList) {
      inlineTargetList.replaceChildren();
      const counts = Object.fromEntries(["cite", "q"].map(tag => [
        tag, inlineTargets.filter(target => target.mark.attrs.tag === tag).length,
      ]));
      for (const [index, target] of inlineTargets.entries()) {
        const tag = target.mark.attrs.tag;
        const tagIndex = inlineTargets.slice(0, index)
          .filter(candidate => candidate.mark.attrs.tag === tag).length;
        const name = tag === "cite" ? "source title" : "inline quotation";
        const button = owner.createElement("button");
        button.type = "button";
        button.role = "menuitem";
        button.dataset.inlineAction = "remove";
        button.dataset.inlineTag = tag;
        button.dataset.inlineIndex = String(tagIndex);
        button.hidden = !prose;
        button.disabled = !prose;
        button.textContent = `Remove ${name}${counts[tag] > 1 ? ` (${tagIndex === 0 ? "outer" : "inner"})` : ""}`;
        inlineTargetList.append(button);
        const change = owner.createElement("button");
        change.type = "button";
        change.role = "menuitem";
        change.dataset.inlineAction = "change";
        change.dataset.inlineTag = tag;
        change.dataset.inlineIndex = String(tagIndex);
        change.hidden = !prose;
        change.disabled = !prose;
        change.textContent = `Change ${name} to ${tag === "cite" ? "inline quotation" : "source title"}`;
        inlineTargetList.append(change);
      }
    }
    for (const button of form.querySelectorAll("[data-image]")) {
      available(button, !!selectedImage(editor));
    }
    for (const button of form.querySelectorAll("[data-link], [data-link-remove], [data-note-repair]")) {
      available(button, !!selectedLink(editor));
    }
    for (const button of form.querySelectorAll("[data-link-insert]")) {
      available(button, canInsertLink(editor));
    }
    const oneBlock = selection instanceof TextSelection && selection.$from.sameParent(selection.$to);
    for (const button of form.querySelectorAll("[data-block]")) {
      available(button, oneBlock && ["p", "h2", "h3", "h4", "h5", "h6", "pre", "inlineRun"]
        .includes(selection.$from.parent.type.name));
      const active = editor.isActive(button.dataset.block);
      button.setAttribute("aria-checked", String(active));
      if (button.hasAttribute("aria-pressed")) button.setAttribute("aria-pressed", String(active));
    }
    for (const button of form.querySelectorAll("[data-move]")) {
      available(button, canAlignTextBlock(editor), canMoveTextBlock(editor, Number(button.dataset.move)));
    }
    for (const button of form.querySelectorAll("[data-align]")) {
      available(button, canAlignTextBlock(editor));
      button.setAttribute("aria-checked", String(textBlockAlignment(editor) === button.dataset.align));
    }
    for (const button of form.querySelectorAll("[data-history]")) {
      button.disabled = !(button.dataset.history === "undo" ? undo : redo)(editor.state);
    }
    for (const group of menu.querySelectorAll("[role=group]")) {
      group.hidden = ![...group.querySelectorAll("button")].some(button => !button.hidden);
    }
    const ancestors = [];
    for (let depth = 1; depth <= selection.$from.depth; depth++) {
      const node = selection.$from.node(depth);
      ancestors.push((node.type.name === "inlineRun" ? "Text run" :
        node.type.name.replace(/Text$|Block$/g, "")) +
        (node.attrs.id ? ` #${node.attrs.id}` : ""));
    }
    path.textContent = `Current block: ${ancestors.join(" / ") || "Document"}`;
    if (inlineTargets.length) path.textContent += " · Inline: " + inlineTargets
      .map(target => target.mark.attrs.tag === "cite" ? "CITE" : "Q").join(" › ");
    if (selection instanceof BlockSelection) path.textContent =
      `${selection.positions.length} whole block(s) selected` +
      (selection.contiguous ? " (contiguous)." : " (gaps: select intervening blocks before extracting).") +
      " Ctrl-click toggles blocks; Escape clears selection.";
    if (selectedImage(editor)) path.textContent += " / Image";
  }
  function openMenu() {
    closeMenu();
    menuTarget = {doc: editor.state.doc, bookmark: editor.state.selection.getBookmark()};
    updateTools();
    const {selection} = editor.state;
    form.querySelector("#editor-menu-target").textContent = selection instanceof BlockSelection
      ? `${selection.positions.length} whole block(s) selected${selection.contiguous ? "" : " with gaps"}. Separate as excerpt uses only contiguous blocks.`
      : selectedImage(editor)
      ? "Selected image: edit alternative text without replacing its retained asset"
      : selectedLink(editor) ? "Existing link: edit the whole link's destination and title, preserving its text"
      : selection.empty
      ? "At the cursor" : "Selected text: styling applies only to this selection";
    menu.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    menu.querySelector("button:not(:disabled):not([hidden])")?.focus();
  }
  function openAtSelection() {
    openMenu();
  }
  trigger.addEventListener("click", openAtSelection);
  function preserveContextSelection(event) {
    if (editor.view.dom.contains(event.target) &&
        event.button === 2 && !editor.state.selection.empty) event.preventDefault();
  }
  // Run before ProseMirror's target listener, not after it has replaced the selection.
  surface.addEventListener("pointerdown", preserveContextSelection, true);
  surface.addEventListener("mousedown", preserveContextSelection, true);
  surface.addEventListener("contextmenu", event => {
    if ((event.target !== surface && !editor.view.dom.contains(event.target)) || editor.view.dom.hidden) return;
    if (event.shiftKey) return;
    event.preventDefault();
    const image = event.target.closest("img");
    const link = event.target.closest("a[href]");
    if (editor.state.selection instanceof BlockSelection) {
      // Keep the explicit block set even when right-click lands on its image or link.
    } else if (image && surface.contains(image)) {
      const position = editor.view.posAtDOM(image, 0);
      editor.view.dispatch(editor.state.tr.setSelection(
        NodeSelection.create(editor.state.doc, position),
      ));
    } else if (link && surface.contains(link)) {
      const from = editor.view.posAtDOM(link, 0);
      editor.view.dispatch(editor.state.tr.setSelection(link.childNodes.length
        ? TextSelection.create(editor.state.doc, from, editor.view.posAtDOM(link, link.childNodes.length))
        : NodeSelection.create(editor.state.doc, from)));
    } else if (editor.state.selection.empty) {
      const position = editor.view.posAtCoords({left: event.clientX, top: event.clientY});
      if (position) editor.view.dispatch(editor.state.tr.setSelection(
        TextSelection.near(editor.state.doc.resolve(position.pos)),
      ));
    }
    openMenu();
  });
  surface.addEventListener("keydown", event => {
    if (!editor.view.dom.contains(event.target) || editor.view.dom.hidden) return;
    if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
      event.preventDefault();
      openAtSelection();
    }
  });
  menu.addEventListener("keydown", event => {
    const items = [...menu.querySelectorAll("button:not(:disabled):not([hidden])")];
    const index = items.indexOf(owner.activeElement);
    if (["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 :
        (index + (["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1) + items.length) % items.length;
      items[next].focus();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeMenu(true);
    } else if (event.key === "Tab") {
      closeMenu();
    }
  });
  form.querySelector("#editor-menu-close").addEventListener("click", () => closeMenu(true));
  function perform(button) {
    try {
      showError("");
      if (menuTarget) {
        if (editor.state.doc !== menuTarget.doc) {
          throw new Error("The document changed while the menu was open. Select the text again.");
        }
        editor.view.dispatch(editor.state.tr.setSelection(menuTarget.bookmark.resolve(editor.state.doc)));
      }
      closeMenu();
      if (button.dataset.quoteAction) {
        const action = button.dataset.quoteAction;
        if (action === "convert") {
          applySelectionQuote(editor, prepareSelectionQuote(editor, readDocument));
        } else if (action === "wrap") {
          wrapInFigure(editor, prepareFigure(editor));
        } else if (action === "remove-quote") removeQuotation(editor);
        else if (action === "remove-figure") removeFigure(editor, prepareFigure(editor));
        editor.commands.focus();
        return;
      }
      if (button.dataset.tableAction) {
        openTableDialog(button.dataset.tableAction);
        return;
      }
      if (button.dataset.quotation) {
        const insertion = button.dataset.quotation === "insert";
        quotationProposal = insertion ? prepareQuotationInsertion(editor, readDocument) : prepareFigure(editor);
        quotationApplied = false;
        quotationDialog.querySelector("#editor-quotation-heading").textContent =
          insertion ? "Insert quotation" : "Caption relationship";
        quotationDialog.querySelector("#editor-quotation-body-field").hidden = !insertion;
        quotationDialog.querySelector("#editor-quotation-body").value = "";
        quotationDialog.querySelector('label[for="editor-quotation-attribution"]').textContent =
          insertion ? "Attribution / caption (optional)" : "New caption text";
        quotationDialog.querySelector("#editor-quotation-apply").textContent =
          insertion ? "Insert quotation" : "Apply";
        quotationDialog.querySelector("#editor-quotation-help").textContent = insertion
          ? "Enter literal quoted text; blank lines separate paragraphs and single line breaks are kept. Attribution is optional. No source facts are inferred. Preview and field edits do not change the document."
          : figureHelp;
        quotationDialog.querySelector("#editor-quotation-target").textContent =
          insertion ? `Insert at the captured paragraph caret (${quotationProposal.offset} of ${quotationProposal.paragraph.content.size}). Surrounding text and targets are preserved.`
          : `${quotationProposal.kind === "quotation" ? "Quotation" : "Image"}${quotationProposal.figure ? " figure" : ""}. Choose a caption relationship; Apply changes the named element once.`;
        const choices = quotationDialog.querySelector("#editor-figure-caption");
        choices.replaceChildren(new Option(insertion ? "No attribution" :
          quotationProposal.caption ? "Keep existing caption" : "No caption yet", insertion ? "none" : "keep"));
        for (const candidate of quotationProposal.candidates || []) choices.add(new Option(candidate.label, candidate.value));
        choices.add(new Option("Write a new caption", "new"));
        if (quotationProposal.caption) choices.add(new Option("Detach caption (keep as ordinary text)", "none"));
        choices.value = insertion ? "none" : "keep";
        const input = quotationDialog.querySelector("#editor-quotation-attribution");
        input.value = "";
        input.disabled = false;
        quotationDialog.querySelector("#editor-figure-title").value = "";
        quotationDialog.querySelector("#editor-figure-uncite").checked = false;
        quotationDialog.querySelector("#editor-figure-remove").hidden = insertion || !quotationProposal.figure &&
          !quotationProposal.quote;
        quotationDialog.querySelector("#editor-figure-uncite").closest("details").hidden = insertion;
        quotationDialog.querySelector('[role="alert"]').textContent = "";
        previewFigure();
        quotationDialog.showModal();
        (insertion ? quotationDialog.querySelector("#editor-quotation-body") : choices).focus();
        return;
      } else if ("image" in button.dataset) {
        imageProposal = prepareImageEdit(editor);
        const preview = imageDialog.querySelector("img");
        preview.src = imageProposal.node.attrs.src;
        preview.alt = imageProposal.node.attrs.alt || "";
        imageDialog.querySelector("textarea").value = imageProposal.node.attrs.alt || "";
        imageDialog.querySelector('[role="alert"]').textContent = "";
        imageDialog.querySelector("#editor-image-target").textContent =
          `Retained image${imageProposal.node.attrs.id ? ` #${imageProposal.node.attrs.id}` : ""}. File and caption are unchanged.`;
        imageDialog.showModal();
        imageDialog.querySelector("textarea").focus();
        return;
      } else if ("noteRepair" in button.dataset) {
        noteRepairs.open();
        return;
      } else if ("link" in button.dataset || "linkInsert" in button.dataset) {
        linkProposal = "linkInsert" in button.dataset ? prepareLinkInsertion(editor) : prepareLinkEdit(editor);
        linkDialog.querySelector("#editor-link-heading").textContent =
          linkProposal.insertion ? "Create link from selection" : "Edit link destination";
        linkDialog.querySelector("#editor-link-href").value = linkProposal.mark?.attrs.href || "";
        linkDialog.querySelector("#editor-link-title").value = linkProposal.mark?.attrs.title || "";
        linkDialog.querySelector("#editor-link-target").textContent =
          `${linkProposal.insertion ? "Selected text" : "Whole link"}: ${editor.state.doc.textBetween(linkProposal.from, linkProposal.to, "", "[image]")}`;
        linkDialog.querySelector('[role="alert"]').textContent = "";
        linkTargets = documentLinkTargets(linkProposal.doc);
        linkDialog.querySelector("#editor-link-search").value = "";
        refreshLinkTargets();
        linkDialog.showModal();
        linkDialog.querySelector("#editor-link-href").focus();
        return;
      } else if (button.dataset.inlineMark === "cite") {
        markCitation(editor);
      } else if (button.dataset.inlineMark === "q") {
        const text = editor.state.doc.textBetween(
          editor.state.selection.from, editor.state.selection.to,
        );
        if (matchingInlineQuotationMarks(text)) {
          inlineQuotationProposal = {
            doc: editor.state.doc,
            bookmark: editor.state.selection.getBookmark(),
            text,
          };
          inlineQuotationDialog.querySelector("#editor-inline-q-before").textContent = text;
          inlineQuotationDialog.querySelector("#editor-inline-q-after").textContent = text;
          inlineQuotationDialog.querySelector("#editor-inline-q-replace").checked = false;
          inlineQuotationDialog.querySelector('[role="alert"]').textContent = "";
          inlineQuotationDialog.showModal();
          inlineQuotationDialog.querySelector("#editor-inline-q-replace").focus();
          return;
        }
        markInlineQuotation(editor);
      } else if (button.dataset.inlineAction) {
        const tag = button.dataset.inlineTag;
        const index = Number(button.dataset.inlineIndex);
        if (button.dataset.inlineAction === "remove") removeInlineSemantic(editor, tag, index);
        else changeInlineSemantic(editor, tag, index);
      } else if ("linkRemove" in button.dataset) applyLinkRemoval(editor, prepareLinkEdit(editor));
      else if ("ruleInsert" in button.dataset) insertHorizontalRule(editor, readDocument);
      else if (button.dataset.list) applyList(editor, button.dataset.list, readDocument);
      else if (button.dataset.mark) toggleInlineStyle(editor, button.dataset.mark);
      else if (button.dataset.block) {
        const {selection} = editor.state;
        const tr = editor.state.tr.setNodeMarkup(selection.$from.before(),
          editor.schema.nodes[button.dataset.block], selection.$from.parent.attrs);
        editor.view.dispatch(tr);
      } else if ("align" in button.dataset) alignTextBlock(editor,
        textBlockAlignment(editor) === button.dataset.align ? "" : button.dataset.align);
      else if (button.dataset.move) moveTextBlock(editor, Number(button.dataset.move));
      else (button.dataset.history === "undo" ? undo : redo)(editor.state, editor.view.dispatch);
      editor.commands.focus();
    } catch (failure) {
      closeMenu();
      showError(failure.message);
    }
  }
  for (const button of form.querySelectorAll("[data-mark], [data-inline-mark], [data-block], [data-align], [data-move], [data-history], [data-image], [data-link], [data-link-insert], [data-link-remove], [data-note-repair], [data-quotation], [data-quote-action], [data-table-action], [data-list], [data-rule-insert]")) {
    button.addEventListener("click", () => perform(button));
  }
  menu.addEventListener("click", event => {
    const button = event.target.closest("[data-inline-action]");
    if (button) perform(button);
  });
  for (const button of form.querySelectorAll(".editor-format-toolbar button")) {
    button.addEventListener("mousedown", event => event.preventDefault());
  }
  function workspaceHistory(event) {
    if (event.defaultPrevented || event.altKey || !(event.ctrlKey || event.metaKey) ||
        event.target.closest("input, textarea, select, [contenteditable], dialog")) return;
    const key = event.key.toLowerCase();
    if (key !== "z" && key !== "y") return;
    event.preventDefault();
    closeMenu();
    showError("");
    const target = event.target;
    const bookView = target.closest("[data-book-view]")?.dataset.bookView;
    const tocPart = target.closest("[data-toc-part]")?.dataset.tocPart;
    const partButton = target.closest(".editor-outline-row")?.querySelector("[data-part]");
    const part = partButton ? parts[Number(partButton.dataset.part)] : null;
    const command = key === "y" || event.shiftKey ? redo : undo;
    command(editor.state, editor.view.dispatch);
    if (!target.isConnected && tocPart !== undefined) {
      form.querySelector(`[data-toc-part="${tocPart}"]`)?.focus({preventScroll: true});
    } else if (!target.isConnected && bookView) {
      outline.querySelector(`[data-book-view="${bookView}"]`)?.focus({preventScroll: true});
    } else if (!target.isConnected && partButton) {
      const index = parts.findIndex(candidate => candidate.kind === part.kind &&
        (part.id ? candidate.id === part.id : candidate.from === part.from));
      (outline.querySelector(`[data-part="${index}"]`) ||
        outline.querySelector("[data-book-view]"))?.focus({preventScroll: true});
    } else if (target.closest("#editor-section-actions, #editor-outline-menu")) {
      (outline.querySelector('.editor-outline-active [data-part]') ||
        outline.querySelector("[data-book-view]"))?.focus({preventScroll: true});
    } else if (menu.contains(target)) trigger.focus({preventScroll: true});
  }
  form.addEventListener("keydown", workspaceHistory);
  surface.addEventListener("click", event => {
    const handle = event.target.closest(
      "[data-editor-figure], [data-editor-image], [data-editor-caption]",
    );
    if (!handle) return;
    event.preventDefault();
    try {
      const position = Number(handle.dataset.editorFigure || handle.dataset.editorImage ||
        handle.dataset.editorCaption);
      editor.view.dispatch(editor.state.tr.setSelection(
        NodeSelection.create(editor.state.doc, position),
      ));
      perform(handle.hasAttribute("data-editor-image")
        ? form.querySelector("[data-image]")
        : form.querySelector('[data-quotation="edit"]'));
    } catch (failure) {
      showError(failure.message);
    }
  });
  if (quotationDialog) {
    quotationDialog.querySelector("#editor-quotation-cancel").addEventListener("click",
      () => quotationDialog.close());
    quotationDialog.addEventListener("close", () => {
      if (quotationProposal?.insertion && !quotationApplied) {
        try {
          checkQuotationInsertion(editor, quotationProposal);
          editor.view.dispatch(editor.state.tr.setSelection(quotationProposal.bookmark.resolve(editor.state.doc)));
        } catch (failure) { showError(failure.message); }
      }
      quotationProposal = null;
      for (const input of quotationDialog.querySelectorAll("textarea")) input.value = "";
      quotationDialog.querySelector("#editor-figure-preview").replaceChildren();
      editor.view.focus();
    });
    for (const control of quotationDialog.querySelectorAll("select, textarea, input")) {
      control.addEventListener("input", previewFigure);
      control.addEventListener("change", previewFigure);
    }
    quotationDialog.querySelector("#editor-figure-remove").addEventListener("click", () => {
      try {
        removeFigure(editor, quotationProposal);
        quotationDialog.close();
      } catch (failure) {
        quotationDialog.querySelector('[role="alert"]').textContent = failure.message;
      }
    });
    quotationDialog.querySelector("#editor-quotation-apply").addEventListener("click", () => {
      try {
        if (!quotationProposal) return;
        const options = figureOptions();
        if (quotationProposal.insertion) {
          applyQuotationInsertion(editor, quotationProposal, {
            ...options, text: options.caption === "new" ? options.text : "",
          });
        } else applyFigure(editor, quotationProposal, options);
        quotationApplied = true;
        quotationDialog.querySelector("#editor-quotation-apply").disabled = true;
        quotationDialog.close();
      } catch (failure) {
        quotationDialog.querySelector('[role="alert"]').textContent = failure.message;
      }
    });
  }
  if (tableDialog) {
    tableDialog.querySelector("#editor-table-cancel").addEventListener("click", () => tableDialog.close());
    tableDialog.addEventListener("close", () => {
      tableProposal = null;
      tableAction = null;
      tableNeedsConfirmation = false;
      tableDialog.querySelector("#editor-table-preview").replaceChildren();
      editor.commands.focus();
    });
    for (const control of tableDialog.querySelectorAll("input")) {
      control.addEventListener("input", previewTable);
      control.addEventListener("change", previewTable);
    }
    tableDialog.querySelector("#editor-table-apply").addEventListener("click", () => {
      try {
        if (!tableProposal || !tableAction) return;
        if (tableAction === "insert-table") applyTableInsertion(editor, tableProposal, tableOptions());
        else applyTableEdit(editor, tableProposal, tableAction,
          tableAction === "add-caption"
            ? {caption: tableDialog.querySelector("#editor-table-caption").value}
            : tableNeedsConfirmation ? {confirmed: true} : {});
        tableDialog.close();
      } catch (failure) {
        tableDialog.querySelector('[role="alert"]').textContent = failure.message;
      }
    });
  }
  if (imageDialog) {
    imageDialog.querySelector("#editor-image-cancel").addEventListener("click", () => imageDialog.close());
    imageDialog.addEventListener("close", () => {
      imageProposal = null;
      imageDialog.querySelector("img").removeAttribute("src");
      imageDialog.querySelector("textarea").value = "";
      editor.commands.focus();
    });
    imageDialog.querySelector("#editor-image-apply").addEventListener("click", () => {
      try {
        applyImageEdit(editor, imageProposal, imageDialog.querySelector("textarea").value);
        imageDialog.close();
      } catch (failure) {
        imageDialog.querySelector('[role="alert"]').textContent = failure.message;
      }
    });
  }
  if (linkDialog) {
    linkDialog.querySelector("#editor-link-search").addEventListener("input", refreshLinkTargets);
    linkDialog.querySelector("#editor-link-cancel").addEventListener("click", () => linkDialog.close());
    linkDialog.addEventListener("close", () => {
      linkProposal = null;
      linkTargets = [];
      linkDialog.querySelector("#editor-link-search").value = "";
      linkDialog.querySelector("#editor-link-targets").replaceChildren();
      linkDialog.querySelector("#editor-link-href").value = "";
      linkDialog.querySelector("#editor-link-title").value = "";
      editor.commands.focus();
    });
    linkDialog.querySelector("#editor-link-apply").addEventListener("click", () => {
      try {
        applyLinkEdit(editor, linkProposal, linkDialog.querySelector("#editor-link-href").value,
          linkDialog.querySelector("#editor-link-title").value);
        linkDialog.close();
      } catch (failure) {
        linkDialog.querySelector('[role="alert"]').textContent = failure.message;
      }
    });
  }
  if (inlineQuotationDialog) {
    const replace = inlineQuotationDialog.querySelector("#editor-inline-q-replace");
    const preview = inlineQuotationDialog.querySelector("#editor-inline-q-after");
    replace.addEventListener("change", () => {
      const pair = matchingInlineQuotationMarks(inlineQuotationProposal?.text || "");
      preview.textContent = replace.checked && pair
        ? inlineQuotationProposal.text.slice(pair[0].length, -pair[1].length)
        : inlineQuotationProposal?.text || "";
    });
    inlineQuotationDialog.querySelector("#editor-inline-q-cancel")
      .addEventListener("click", () => inlineQuotationDialog.close());
    inlineQuotationDialog.addEventListener("close", () => {
      inlineQuotationProposal = null;
      editor.commands.focus();
    });
    inlineQuotationDialog.querySelector("#editor-inline-q-apply").addEventListener("click", () => {
      try {
        const proposal = inlineQuotationProposal;
        if (!proposal || editor.state.doc !== proposal.doc) {
          throw new Error("The document changed while quotation options were open. Select the text again.");
        }
        editor.view.dispatch(editor.state.tr.setSelection(
          proposal.bookmark.resolve(editor.state.doc),
        ));
        if (editor.state.doc.textBetween(
          editor.state.selection.from, editor.state.selection.to,
        ) !== proposal.text) {
          throw new Error("The selected text changed. Select it again before marking it.");
        }
        markInlineQuotation(editor, {replaceOuterMarks: replace.checked});
        inlineQuotationDialog.close();
      } catch (failure) {
        inlineQuotationDialog.querySelector('[role="alert"]').textContent = failure.message;
      }
    });
  }
  function outside(event) {
    if (!menu.contains(event.target) && !trigger.contains(event.target)) closeMenu();
  }
  owner.addEventListener("pointerdown", outside);
  let lastScope = visiblePart(editor);
  let lastFolds = foldedDocumentParts(editor);
  editor.on("transaction", ({transaction}) => {
    const generatedView = !["book", "sections"].includes(bookViews.view);
    const tocFormatting = transaction.getMeta("readingHubToc") ||
      generatedView && transaction.docChanged && isTocNumberingChange(transaction.before, transaction.doc);
    const revealProse = !tocFormatting && (transaction.docChanged || transaction.selectionSet) && generatedView;
    if (revealProse) bookViews.show("sections");
    if (transaction.docChanged) closeMenu();
    updateTools();
    const scope = visiblePart(editor);
    const folds = foldedDocumentParts(editor);
    if (transaction.docChanged || scope !== lastScope || folds !== lastFolds || revealProse) refreshOutline();
    lastScope = scope;
    lastFolds = folds;
  });
  editor.on("destroy", () => {
    owner.removeEventListener("pointerdown", outside);
  });
  function updateWorkspaceContext() {
    const next = workspaceContext(editor.state.doc, readDocument(), initial.structure || {});
    if (JSON.stringify(next) === JSON.stringify(context)) return;
    context = next;
    setWorkspaceContext(editor, context);
    refreshOutline();
  }
  form.querySelector('[name="title"]')?.addEventListener("input", updateWorkspaceContext);
  form.querySelector('[name="work_type"]')?.addEventListener("change", updateWorkspaceContext);
  const sectionMoves = mountSectionMoves(form, editor, showError, {externalMenu: true});
  const sectionCreation = mountSectionCreation(form, editor, showError);
  mountSectionManagement(form, editor, showError, sectionMoves, sectionCreation, initial);
  mountContentMoves(form, editor, showError);
  mountSectionExcerpts(form, editor, showError, initial.structure?.parts || []);
  refreshOutline();
  updateTools();
  return {refreshGenerated: () => bookViews.refresh(parts)};
}
