import {outlineHierarchy} from "./outline.js";

const views = [["book", "Whole book"], ["title", "Title"], ["toc", "ToC"], ["sections", "Sections"]];

export function titlePageRows(metadata) {
  const rows = [];
  if (metadata.author) rows.push([metadata.author_is_fallback ? "Source website" : "Author", metadata.author]);
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
  if (metadata.language) rows.push(["Language", metadata.language]);
  if (metadata.topics?.length) rows.push(["Subjects", metadata.topics.join(", ")]);
  return rows;
}

export function mountBookViews(form, editor, readDocument, navigate) {
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
  function element(tag, text) {
    const node = owner.createElement(tag);
    node.textContent = text;
    return node;
  }
  function refresh(parts) {
    const document = readDocument();
    const metadata = document.metadata || {};
    const label = element("p", "Generated from current document metadata");
    label.className = "editor-generated-notice";
    const heading = element("h1", document.title || "Untitled document");
    title.replaceChildren(label, heading);
    if (metadata.subtitle) title.append(element("p", metadata.subtitle));
    const rows = owner.createElement("dl");
    rows.className = "document-metadata";
    for (const [name, value] of titlePageRows(metadata)) {
      rows.append(element("dt", name), element("dd", value));
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
      element("p", "Generated from current sections and headings; edit their titles or order in the outline."));
    const list = owner.createElement("ol");
    const hierarchy = outlineHierarchy(parts);
    const lists = new Map([[-1, list]]);
    parts.forEach((part, index) => {
      const item = owner.createElement("li");
      const button = element("button", part.label);
      button.type = "button";
      button.dataset.tocPart = String(index);
      button.addEventListener("click", () => navigate(index));
      item.append(button);
      const nested = owner.createElement("ol");
      if (hierarchy[index].children) item.append(nested);
      lists.set(index, nested);
      lists.get(hierarchy[index].parent).append(item);
    });
    if (parts.length) toc.append(list);
    else toc.append(element("p", "No sections or headings yet."));
    applyView();
  }
  function navigation(outline) {
    const root = outline.querySelector(".editor-outline-root [data-part]");
    if (root) root.dataset.bookView = "book";
    const rows = [...outline.querySelectorAll(".editor-outline-row")];
    for (const [value, label] of views.slice(1)) {
      const group = owner.createElement("div");
      group.className = "editor-book-group";
      group.dataset.bookGroup = value;
      const header = owner.createElement("div");
      header.className = "editor-book-group-heading";
      const button = element("button", label);
      button.type = "button";
      button.dataset.bookView = value;
      if (value === "sections") {
        const toggle = element("button", sectionsCollapsed ? "+" : "\u2212");
        toggle.type = "button";
        toggle.dataset.bookGroupFold = "sections";
        toggle.setAttribute("aria-label", `${sectionsCollapsed ? "Expand" : "Fold"} Sections navigation group`);
        toggle.setAttribute("aria-expanded", String(!sectionsCollapsed));
        const children = owner.createElement("div");
        children.className = "editor-book-sections";
        children.hidden = sectionsCollapsed;
        children.append(...rows);
        toggle.addEventListener("click", () => {
          sectionsCollapsed = !sectionsCollapsed;
          children.hidden = sectionsCollapsed;
          toggle.textContent = sectionsCollapsed ? "+" : "\u2212";
          toggle.setAttribute("aria-expanded", String(!sectionsCollapsed));
          toggle.setAttribute("aria-label", `${sectionsCollapsed ? "Expand" : "Fold"} Sections navigation group`);
        });
        header.append(toggle, button);
        group.append(header, children);
      } else {
        const spacer = owner.createElement("span");
        spacer.setAttribute("aria-hidden", "true");
        header.append(spacer, button);
        group.append(header);
      }
      outline.append(group);
    }
    applyView();
  }
  return {
    filter, refresh, navigation,
    expandNavigation() {
      if (sectionsCollapsed) form.querySelector("[data-book-group-fold]")?.click();
    },
    get view() { return view; },
    show(value) {
      if (!views.some(([key]) => key === value)) throw new Error("Choose a supported book view.");
      view = value;
      applyView();
    },
  };
}
