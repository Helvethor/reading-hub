import {undo, redo} from "@tiptap/pm/history";
import {NodeSelection, TextSelection} from "@tiptap/pm/state";
import {
  canMoveTextBlock, moveTextBlock, isInlineStyleActive, toggleInlineStyle,
  canAlignTextBlock, textBlockAlignment, alignTextBlock,
  selectedImage, prepareImageEdit, applyImageEdit,
  selectedLink, prepareLinkEdit, applyLinkEdit, applyLinkRemoval,
  canInsertLink, prepareLinkInsertion,
  documentLinkTargets,
} from "./editor.js";
import {
  canEditFigure, prepareFigure, buildFigure, applyFigure, removeFigure,
} from "./figures.js";
import {documentParts, foldedDocumentParts, showDocumentPart, showBlockLabels, visiblePart} from "./workspace.js";
import {mountDynamicOutline} from "./outline.js";
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

export function mountWorkspace(form, editor, showError, initial = {}, readDocument = () => ({
  title: form.querySelector('[name="title"]')?.value || initial.document?.title || "",
  metadata: initial.document?.metadata || {},
})) {
  const owner = form.ownerDocument;
  const surface = form.querySelector("#editor-surface");
  const partSelect = form.querySelector("#editor-part");
  const outline = form.querySelector("#editor-outline-items");
  const viewNotice = form.querySelector("#editor-view-notice");
  const path = form.querySelector("#editor-selection-path");
  const menu = form.querySelector("#editor-context-menu");
  const trigger = form.querySelector("#editor-tools");
  const imageDialog = owner.querySelector("#editor-image");
  const linkDialog = owner.querySelector("#editor-link");
  const quotationDialog = owner.querySelector("#editor-quotation");
  let quotationProposal = null;
  let linkProposal = null;
  let linkTargets = [];
  let imageProposal = null;
  let parts = [], menuTarget = null;
  const bookViews = mountBookViews(form, editor, readDocument, index => navigatePart(index), showError,
    initial.presentation);
  const sectionFilter = bookViews.filter;
  const dynamicOutline = mountDynamicOutline(editor, outline, surface, showError,
    () => bookViews.expandNavigation());
  mountSectionBoundaries(form, editor, showError, initial.structure?.parts || []);
  mountTargets(form, editor, showError);

  function figureOptions() {
    return {
      caption: quotationDialog.querySelector("#editor-figure-caption").value,
      text: quotationDialog.querySelector("textarea").value,
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
      const built = buildFigure(editor, quotationProposal, options);
      const quote = built.figure.firstChild;
      const caption = built.figure.lastChild;
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
      relation.textContent = ["figcaption", "figcaptionText"].includes(caption.type.name)
        ? `CAPTION / ATTRIBUTION: ${caption.textContent}` : "CAPTION: none";
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
    const currentParts = documentParts(editor.state.doc);
    const numbering = tocNumberingEntries(editor.state.doc, currentParts);
    parts = currentParts.map((part, index) => {
      const original = initial.structure?.parts?.find(source => source.id === part.id);
      return {...part, role: part.role || original?.role, marker: tocMarker(numbering[index])};
    });
    const sections = movableSections(editor.state.doc);
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
      const label = index ? `${"  ".repeat(Math.min(part.depth, 8))}${part.kind}: ${title}` : title;
      if (index) sectionFilter.add(new Option(label, value));
      if (current) sectionFilter.value = value;
      if (current) matched = true;
      const button = owner.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.dataset.part = value;
      button.title = part.label;
      if (current) button.setAttribute("aria-current", "true");
      outline.append(button);
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
    viewNotice.textContent = scope
      ? `Showing only: ${scope.label}. Other parts are hidden, not deleted. Saving includes the whole book.`
      : bookViews.view === "book"
        ? "Whole book: generated title page, table of contents and all sections. Saving always includes all document content."
        : bookViews.view === "sections" ? "All sections. Saving always includes all document content."
          : `${bookViews.view === "title" ? "Title page" : "Table of contents"} generated from current metadata and structure. Saving always includes all document content.`;
    const folds = foldedDocumentParts(editor);
    if (folds.length) viewNotice.textContent +=
      ` ${folds.length} content range${folds.length === 1 ? "" : "s"} collapsed; saving still includes their text.`;
  }
  function choosePart(value) {
    try {
      showError("");
      closeMenu();
      bookViews.show("sections");
      showDocumentPart(editor, value === "" ? null : parts[Number(value)]);
      surface.scrollTop = 0;
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
      surface.scrollTop = 0;
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
      if (target instanceof owner.defaultView.HTMLElement) {
        surface.scrollTop += target.getBoundingClientRect().top - surface.getBoundingClientRect().top;
      }
      editor.view.focus();
    } catch (failure) { showError(failure.message); }
  }
  outline.addEventListener("click", event => {
    const view = event.target.closest("[data-book-view]");
    if (view) {
      const value = view.dataset.bookView;
      chooseView(value);
      outline.querySelector(`[data-book-view="${value}"]`)?.focus({preventScroll: true});
      return;
    }
    const button = event.target.closest("[data-part]");
    if (!button) return;
    if (button.dataset.part === "") {
      chooseView("book");
      return;
    }
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
      available(button, canEditFigure(editor));
    }
    for (const button of form.querySelectorAll("[data-mark]")) {
      available(button, textSelection);
      button.setAttribute("aria-checked", String(isInlineStyleActive(editor, button.dataset.mark)));
    }
    for (const button of form.querySelectorAll("[data-image]")) {
      available(button, !!selectedImage(editor));
    }
    for (const button of form.querySelectorAll("[data-link], [data-link-remove]")) {
      available(button, !!selectedLink(editor));
    }
    for (const button of form.querySelectorAll("[data-link-insert]")) {
      available(button, canInsertLink(editor));
    }
    const oneBlock = selection instanceof TextSelection && selection.$from.sameParent(selection.$to);
    for (const button of form.querySelectorAll("[data-block]")) {
      available(button, oneBlock && ["p", "h2", "h3", "h4", "h5", "h6", "pre", "inlineRun"]
        .includes(selection.$from.parent.type.name));
      button.setAttribute("aria-checked", String(editor.isActive(button.dataset.block)));
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
    if (selection instanceof BlockSelection) path.textContent =
      `${selection.positions.length} whole block(s) selected` +
      (selection.contiguous ? " (contiguous)." : " (gaps: select intervening blocks before extracting).") +
      " Ctrl-click toggles blocks; Escape clears selection.";
    if (selectedImage(editor)) path.textContent += " / Image";
  }
  function openMenu(x, y) {
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
    const bounds = menu.getBoundingClientRect();
    menu.style.left = `${Math.max(8, Math.min(x, owner.defaultView.innerWidth - bounds.width - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(y, owner.defaultView.innerHeight - bounds.height - 8))}px`;
    menu.querySelector("button:not(:disabled):not([hidden])")?.focus();
  }
  function openAtSelection() {
    const coords = editor.view.coordsAtPos(editor.state.selection.head);
    const bounds = surface.getBoundingClientRect();
    const visible = coords.top >= bounds.top && coords.bottom <= bounds.bottom;
    const fallback = trigger.getBoundingClientRect();
    openMenu(visible ? coords.left : fallback.left, visible ? coords.bottom : fallback.bottom);
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
    openMenu(event.clientX, event.clientY);
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
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 :
        (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      items[next].focus();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeMenu(true);
    } else if (event.key === "Tab") {
      closeMenu();
      trigger.focus();
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
      if (button.dataset.quotation === "edit") {
        quotationProposal = prepareFigure(editor);
        quotationDialog.querySelector("#editor-quotation-target").textContent =
          `${quotationProposal.kind === "quotation" ? "Quotation" : "Image"} figure. Choose the caption below; Apply changes the whole group once.`;
        const choices = quotationDialog.querySelector("#editor-figure-caption");
        choices.replaceChildren(new Option(quotationProposal.caption ? "Keep existing caption" : "No caption yet", "keep"));
        for (const candidate of quotationProposal.candidates) choices.add(new Option(candidate.label, candidate.value));
        choices.add(new Option("Write a new caption", "new"));
        if (quotationProposal.caption) choices.add(new Option("Detach caption (keep as ordinary text)", "none"));
        choices.value = "keep";
        const input = quotationDialog.querySelector("textarea");
        input.value = "";
        input.disabled = false;
        quotationDialog.querySelector("#editor-figure-title").value = "";
        quotationDialog.querySelector("#editor-figure-uncite").checked = false;
        quotationDialog.querySelector("#editor-figure-remove").hidden = !quotationProposal.figure &&
          !quotationProposal.quote;
        quotationDialog.querySelector('[role="alert"]').textContent = "";
        previewFigure();
        quotationDialog.showModal();
        choices.focus();
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
      } else if ("linkRemove" in button.dataset) applyLinkRemoval(editor, prepareLinkEdit(editor));
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
  for (const button of form.querySelectorAll("[data-mark], [data-block], [data-align], [data-move], [data-history], [data-image], [data-link], [data-link-insert], [data-link-remove], [data-quotation]")) {
    button.addEventListener("click", () => perform(button));
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
        outline.querySelector('[data-part=""]'))?.focus({preventScroll: true});
    } else if (target.closest("#editor-section-actions, #editor-outline-menu")) {
      (outline.querySelector('.editor-outline-active [data-part]') ||
        outline.querySelector('[data-part=""]'))?.focus({preventScroll: true});
    } else if (menu.contains(target)) trigger.focus({preventScroll: true});
  }
  form.addEventListener("keydown", workspaceHistory);
  surface.addEventListener("click", event => {
    const handle = event.target.closest("[data-editor-figure]");
    if (!handle) return;
    event.preventDefault();
    try {
      const position = Number(handle.dataset.editorFigure);
      editor.view.dispatch(editor.state.tr.setSelection(
        NodeSelection.create(editor.state.doc, position),
      ));
      perform(form.querySelector('[data-quotation="edit"]'));
    } catch (failure) {
      showError(failure.message);
    }
  });
  if (quotationDialog) {
    quotationDialog.querySelector("#editor-quotation-cancel").addEventListener("click",
      () => quotationDialog.close());
    quotationDialog.addEventListener("close", () => {
      quotationProposal = null;
      quotationDialog.querySelector("textarea").value = "";
      quotationDialog.querySelector("#editor-figure-preview").replaceChildren();
      editor.commands.focus();
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
        applyFigure(editor, quotationProposal, figureOptions());
        quotationDialog.close();
      } catch (failure) {
        quotationDialog.querySelector('[role="alert"]').textContent = failure.message;
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
  function outside(event) {
    if (!menu.contains(event.target) && !trigger.contains(event.target)) closeMenu();
  }
  function scrolled() { closeMenu(); }
  function pageScrolled(event) {
    if (!menu.contains(event.target)) closeMenu();
  }
  owner.addEventListener("pointerdown", outside);
  owner.addEventListener("scroll", pageScrolled, true);
  owner.defaultView.addEventListener("resize", scrolled);
  surface.addEventListener("scroll", scrolled);
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
    owner.removeEventListener("scroll", pageScrolled, true);
    owner.defaultView.removeEventListener("resize", scrolled);
  });
  const sectionMoves = mountSectionMoves(form, editor, showError, {externalMenu: true});
  const sectionCreation = mountSectionCreation(form, editor, showError);
  mountSectionManagement(form, editor, showError, sectionMoves, sectionCreation, initial);
  mountContentMoves(form, editor, showError);
  mountSectionExcerpts(form, editor, showError, initial.structure?.parts || []);
  refreshOutline();
  updateTools();
  return {refreshGenerated: () => bookViews.refresh(parts)};
}
