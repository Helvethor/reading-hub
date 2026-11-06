import {outlineHierarchy} from "./outline.js";
import {applyTocNumbering, applyTocVisibility, tocEntryPosition, tocNumberingEntries, tocStyles,
  tocVisibilityEntries, tocVisibilityOptions} from "./toc-numbering.js";

const views = [["book", "Whole book"], ["title", "Title"], ["toc", "ToC"], ["sections", "Sections"]];

export function titlePageRows(metadata, presentation = {}) {
  const rows = [];
  const author = metadata.author || presentation.sourceName;
  if (author) rows.push([!metadata.author || metadata.author_is_fallback ? "Source website" : "Author", author]);
  const roles = {editor: "Editor", translator: "Translator", unknown: "Contributor (role unconfirmed)"};
  for (const person of metadata.contributors || []) {
    if (roles[person.role]) rows.push([roles[person.role], person.name]);
  }
  const labels = {written: "Written", publication: "Published", online_edition: "Online edition",
    unknown: "Date (role unconfirmed)"};
  for (const date of metadata.date_facts || []) {
    rows.push([labels[date.type], date.value + (date.end_value ? ` / ${date.end_value}` : "")]);
  }
  if (metadata.published && !metadata.date_facts?.some(date => date.type === "publication")) {
    rows.push(["Published", metadata.published]);
  }
  if (metadata.language) {
    const code = metadata.language.toLowerCase().replaceAll("_", "-");
    const language = code === "und" ? "Unknown language" :
      presentation.languages?.[code] || presentation.languages?.[code.split("-")[0]] || code;
    rows.push(["Language", language]);
  }
  if (metadata.topics?.length) rows.push(["Subjects", metadata.topics.join(", ")]);
  if (presentation.sourceUrl) rows.push(["Source", presentation.sourceUrl]);
  return rows;
}

export function mountBookViews(form, editor, readDocument, navigate, showError, presentation = {}) {
  const owner = form.ownerDocument;
  const surface = form.querySelector("#editor-surface");
  const primary = form.querySelector("#editor-part");
  let filter = form.querySelector("#editor-section-filter");
  if (!filter) {
    const label = owner.createElement("label");
    label.className = "editor-section-filter-control";
    label.append("Section ");
    filter = owner.createElement("select");
    filter.id = "editor-section-filter";
    label.append(filter);
    primary.after(label);
  }
  primary.replaceChildren(...views.map(([value, label]) => new Option(label, value)));
  const title = owner.createElement("section");
  title.className = "editor-generated-page editor-title-page";
  title.setAttribute("aria-label", "Generated title page");
  const toc = owner.createElement("section");
  toc.className = "editor-generated-page editor-toc-page";
  toc.setAttribute("aria-label", "Generated table of contents");
  surface.prepend(title, toc);
  const menu = owner.createElement("div");
  menu.id = "editor-toc-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "ToC numbering style");
  menu.hidden = true;
  form.append(menu);
  let selected = new Set(), selectionDoc = editor.state.doc, currentParts = [], hierarchy = [];
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
      editor.state.doc.nodeAt(tocEntryPosition(currentParts[index])).attrs["data-toc-style"] || "none"));
    for (const [style, label] of tocStyles) {
      const button = owner.createElement("button");
      button.type = "button";
      button.dataset.tocStyle = style;
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
      editor.state.doc.nodeAt(tocEntryPosition(currentParts[index])).attrs["data-toc-entry"] || "auto"));
    for (const [setting, label] of tocVisibilityOptions) {
      const button = owner.createElement("button");
      button.type = "button";
      button.dataset.tocEntry = setting;
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
    menu.hidden = false;
    const target = event.target.getBoundingClientRect(), bounds = menu.getBoundingClientRect();
    const x = event.type === "keydown" ? target.left : event.clientX;
    const y = event.type === "keydown" ? target.bottom : event.clientY;
    menu.style.left = `${Math.max(8, Math.min(x, owner.defaultView.innerWidth - bounds.width - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(y, owner.defaultView.innerHeight - bounds.height - 8))}px`;
    menu.querySelector("button")?.focus();
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
  function outside(event) { if (!menu.contains(event.target)) closeMenu(); }
  owner.addEventListener("pointerdown", outside);
  owner.addEventListener("scroll", outside, true);
  owner.defaultView.addEventListener("resize", closeMenu);
  editor.on("destroy", () => {
    owner.removeEventListener("pointerdown", outside);
    owner.removeEventListener("scroll", outside, true);
    owner.defaultView.removeEventListener("resize", closeMenu);
    menu.remove();
  });
  editor.on("transaction", ({transaction}) => {
    if (transaction.docChanged) {
      closeMenu();
      if (!transaction.getMeta("readingHubToc")) selected.clear();
      selectionDoc = editor.state.doc;
    }
  });
  let view = "book", sectionsCollapsed = false;
  function applyView() {
    primary.value = view;
    title.hidden = !["book", "title"].includes(view);
    toc.hidden = !["book", "toc"].includes(view);
    editor.view.dom.hidden = !["book", "sections"].includes(view);
    filter.closest("label").hidden = view !== "sections";
    for (const button of form.querySelectorAll("[data-book-view]")) {
      if (button.dataset.bookView === view) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    }
  }
  function refresh(parts) {
    currentParts = parts;
    if (selectionDoc !== editor.state.doc) selected.clear();
    selectionDoc = editor.state.doc;
    const document = readDocument();
    const metadata = document.metadata || {};
    const label = element("p", "Generated from current document metadata");
    label.className = "editor-generated-notice";
    const heading = element("h1", document.title || "Untitled document");
    title.replaceChildren(label, heading);
    if (metadata.subtitle) title.append(element("p", metadata.subtitle));
    const rows = owner.createElement("dl");
    rows.className = "document-metadata";
    for (const [name, value] of titlePageRows(metadata, presentation)) {
      const description = element("dd", value);
      if (name === "Source") {
        const link = element("a", value);
        link.href = value;
        link.rel = "noopener noreferrer";
        description.replaceChildren(link);
      }
      rows.append(element("dt", name), description);
    }
    title.append(rows);
    const edit = element("button", "Edit title-page metadata");
    edit.type = "button";
    edit.addEventListener("click", () => {
      const details = form.querySelector(".editor-metadata");
      if (details) details.open = true;
      form.querySelector('[name="title"]')?.focus();
    });
    title.append(edit);
    toc.replaceChildren(element("h2", "Table of contents"),
      element("p", "Ctrl-click sibling entries to select them; right-click to set numbering or hide entries from the published contents (navigation keeps them). Ordinary clicks navigate. Edit titles/order in the outline."));
    const list = owner.createElement("ol");
    hierarchy = outlineHierarchy(parts);
    const lists = new Map([[-1, list]]);
    const numbering = tocNumberingEntries(editor.state.doc, parts);
    const visibility = tocVisibilityEntries(editor.state.doc, parts);
    parts.forEach((part, index) => {
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
        } else { selected.clear(); navigate(index); }
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
    applyView();
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
        group.append(bookRow(value, label, "Content", {last: true, fold}), children);
      } else {
        group.append(bookRow(value, label, "Page"));
      }
      groups.push(group);
    }
    outline.prepend(...groups);
    applyView();
  }
  function bounds(element) {
    if (element.hidden || !element.isConnected || !element.getClientRects().length) return null;
    return element.getBoundingClientRect();
  }
  // Bounding boxes of the book-level entries, so the outline can relate them to the viewport.
  function targets() {
    const pages = {title: bounds(title), toc: bounds(toc), sections: bounds(editor.view.dom)};
    return pages;
  }
  function element(tag, text) {
    const node = owner.createElement(tag);
    node.textContent = text;
    return node;
  }
  return {
    filter, refresh, navigation, targets,
    target(value) {
      return {title, toc, sections: editor.view.dom}[value];
    },
    expandNavigation() {
      if (sectionsCollapsed) form.querySelector('[data-book-group-fold="sections"]')?.click();
    },
    get view() { return view; },
    show(value) {
      if (!views.some(([key]) => key === value)) throw new Error("Choose a supported book view.");
      view = value;
      closeMenu();
      applyView();
    },
  };
}
