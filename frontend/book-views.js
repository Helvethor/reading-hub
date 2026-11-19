import {bookPages, factSpans, metadataEntries, pagePreset, titleLayouts, titlePageFields, titlePageRows,
  titlePageSelection, workTypes} from "./metadata-fields.js";
import {outlineHierarchy} from "./outline.js";
import {applyTocNumbering, applyTocVisibility, publicationParts, tocEntryPosition,
  tocNumberingEntries, tocStyles, tocVisibilityEntries, tocVisibilityOptions} from "./toc-numbering.js";
import {
  bodyBoundary, partLayout, resolveLayoutMetadata, resolveSeparationBoundary,
  separations, separationBoundary, setBoundarySeparation, setDocumentLayout,
} from "./part-layout.js";
import {closeHistory} from "@tiptap/pm/history";
import {attachContextualPanel, showContextMenu} from "./contextual-panels.js";

export {titlePageRows};

const views = [["book", "Whole book"], ["title", "Title"], ["toc", "ToC"], ["sections", "Sections"],
  ["metadata", "Metadata page"]];
const pageSettings = {
  title: "title_layout", toc: "contents_page", metadata: "metadata_page",
};

export function mountBookViews(form, editor, readDocument, navigate, showError, presentation = {}) {
  const owner = form.ownerDocument;
  const surface = form.querySelector("#editor-surface");
  const title = owner.createElement("section");
  title.className = "editor-generated-page editor-title-page";
  title.setAttribute("aria-label", "Title page and metadata");
  const preview = owner.createElement("div");
  preview.className = "editor-title-preview";
  title.append(preview);
  const toc = owner.createElement("section");
  toc.className = "editor-generated-page editor-toc-page";
  toc.setAttribute("aria-label", "Generated table of contents");
  surface.prepend(title, toc);
  const metadataPage = owner.createElement("section");
  metadataPage.className = "editor-generated-page editor-metadata-page";
  metadataPage.setAttribute("aria-label", "Generated metadata page");
  editor.view.dom.after(metadataPage);
  const pageBreakMarkers = new WeakMap();
  function pages() {
    const book = form.querySelector("#editor-organization-book");
    return bookPages(layoutMetadata(), book ? book.checked : Boolean(presentation.book));
  }
  function layoutMetadata(source = readDocument().metadata) {
    return resolveLayoutMetadata(editor.state.doc, source);
  }
  const isBook = () => form.querySelector("#editor-organization-book")?.checked ?? Boolean(presentation.book);
  const menu = owner.createElement("div");
  menu.id = "editor-toc-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "ToC numbering style");
  menu.hidden = true;
  attachContextualPanel(form, menu, null, editor);
  let selected = new Set(), selectionDoc = editor.state.doc, currentParts = [];
  let currentTocParts = [], hierarchy = [];
  function closeMenu() { menu.hidden = true; }
  function updateSelection() {
    for (const button of toc.querySelectorAll("[data-toc-part]")) {
      button.setAttribute("aria-pressed", String(selected.has(Number(button.dataset.tocPart))));
    }
  }
  function select(index, toggle) {
    if (toggle && selected.size && hierarchy[index].parent !== hierarchy[[...selected][0]].parent) {
      throw new Error("Select ToC entries within the same parent and level.");
    }
    if (!toggle) selected.clear();
    if (toggle && selected.has(index)) selected.delete(index);
    else selected.add(index);
    updateSelection();
  }
  function openMenu(event, index) {
    if (event.shiftKey && event.type === "contextmenu") return;
    event.preventDefault();
    if (!selected.has(index)) select(index, false);
    const proposal = {doc: editor.state.doc, indices: [...selected]};
    menu.replaceChildren();
    const caption = owner.createElement("p");
    caption.textContent = `${selected.size} ToC entry/entries - numbering style`;
    menu.append(caption);
    const styles = new Set([...selected].map(index =>
      editor.state.doc.nodeAt(tocEntryPosition(currentTocParts[index])).attrs["data-toc-style"] || "none"));
    for (const [style, label] of tocStyles) {
      const button = owner.createElement("button");
      button.type = "button";
      button.dataset.tocStyle = style;
      button.dataset.menuIcon = {
        none: "−", disc: "•", decimal: "1.", "upper-roman": "I.",
        "lower-roman": "i.", "upper-alpha": "A.", "lower-alpha": "a.",
      }[style];
      button.setAttribute("role", "menuitemradio");
      button.setAttribute("aria-checked", String(styles.size === 1 && styles.has(style)));
      button.textContent = label;
      button.addEventListener("click", () => {
        closeMenu();
        try {
          showError("");
          applyTocNumbering(editor, proposal, style);
          toc.querySelector(`[data-toc-part="${index}"]`)?.focus({preventScroll: true});
        } catch (failure) { showError(failure.message); }
      });
      menu.append(button);
    }
    const visibility = owner.createElement("p");
    visibility.textContent = "Table of contents visibility";
    menu.append(visibility);
    const settings = new Set([...selected].map(index =>
      editor.state.doc.nodeAt(tocEntryPosition(currentTocParts[index])).attrs["data-toc-entry"] || "auto"));
    for (const [setting, label] of tocVisibilityOptions) {
      const button = owner.createElement("button");
      button.type = "button";
      button.dataset.tocEntry = setting;
      button.dataset.menuIcon = setting === "hide" ? "−" : "☰";
      button.setAttribute("role", "menuitemradio");
      button.setAttribute("aria-checked", String(settings.size === 1 && settings.has(setting)));
      button.textContent = label;
      button.addEventListener("click", () => {
        closeMenu();
        try {
          showError("");
          applyTocVisibility(editor, proposal, setting);
          toc.querySelector(`[data-toc-part="${index}"]`)?.focus({preventScroll: true});
        } catch (failure) { showError(failure.message); }
      });
      menu.append(button);
    }
    showContextMenu(menu, event);
  }
  toc.addEventListener("mousedown", event => {
    if (event.target.closest("[data-toc-part]") && (event.button === 2 || event.ctrlKey || event.metaKey)) {
      event.preventDefault();
    }
  });
  toc.addEventListener("contextmenu", event => {
    const button = event.target.closest("[data-toc-part]");
    if (button) openMenu(event, Number(button.dataset.tocPart));
  });
  toc.addEventListener("keydown", event => {
    const button = event.target.closest("[data-toc-part]");
    if (button && (event.key === "ContextMenu" || event.shiftKey && event.key === "F10")) {
      openMenu(event, Number(button.dataset.tocPart));
    }
    if (event.key === "Escape") { selected.clear(); updateSelection(); closeMenu(); }
  });
  menu.addEventListener("keydown", event => {
    const buttons = [...menu.querySelectorAll("button")], index = buttons.indexOf(owner.activeElement);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      buttons[event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 :
        (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length].focus();
    }
    if (["Escape", "Tab"].includes(event.key)) {
      closeMenu();
      if (event.key === "Escape") {
        event.preventDefault();
        toc.querySelector(`[data-toc-part="${[...selected][0]}"]`)?.focus();
      }
    }
  });
  const fieldMenu = owner.createElement("div");
  fieldMenu.id = "editor-title-menu";
  fieldMenu.setAttribute("role", "menu");
  fieldMenu.setAttribute("aria-label", "Title page fields");
  fieldMenu.hidden = true;
  attachContextualPanel(form, fieldMenu, null, editor);
  let fieldReturn = null;
  function chooseFields(fields) {
    form.dispatchEvent(new owner.defaultView.CustomEvent("editor-title-fields", {detail: {fields}}));
  }
  function openFieldMenu(event) {
    if (event.shiftKey && event.type === "contextmenu") return;
    event.preventDefault();
    fieldReturn = pageReturn = event.target;
    const metadata = readDocument().metadata || {};
    const shown = titlePageSelection(metadata);
    const entries = metadataEntries(metadata, presentation);
    const key = event.target.closest("[data-field]")?.dataset.field;
    const item = (label, fields, data) => {
      const button = element("button", label);
      button.type = "button";
      button.setAttribute("role", "menuitem");
      Object.assign(button.dataset, data);
      button.dataset.menuIcon = "titleReset" in data ? "↶" : "titleHide" in data ? "−" : "+";
      button.addEventListener("click", () => {
        fieldMenu.hidden = true;
        chooseFields(fields);
        (preview.querySelector("dl") || preview).focus?.();
      });
      fieldMenu.append(button);
    };
    fieldMenu.replaceChildren(element("p", "Title page fields"));
    if (key && shown.has(key)) {
      const label = entries.find(([name]) => name === key)?.[1] || key;
      item(`Hide ${label}`, titlePageFields.filter(name => shown.has(name) && name !== key), {titleHide: key});
    }
    const hidden = [...new Map(entries.filter(([name]) => !shown.has(name)).map(entry => [entry[0], entry]))
      .values()];
    if (hidden.length) fieldMenu.append(element("p", "Show filled field"));
    for (const [name, label] of hidden) {
      item(`Show ${label}`, titlePageFields.filter(field => shown.has(field) || field === name), {titleShow: name});
    }
    if (Array.isArray(metadata.title_page_fields)) item("Reset to default fields", null, {titleReset: ""});
    pageItems(fieldMenu, "title", () => { fieldMenu.hidden = true; });
    showContextMenu(fieldMenu, event);
  }
  preview.addEventListener("contextmenu", event => {
    if (event.target.closest(".document-metadata")) openFieldMenu(event);
  });
  preview.addEventListener("keydown", event => {
    if (event.target.closest(".document-metadata") &&
      (event.key === "ContextMenu" || event.shiftKey && event.key === "F10")) openFieldMenu(event);
  });
  fieldMenu.addEventListener("keydown", event => {
    const buttons = [...fieldMenu.querySelectorAll("button")], index = buttons.indexOf(owner.activeElement);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      buttons[event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 :
        (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length].focus();
    }
    if (["Escape", "Tab"].includes(event.key)) {
      fieldMenu.hidden = true;
      if (event.key === "Escape") {
        event.preventDefault();
        fieldReturn?.focus();
      }
    }
  });
  // Generated page settings: title layout and whether the ToC and metadata pages are
  // part of the book. Explicit choices override the preset derived from the work type.
  const pageMenu = owner.createElement("div");
  pageMenu.id = "editor-page-menu";
  pageMenu.setAttribute("role", "menu");
  pageMenu.setAttribute("aria-label", "Generated page settings");
  pageMenu.hidden = true;
  attachContextualPanel(form, pageMenu, null, editor);
  let pageReturn = null;
  function setPage(key, value) {
    const current = editor.state.doc.attrs.pages || Object.fromEntries(
      Object.values(pageSettings).filter(name => name in (readDocument().metadata || {}))
        .map(name => [name, readDocument().metadata[name]]));
    const next = {...current};
    if (value === null) delete next[key];
    else next[key] = value;
    editor.view.dispatch(closeHistory(editor.state.tr.setDocAttribute("pages", next)));
    form.dispatchEvent(new owner.defaultView.CustomEvent("editor-book-pages", {detail: {key, value}}));
  }
  function presetLabel() {
    const metadata = readDocument().metadata || {};
    const type = workTypes.find(([key]) => key === metadata.work_type);
    if (type) return type[1].toLowerCase();
    const book = form.querySelector("#editor-organization-book");
    return (book ? book.checked : presentation.book) ? "book" : "article";
  }
  function pageItems(container, page, close) {
    const metadata = layoutMetadata(), current = pages(), key = pageSettings[page];
    const book = form.querySelector("#editor-organization-book");
    const preset = pagePreset(metadata.work_type, book ? book.checked : Boolean(presentation.book))[key];
    const button = (label, role, checked, value, data) => {
      const item = element("button", label);
      item.type = "button";
      item.setAttribute("role", role);
      if (checked !== null) item.setAttribute("aria-checked", String(checked));
      Object.assign(item.dataset, data);
      item.dataset.menuIcon = "pageReset" in data ? "↶" : "pageLayout" in data ? "¶" : "☰";
      item.addEventListener("click", () => {
        close();
        setPage(key, value);
        pageReturn?.focus?.({preventScroll: true});
      });
      container.append(item);
    };
    if (page === "title") {
      container.append(element("p", "Title layout"));
      const names = {full: "Full title presentation", compact: "Compact title presentation"};
      for (const layout of titleLayouts) {
        button(names[layout], "menuitemradio", current.title_layout === layout, layout, {pageLayout: layout});
      }
    } else {
      const names = {toc: "Include table of contents page", metadata: "Include metadata page at the end"};
      button(names[page], "menuitemcheckbox", current[key], !current[key], {pageInclude: page});
    }
    const explicit = key === "title_layout" ? titleLayouts.includes(metadata[key]) : typeof metadata[key] === "boolean";
    if (explicit) {
      const value = key === "title_layout" ? preset : preset ? "included" : "omitted";
      button(`Reset to ${presetLabel()} preset (${value})`, "menuitem", null, null, {pageReset: page});
    }
  }
  function layoutChoices(container, target, close) {
    const metadata = layoutMetadata();
    const doc = editor.state.doc;
    const position = target.part ? tocEntryPosition(target.part) : null;
    const boundary = target.part ? separationBoundary(doc, target.part, currentParts) :
      target.name === "body" ? bodyBoundary(doc, currentParts) : null;
    const info = boundary ? resolveSeparationBoundary(boundary, metadata, isBook()) :
      partLayout(metadata, isBook())[target.name];
    if (!info) throw new Error("This layout target is no longer available. Open its menu again.");
    const explicit = boundary ? info.explicit :
      metadata.layout?.overrides?.[target.name];
    const group = owner.createElement("div");
    group.className = "editor-menu-group editor-layout-menu";
    group.setAttribute("role", "group");
    const label = target.part ? `${target.part.displayKind || target.part.kind}: ${target.part.label}` :
      target.name === "body" ? "Content body" :
        ({title: "Title page", toc: "Table of contents", metadata: "Metadata page",
          edition: "Edition and review status"}[target.name] || target.name);
    const heading = element("span", `Separation before ${label}`);
    heading.id = `editor-layout-heading-${target.part ? position : target.name}`;
    heading.className = "editor-menu-heading";
    group.setAttribute("aria-labelledby", heading.id);
    group.append(heading);
    const inherited = boundary ? info.inherited : info.origin === "override" ?
      partLayout({...metadata, layout: {...metadata.layout, overrides: {
        ...metadata.layout?.overrides, [target.name]: undefined,
      }}}, isBook())[target.name].value : info.value;
    const description = element("span", [
      `Inherited default: ${inherited === "new-page" ? "New page" : "Continuous"}.`,
      info.conflict ? " Conflicting saved choices are retained; New page takes precedence until changed." : "",
      " Activate an active choice again to inherit.",
    ].join(""));
    description.id = `editor-layout-description-${target.part ? position : target.name}`;
    description.className = "editor-visually-hidden";
    group.append(description);
    const choices = target.name === "title" ? [] : separations;
    const row = element("div");
    row.className = "editor-layout-choices";
    for (const value of choices) {
      const label = value === "new-page" ? "New page" : "Continuous";
      const button = element("button", label);
      button.type = "button";
      button.setAttribute("role", "menuitemcheckbox");
      button.setAttribute("aria-checked", String(explicit === value));
      button.setAttribute("aria-describedby", description.id);
      button.dataset.menuIcon = value === "new-page" ? "↵" : "↔";
      button.title = `${label}; inherited default is ${inherited === "new-page" ? "New page" : "Continuous"}.`;
      button.addEventListener("click", () => {
        try {
          if (doc !== editor.state.doc) throw new Error("The document changed. Open the layout menu again.");
          const next = explicit === value ? null : value;
          if (boundary) setBoundarySeparation(editor, boundary, next);
          else {
            const layout = editor.state.doc.attrs.layout || metadata.layout ||
              {version: 1, defaults: "legacy", overrides: {}};
            const overrides = {...layout.overrides};
            if (next) overrides[target.name] = next;
            else delete overrides[target.name];
            setDocumentLayout(editor, layout.defaults === "legacy" && !Object.keys(overrides).length
              ? null : {...layout, overrides});
          }
          showError("");
          close();
        } catch (failure) { showError(failure.message); }
      });
      row.append(button);
    }
    if (choices.length) group.append(row);
    if (target.name === "title") {
      group.append(element("p", "The title page starts the document; set separation on the following part."));
    }
    container.append(group);
  }
  form.querySelector("#editor-layout-defaults")?.addEventListener("click", () => {
    setDocumentLayout(editor, {version: 1, defaults: "type", overrides: {}});
  });
  form.addEventListener("editor-layout-menu", event => {
    const {menu: targetMenu, part, doc, close} = event.detail;
    if (doc !== editor.state.doc) {
      showError("The document changed. Open the layout menu again.");
      return;
    }
    try { layoutChoices(targetMenu, {part}, close); }
    catch (failure) { showError(failure.message); }
  });
  function openPageMenu(event, page) {
    if (event.shiftKey && event.type === "contextmenu") return;
    event.preventDefault();
    closeMenus();
    pageReturn = event.target.closest("button, [tabindex]") || event.target;
    const names = {title: "Title page", toc: "Table of contents page", metadata: "Metadata page"};
    pageMenu.replaceChildren(element("p", names[page]));
    pageItems(pageMenu, page, () => { pageMenu.hidden = true; });
    layoutChoices(pageMenu, {name: page}, () => { pageMenu.hidden = true; });
    if (page === "metadata") {
      const edit = element("button", "Edit complete metadata\u2026");
      edit.type = "button";
      edit.setAttribute("role", "menuitem");
      edit.dataset.pageEdit = "metadata";
      edit.dataset.menuIcon = "✎";
      edit.addEventListener("click", () => {
        pageMenu.hidden = true;
        showMetadataTab();
      });
      pageMenu.append(edit);
    }
    showContextMenu(pageMenu, event, pageReturn);
  }
  function openLayoutMenu(event, name, label) {
    if (event.shiftKey && event.type === "contextmenu") return;
    event.preventDefault();
    closeMenus();
    pageReturn = event.target.closest("button, [tabindex]") || event.target;
    pageMenu.replaceChildren(element("p", label));
    layoutChoices(pageMenu, {name}, () => {
      pageMenu.hidden = true;
      pageReturn?.focus?.({preventScroll: true});
    });
    showContextMenu(pageMenu, event, pageReturn);
  }
  function showMetadataTab() {
    form.dispatchEvent(new owner.defaultView.CustomEvent("editor-show-tab", {detail: {tab: "metadata", focus: true}}));
  }
  const menuKey = event => event.key === "ContextMenu" || event.shiftKey && event.key === "F10";
  title.addEventListener("contextmenu", event => {
    if (!event.target.closest(".document-metadata")) openPageMenu(event, "title");
  });
  title.addEventListener("keydown", event => {
    if (menuKey(event) && !event.target.closest(".document-metadata")) openPageMenu(event, "title");
  });
  toc.addEventListener("contextmenu", event => {
    if (!event.target.closest("[data-toc-part]")) openPageMenu(event, "toc");
  });
  toc.addEventListener("keydown", event => {
    if (menuKey(event) && !event.target.closest("[data-toc-part]")) openPageMenu(event, "toc");
  });
  metadataPage.addEventListener("contextmenu", event => openPageMenu(event, "metadata"));
  metadataPage.addEventListener("keydown", event => { if (menuKey(event)) openPageMenu(event, "metadata"); });
  pageMenu.addEventListener("keydown", event => {
    const buttons = [...pageMenu.querySelectorAll("button")], index = buttons.indexOf(owner.activeElement);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      buttons[event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 :
        (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length].focus();
    }
    if (["Escape", "Tab"].includes(event.key)) {
      pageMenu.hidden = true;
      if (event.key === "Escape") {
        event.preventDefault();
        pageReturn?.focus();
      }
    }
  });
  function outside(event) {
    if (!menu.contains(event.target)) closeMenu();
    if (!fieldMenu.contains(event.target)) fieldMenu.hidden = true;
    if (!pageMenu.contains(event.target)) pageMenu.hidden = true;
  }
  function closeMenus() {
    closeMenu();
    fieldMenu.hidden = true;
    pageMenu.hidden = true;
  }
  owner.addEventListener("pointerdown", outside);
  editor.on("destroy", () => {
    owner.removeEventListener("pointerdown", outside);
    menu.remove();
    fieldMenu.remove();
    pageMenu.remove();
    metadataPage.remove();
  });
  editor.on("transaction", ({transaction}) => {
    if (transaction.docChanged) {
      closeMenu();
      if (!transaction.getMeta("readingHubToc")) selected.clear();
      selectionDoc = editor.state.doc;
    }
  });
  let sectionsCollapsed = false;
  function refresh(parts) {
    currentParts = parts;
    currentTocParts = publicationParts(parts);
    if (selectionDoc !== editor.state.doc) selected.clear();
    selectionDoc = editor.state.doc;
    const document = readDocument();
    const metadata = document.metadata || {};
    const layout = pages();
    title.classList.toggle("editor-title-compact", layout.title_layout === "compact");
    title.classList.toggle("editor-title-full", layout.title_layout === "full");
    const label = element("p", `${layout.title_layout === "compact" ? "Compact" : "Full"} title generated from current metadata. Right-click for presentation, visibility and Layout and separation.`);
    label.className = "editor-generated-notice";
    const heading = element("h1", document.title || "Untitled document");
    preview.replaceChildren(label, heading);
    if (metadata.subtitle) preview.append(element("p", metadata.subtitle));
    const compact = layout.title_layout === "compact";
    const rows = owner.createElement(compact ? "p" : "dl");
    rows.className = compact ? "document-metadata document-facts" : "document-metadata";
    rows.tabIndex = 0;
    rows.title = "Right-click (Shift+F10) to choose which filled fields appear on the title page";
    const shown = titlePageSelection(metadata);
    const entries = metadataEntries(metadata, presentation).filter(([key]) => shown.has(key));
    const spans = factSpans(entries.map(([, , value]) => String(value).length));
    for (const [index, [key, name, value]] of entries.entries()) {
      const description = element(compact ? "span" : "dd", value);
      if (key === "source_url") {
        const link = element("a", value);
        link.href = value;
        link.rel = "noopener noreferrer";
        description.replaceChildren(link);
      }
      if (compact) {
        const fact = owner.createElement("span");
        fact.className = `document-fact document-fact-span-${spans[index]}` +
          (key === "author" ? " document-fact-author" : "");
        fact.dataset.field = key;
        const term = element("span", name);
        term.className = "document-fact-label";
        description.removeAttribute("data-field");
        description.className = "document-fact-value";
        fact.append(term, " ", description);
        rows.append(fact);
        continue;
      }
      const term = element("dt", name);
      term.dataset.field = description.dataset.field = key;
      rows.append(term, description);
    }
    preview.append(rows);
    renderMetadataPage(document, metadata, layout.metadata_page);
    const currentMetadata = layoutMetadata(metadata);
    const currentBook = isBook();
    const boundaries = partLayout(currentMetadata, currentBook);
    toc.dataset.layoutBefore = boundaries.toc.value;
    metadataPage.dataset.layoutBefore = boundaries.metadata.value;
    pageBreak(metadataPage, boundaries.metadata.value === "new-page", "metadata");
    if (!layout.contents_page) {
      toc.classList.add("editor-page-disabled");
      const stub = element("p", "Not included in this book: navigation and the PDF outline still list every section. Right-click to include the table of contents page.");
      stub.className = "editor-generated-notice";
      toc.replaceChildren(element("h2", "Table of contents"), stub);
      toc.tabIndex = 0;
      hierarchy = outlineHierarchy(currentTocParts);
      updateSelection();
      pageStates();
      pageBreak(toc, boundaries.toc.value === "new-page", "table of contents");
      return;
    }
    toc.classList.remove("editor-page-disabled");
    toc.removeAttribute("tabindex");
    toc.replaceChildren(element("h2", "Table of contents"),
      element("p", "Ctrl-click sibling entries to select them; right-click to set numbering or hide entries from the published contents (navigation keeps them). Ordinary clicks navigate. Edit titles/order in the outline."));
    const list = owner.createElement("ol");
    hierarchy = outlineHierarchy(currentTocParts);
    const lists = new Map([[-1, list]]);
    const numbering = tocNumberingEntries(editor.state.doc, currentTocParts);
    const visibility = tocVisibilityEntries(editor.state.doc, currentTocParts);
    currentTocParts.forEach((part, index) => {
      const item = owner.createElement("li");
      const {style, number} = numbering[index];
      item.style.listStyleType = style;
      item.value = number;
      const button = element("button", part.label);
      button.type = "button";
      button.dataset.tocPart = String(index);
      if (!visibility[index].inToc) {
        item.classList.add("editor-toc-hidden");
        const reason = visibility[index].inherited ? "hidden with parent" :
          visibility[index].automatic ? "hidden automatically" : "hidden";
        const note = element("span", ` (${reason})`);
        note.className = "editor-toc-hidden-note";
        button.append(note);
        button.title = "Not in the published table of contents; navigation still lists it.";
      }
      button.addEventListener("click", event => {
        if (event.ctrlKey || event.metaKey) {
          try { showError(""); select(index, true); } catch (failure) { showError(failure.message); }
        } else { selected.clear(); navigate(parts.indexOf(part)); }
      });
      item.append(button);
      const nested = owner.createElement("ol");
      if (hierarchy[index].children) item.append(nested);
      lists.set(index, nested);
      lists.get(hierarchy[index].parent).append(item);
    });
    if (parts.length) toc.append(list);
    else toc.append(element("p", "No sections or headings yet."));
    updateSelection();
    pageStates();
    pageBreak(toc, boundaries.toc.value === "new-page", "table of contents");
  }
  function renderMetadataPage(document, metadata, included) {
    metadataPage.classList.toggle("editor-page-disabled", !included);
    metadataPage.tabIndex = 0;
    const heading = element("h2", "Metadata");
    const notice = element("p", included
      ? "Generated at the end of the book from the complete metadata. Right-click to omit this page."
      : "Not included in this book. Right-click to include the metadata page at the end.");
    notice.className = "editor-generated-notice";
    const edit = element("button", "Edit complete metadata");
    edit.type = "button";
    edit.className = "editor-metadata-page-edit";
    edit.addEventListener("click", showMetadataTab);
    metadataPage.replaceChildren(heading, notice, edit);
    if (!included) return;
    const table = owner.createElement("table");
    table.className = "document-metadata-table";
    const body = owner.createElement("tbody");
    const rows = [["title", "Title", document.title || "Untitled document"]];
    if (metadata.subtitle) rows.push(["subtitle", "Subtitle", metadata.subtitle]);
    rows.push(...metadataEntries(metadata, presentation));
    for (const [key, name, value] of rows) {
      const row = owner.createElement("tr");
      row.dataset.field = key;
      const cell = element("td", value);
      if (key === "source_url") {
        const link = element("a", value);
        link.href = value;
        link.rel = "noopener noreferrer";
        cell.replaceChildren(link);
      }
      row.append(element("th", name), cell);
      body.append(row);
    }
    table.append(body);
    metadataPage.append(table);
  }
  function pageBreak(page, enabled, label) {
    page.querySelector(":scope > .editor-page-break")?.remove();
    let marker = pageBreakMarkers.get(page);
    if (!enabled) {
      marker?.remove();
      return;
    }
    if (!marker) {
      marker = element("span", "Page break");
      marker.className = "editor-page-break";
      marker.classList.add("editor-page-break-before-page");
      marker.setAttribute("role", "separator");
      marker.setAttribute("aria-label", `Page break before ${label}`);
      marker.setAttribute("contenteditable", "false");
      marker.dataset.editorPageBreak = label;
      pageBreakMarkers.set(page, marker);
    }
    if (marker.nextElementSibling !== page) page.before(marker);
  }
  // Book-level entries use the same row component as section rows: tree guides, a
  // kind badge, a controls column and a title button that navigates within the book.
  function bookRow(value, label, kind, {last = false, fold = null} = {}) {
    const row = owner.createElement("div");
    row.className = "editor-outline-row editor-book-row";
    row.dataset.bookRow = value;
    const guides = owner.createElement("span");
    guides.className = "editor-outline-guides";
    guides.setAttribute("aria-hidden", "true");
    const guide = owner.createElement("span");
    guide.className = "editor-outline-branch";
    if (last) guide.classList.add("editor-outline-last");
    guides.append(guide);
    const header = owner.createElement("div");
    header.className = "editor-outline-row-header";
    const badge = element("span", kind);
    badge.className = "editor-outline-kind";
    const controls = owner.createElement("span");
    controls.className = "editor-outline-row-controls";
    if (fold) controls.append(fold);
    else {
      const spacer = owner.createElement("span");
      spacer.className = "editor-outline-spacer";
      controls.append(spacer);
    }
    header.append(badge, controls);
    const button = owner.createElement("button");
    button.type = "button";
    button.dataset.bookView = value;
    button.title = `${label} \u2014 scroll to it in the book`;
    const title = element("span", label);
    title.className = "editor-outline-title";
    button.append(title);
    row.append(guides, header, button);
    return row;
  }
  function foldButton(label, collapsed, toggle) {
    const button = element("button", collapsed ? "+" : "\u2212");
    button.type = "button";
    const update = folded => {
      button.textContent = folded ? "+" : "\u2212";
      button.setAttribute("aria-label", `${folded ? "Expand" : "Fold"} ${label} navigation group`);
      button.setAttribute("aria-expanded", String(!folded));
    };
    update(collapsed);
    button.addEventListener("click", event => {
      event.stopPropagation();
      update(toggle());
    });
    return button;
  }
  // The navigation tree starts with the generated pages and the content; the
  // whole book is the default view, not a navigation destination of its own.
  let outlineMenus = null;
  function navigation(outline) {
    const rows = [...outline.querySelectorAll(".editor-outline-row")];
    const groups = [];
    for (const [value, label] of views.slice(1)) {
      const group = owner.createElement("div");
      group.className = "editor-book-group";
      group.dataset.bookGroup = value;
      if (value === "sections") {
        const children = owner.createElement("div");
        children.className = "editor-book-sections";
        children.hidden = sectionsCollapsed;
        children.append(...rows);
        const fold = foldButton("Sections", sectionsCollapsed, () => {
          sectionsCollapsed = !sectionsCollapsed;
          children.hidden = sectionsCollapsed;
          return sectionsCollapsed;
        });
        fold.dataset.bookGroupFold = "sections";
        group.append(bookRow(value, label, "Content", {fold}), children);
      } else {
        const row = bookRow(value, value === "metadata" ? "Metadata" : label, "Page");
        row.querySelector("button").title += ". Right-click (Shift+F10) for page settings.";
        group.append(row);
      }
      groups.push(group);
    }
    outline.prepend(...groups);
    const editionRow = bookRow("edition", "Edition and review status", "Page", {last: true});
    const editionButton = editionRow.querySelector("[data-book-view]");
    delete editionButton.dataset.bookView;
    editionButton.title = "Mandatory generated end matter — right-click for Layout and separation";
    editionButton.addEventListener("click", event =>
      openLayoutMenu(event, "edition", "Edition and review status"));
    editionButton.addEventListener("contextmenu", event =>
      openLayoutMenu(event, "edition", "Edition and review status"));
    editionButton.addEventListener("keydown", event => {
      if (menuKey(event)) openLayoutMenu(event, "edition", "Edition and review status");
    });
    outline.append(editionRow);
    pageStates();
    if (outlineMenus !== outline) {
      outlineMenus = outline;
      const page = event => {
        const row = event.target.closest("[data-book-row]");
        return row && (row.dataset.bookRow in pageSettings || row.dataset.bookRow === "sections")
          ? row.dataset.bookRow : null;
      };
      outline.addEventListener("contextmenu", event => {
        const value = page(event);
        if (value === "sections") openLayoutMenu(event, "body", "Content");
        else if (value) openPageMenu(event, value);
      });
      outline.addEventListener("keydown", event => {
        const value = page(event);
        if (value && menuKey(event)) {
          if (value === "sections") openLayoutMenu(event, "body", "Content");
          else openPageMenu(event, value);
        }
      });
    }
  }
  // Navigation rows show whether a generated page is compact or omitted from the book.
  function pageStates() {
    const layout = pages();
    const states = {
      title: layout.title_layout === "compact" ? "compact" : "",
      toc: layout.contents_page ? "" : "not included",
      metadata: layout.metadata_page ? "" : "not included",
    };
    const names = {title: "Title", toc: "ToC", metadata: "Metadata"};
    for (const [value, state] of Object.entries(states)) {
      const row = form.querySelector(`[data-book-row="${value}"]`);
      if (!row) continue;
      row.querySelector(".editor-outline-title").textContent = state ? `${names[value]} (${state})` : names[value];
      row.classList.toggle("editor-book-row-disabled", value !== "title" && Boolean(state));
    }
  }
  function bounds(element) {
    if (element.hidden || !element.isConnected || !element.getClientRects().length) return null;
    return element.getBoundingClientRect();
  }
  // Bounding boxes of the book-level entries, so the outline can relate them to the viewport.
  function targets() {
    return {title: bounds(title), toc: bounds(toc), sections: bounds(editor.view.dom), metadata: bounds(metadataPage)};
  }
  function element(tag, text) {
    const node = owner.createElement(tag);
    node.textContent = text;
    return node;
  }
  return {
    refresh, navigation, targets,
    target(value) {
      return {title, toc, sections: editor.view.dom, metadata: metadataPage}[value];
    },
    expandNavigation() {
      if (sectionsCollapsed) form.querySelector('[data-book-group-fold="sections"]')?.click();
    },
    get view() { return "book"; },
    show(value) {
      if (!views.some(([key]) => key === value)) throw new Error("Choose a supported book view.");
      closeMenus();
    },
    get pages() { return pages(); },
  };
}
