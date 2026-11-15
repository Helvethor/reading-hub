import {dateFields, editorialNoteLines, fieldLabels, parseEditorialNote, personKeys,
  titlePageFields, titlePageSelection} from "./metadata-fields.js";
import {attachContextualPanel} from "./contextual-panels.js";

const roleChoices = [
  ["author", "Author"], ["editor", "Editor"], ["translator", "Translator"],
  ["unknown", "Contributor (role unconfirmed)"], ["exclude", "Excluded attribution"],
];
const dateChoices = [
  ["publication", "Published"], ["written", "Written"], ["delivered", "Delivered"],
  ["online_edition", "Online edition"], ["unknown", "Date (role unconfirmed)"],
];
const dateLabels = {publication: "Publication date", written: "Written date", delivered: "Delivered date",
  online_edition: "Online edition date", unknown: "Date (role unconfirmed)"};
const fixedFields = new Set(["title", "book", "work_type"]);
const pageKeys = ["title_layout", "contents_page", "metadata_page"];
const explicitPages = value => Object.fromEntries(pageKeys.filter(key => key === "title_layout"
  ? ["full", "compact"].includes(value[key]) : typeof value[key] === "boolean").map(key => [key, value[key]]));
const storedDate = /^(\d{4}(?:-\d{2}){0,2})(?:\s*\/\s*(\d{4}(?:-\d{2}){0,2}))?$/;

function personRows(value) {
  const rows = (value.contributors || []).map(person => ({...person}));
  if (!rows.some(row => row.role === "author") && value.author && !value.author_is_fallback) {
    const names = value.authors?.length ? value.authors : [value.author];
    rows.unshift(...names.map(name => ({name, role: "author", source_name: name})));
  }
  if (!rows.some(row => row.role === "author")) rows.unshift({name: "", role: "author"});
  if (!rows.some(row => row.role === "translator")) rows.push({name: "", role: "translator"});
  return rows;
}

function dateRows(value) {
  const rows = (value.date_facts || []).map(date => ({...date}));
  if (!rows.some(row => row.type === "publication")) {
    const match = storedDate.exec((value.published || "").trim());
    rows.push({type: "publication", value: match?.[1] || "", end_value: match?.[2] || ""});
  }
  if (!rows.some(row => row.type === "written")) rows.push({type: "written", value: ""});
  return rows;
}

const linked = row => row.canonical?.name === row.name.trim() ? row.canonical : null;
const peopleSignature = rows => JSON.stringify(rows.filter(row => row.name.trim())
  .map(row => [row.name.trim(), row.role, linked(row)?.authority_uri ?? null]));
const dateSignature = rows => JSON.stringify(rows.filter(row => row.value.trim())
  .map(row => [row.value.trim(), (row.end_value || "").trim(), row.type]));
const topicList = text => text.split("\n").map(value => value.trim()).filter(Boolean);

export function mountMetadata(form, initial, changed) {
  const owner = form.ownerDocument;
  const people = form.querySelector("#editor-contributors");
  const dates = form.querySelector("#editor-dates");
  const topics = form.elements.subjects;
  const author = form.elements.author;
  const book = form.querySelector("#editor-organization-book");
  const sheet = people.closest("table") || people.parentElement;
  const section = sheet.closest(".editor-metadata") || form;
  const originalBook = book?.checked;
  let baseline = {}, organizationRestored = false, titleFields = null, pages = {};

  function field(tag, value, label, maximum, placeholder = "") {
    const control = owner.createElement(tag);
    if (tag === "select") {
      for (const [key, name] of value.choices) control.append(new owner.defaultView.Option(name, key));
      control.value = value.selected;
    } else {
      control.value = value || "";
      control.maxLength = maximum;
      if (placeholder) control.placeholder = placeholder;
    }
    control.setAttribute("aria-label", label);
    return control;
  }
  function cell(tag, ...children) {
    const element = owner.createElement(tag);
    element.append(...children);
    return element;
  }
  function insertRow(container, row, after) {
    if (after?.parentElement === container) after.after(row);
    else container.append(row);
    for (const control of row.querySelectorAll("input, select")) {
      control.addEventListener("input", () => update(container));
      control.addEventListener("change", () => update(container));
    }
    return row;
  }
  function showLink(row) {
    const button = row.querySelector(".editor-person-link");
    const canonical = linked({name: row.editorFields.name.value, canonical: row.canonical});
    button.textContent = canonical ? `Registered: ${canonical.name}` : "Link registered author…";
    button.title = canonical ? canonical.authority_uri || "Registered author without authority URI" : "";
    row.dataset.linked = String(Boolean(canonical));
  }
  function addPerson(value = {}, after = null) {
    const role = field("select", {choices: roleChoices, selected: value.role || "unknown"}, "Role");
    const name = field("input", value.name, "Name", 500);
    const link = owner.createElement("button");
    link.type = "button";
    link.className = "editor-person-link";
    const row = cell("tr", cell("th", role), cell("td", name), cell("td", link));
    row.dataset.metadataRow = "person";
    row.editorFields = {name, role};
    row.originalValue = value.name ? value : null;
    row.canonical = value.canonical || null;
    link.addEventListener("click", () => openLink(row));
    name.addEventListener("input", () => showLink(row));
    showLink(row);
    return insertRow(people, row, after);
  }
  function addDate(value = {}, after = null) {
    const type = field("select", {choices: dateChoices, selected: value.type || "unknown"}, "Date describes");
    const start = field("input", value.value, "Date", 10, "YYYY[-MM[-DD]]");
    const end = field("input", value.end_value, "End date (optional, same precision)", 10, "end (optional)");
    const row = cell("tr", cell("th", type), cell("td", start), cell("td", end));
    row.dataset.metadataRow = "date";
    row.editorFields = {value: start, end_value: end, type};
    return insertRow(dates, row, after);
  }
  const currentPeople = () => [...people.querySelectorAll('[data-metadata-row="person"]')].map(row => ({
    name: row.editorFields.name.value, role: row.editorFields.role.value, original: row.originalValue,
    canonical: row.canonical, sourceName: row.sourceName,
  }));
  const currentDates = () => [...dates.querySelectorAll('[data-metadata-row="date"]')].map(row => ({
    value: row.editorFields.value.value, end_value: row.editorFields.end_value.value,
    type: row.editorFields.type.value,
  }));
  const peopleChanged = () => peopleSignature(currentPeople()) !== baseline.people;
  const datesChanged = () => dateSignature(currentDates()) !== baseline.dates;
  const topicsChanged = () => JSON.stringify(topicList(topics.value)) !== baseline.topics;
  const bookChanged = () => Boolean(book) && (organizationRestored || book.checked !== baseline.book);
  const titleFieldsChanged = () => JSON.stringify(titleFields) !== baseline.titleFields;
  const pagesChanged = () => JSON.stringify(pages) !== baseline.pages;
  function syncAuthors() {
    author.value = peopleChanged()
      ? currentPeople().filter(row => row.role === "author" && row.name.trim())
        .map(row => row.name.trim()).join(", ")
      : baseline.author;
  }
  function update(container) {
    if (container === people) syncAuthors();
    if (container === people || container === dates) markTitleRows();
    changed();
  }
  function setBaseline(value) {
    baseline = {
      people: peopleSignature(personRows(value)), dates: dateSignature(dateRows(value)),
      topics: JSON.stringify(topicList((value.topics || []).join("\n"))), author: value.author || "",
      book: value.content_organization?.book ?? originalBook,
      titleFields: JSON.stringify(value.title_page_fields ?? null),
      pages: JSON.stringify(explicitPages(value)),
    };
  }
  function populate(value) {
    if (book) book.checked = value.content_organization?.book ?? originalBook;
    organizationRestored = false;
    people.querySelectorAll("[data-metadata-row]").forEach(row => row.remove());
    dates.querySelectorAll("[data-metadata-row]").forEach(row => row.remove());
    for (const person of personRows(value)) addPerson(person);
    for (const date of dateRows(value)) addDate(date);
    topics.value = (value.topics || []).join("\n");
    titleFields = Array.isArray(value.title_page_fields) ? [...value.title_page_fields] : null;
    pages = explicitPages(value);
    for (const row of sheet.querySelectorAll("tr[data-metadata-field]")) row.hidden = false;
    markTitleRows();
    const publication = form.querySelector("#editor-original-publication");
    if (publication) {
      const stored = value.published && !value.date_facts?.some(date => date.type === "publication") &&
        !storedDate.test(value.published.trim());
      publication.hidden = !stored;
      publication.textContent = stored
        ? `Stored publication text: ${value.published}. Editing dates replaces it with the Published row.` : "";
    }
    setBaseline(value);
  }
  function read(value) {
    if (bookChanged()) value.content_organization = {book: book.checked};
    if (peopleChanged()) {
      value.contributors = currentPeople().filter(row => row.name.trim()).map(row => {
        const name = row.name.trim(), original = row.original || {};
        const result = {name, source_name: original.source_name || row.sourceName || name, role: row.role};
        const canonical = linked(row);
        if (canonical) result.canonical = {name: canonical.name, authority_uri: canonical.authority_uri};
        return result;
      });
      value.authors = value.contributors.filter(person => person.role === "author")
        .map(person => person.name);
      value.author = value.authors.join(", ");
      value.author_is_fallback = false;
    }
    if (datesChanged()) {
      value.date_facts = currentDates().filter(row => row.value.trim()).map(row => ({
        value: row.value.trim(), type: row.type,
        ...(row.end_value.trim() ? {end_value: row.end_value.trim()} : {}),
      }));
      const publication = value.date_facts.find(date => date.type === "publication");
      value.published = publication
        ? publication.value + (publication.end_value ? ` / ${publication.end_value}` : "") : "";
    }
    if (topicsChanged()) {
      value.topics = topicList(topics.value);
      value.topic = value.topics.join(", ");
    }
    if (titleFieldsChanged()) {
      if (titleFields) value.title_page_fields = [...titleFields];
      else delete value.title_page_fields;
    }
    if (pagesChanged()) {
      for (const key of pageKeys) {
        if (key in pages) value[key] = pages[key];
        else delete value[key];
      }
    }
    return value;
  }
  function rowKey(row) {
    if (row?.dataset.metadataRow === "person") return personKeys[row.editorFields.role.value];
    if (row?.dataset.metadataRow === "date") return (dateFields[row.editorFields.type.value] || dateFields.unknown)[0];
    const key = row?.dataset.metadataField;
    return titlePageFields.includes(key) ? key : null;
  }
  function currentSelection() {
    return titlePageSelection(titleFields ? {title_page_fields: titleFields} : {});
  }
  function markTitleRows() {
    const shown = currentSelection();
    for (const row of sheet.querySelectorAll("tr")) {
      const key = rowKey(row);
      if (key) row.dataset.titlePage = shown.has(key) ? "shown" : "hidden";
      else delete row.dataset.titlePage;
    }
  }
  function setTitleFields(fields) {
    titleFields = fields ? titlePageFields.filter(key => fields.includes(key)) : null;
    markTitleRows();
    changed();
  }
  form.addEventListener("editor-title-fields", event => setTitleFields(event.detail.fields));
  // Generated page settings: a null value returns that setting to the work-type preset.
  form.addEventListener("editor-book-pages", event => {
    const {key, value} = event.detail;
    if (!pageKeys.includes(key)) return;
    pages = {...pages};
    if (value === null) delete pages[key];
    else pages[key] = value;
    pages = explicitPages(pages);
    changed();
  });
  function restore(value) {
    populate(value);
    setBaseline(initial);
    organizationRestored = JSON.stringify(value.content_organization) !==
      JSON.stringify(initial.content_organization);
    syncAuthors();
  }

  const menu = owner.createElement("div");
  menu.id = "editor-metadata-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "Metadata fields");
  menu.hidden = true;
  attachContextualPanel(form, menu);
  let returnFocus = null;
  function closeMenu() { menu.hidden = true; }
  function rowLabel(row) {
    if (row.dataset.metadataRow === "person") {
      const {name, role} = row.editorFields;
      return `${role.selectedOptions[0]?.textContent || "contributor"}${name.value.trim() ? ` “${name.value.trim()}”` : ""}`;
    }
    if (row.dataset.metadataRow === "date") {
      const {value, type} = row.editorFields;
      return `${dateLabels[type.value] || "date"}${value.value.trim() ? ` ${value.value.trim()}` : ""}`;
    }
    return row.querySelector("th").textContent.trim();
  }
  function focusRow(row) {
    (row?.querySelector("td input, td textarea") || form.elements.title)?.focus();
  }
  function removeRow(row) {
    const next = [...sheet.querySelectorAll("tr")].filter(other => !other.hidden && other !== row)
      .find(other => row.compareDocumentPosition(other) & owner.defaultView.Node.DOCUMENT_POSITION_FOLLOWING);
    if (row.dataset.metadataField) {
      row.hidden = true;
      const control = row.querySelector("input, textarea");
      control.value = "";
      control.dispatchEvent(new owner.defaultView.Event("input", {bubbles: true}));
    } else {
      const container = row.parentElement;
      row.remove();
      update(container);
    }
    focusRow(next);
  }
  function addField(kind, value, row) {
    if (kind === "person") return addPerson({role: value}, row);
    if (kind === "date") return addDate({type: value}, row);
    const hidden = sheet.querySelector(`tr[data-metadata-field="${value}"]`);
    hidden.hidden = false;
    return hidden;
  }
  function menuItem(label, action) {
    const button = owner.createElement("button");
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.textContent = label;
    button.addEventListener("click", () => {
      closeMenu();
      action();
    });
    menu.append(button);
    return button;
  }
  function openMenu(event, row) {
    if (event.shiftKey && event.type === "contextmenu") return;
    event.preventDefault();
    returnFocus = event.target;
    menu.replaceChildren(cell("p", "Add person"));
    for (const [role, label] of roleChoices.slice(0, 4)) {
      menuItem(label, () => focusRow(addField("person", role, row))).dataset.metadataAdd = `person:${role}`;
    }
    menu.append(cell("p", "Add date"));
    for (const [type, label] of Object.entries(dateLabels)) {
      menuItem(label, () => focusRow(addField("date", type, row))).dataset.metadataAdd = `date:${type}`;
    }
    const hiddenRows = sheet.querySelectorAll("tr[data-metadata-field][hidden]");
    if (hiddenRows.length) menu.append(cell("p", "Add field"));
    for (const hidden of hiddenRows) {
      const name = hidden.dataset.metadataField;
      menuItem(hidden.querySelector("th").textContent.trim(), () => focusRow(addField("field", name)))
        .dataset.metadataAdd = `field:${name}`;
    }
    const key = rowKey(row);
    if (key) {
      menu.append(cell("p", "Title page preview"));
      const shown = currentSelection();
      const label = fieldLabels[key] || key;
      if (shown.has(key)) {
        menuItem(`Hide ${label} on title page`, () => setTitleFields([...shown].filter(name => name !== key)))
          .dataset.titleHide = key;
      } else {
        menuItem(`Show ${label} on title page`, () => setTitleFields([...shown, key])).dataset.titleShow = key;
      }
      if (titleFields) menuItem("Reset title page fields", () => setTitleFields(null)).dataset.titleReset = "";
    }
    if (row?.dataset.metadataRow === "person") {
      menuItem("Link registered author…", () => openLink(row)).dataset.metadataLink = "";
    }
    if (row && !fixedFields.has(row.dataset.metadataField)) {
      menu.append(cell("p", "Remove field"));
      menuItem(`Remove ${rowLabel(row)}`, () => removeRow(row)).dataset.metadataRemove = "";
    }
    menu.hidden = false;
    menu.querySelector("button")?.focus();
  }
  sheet.addEventListener("contextmenu", event => openMenu(event, event.target.closest("tr")));
  sheet.addEventListener("keydown", event => {
    if (event.key === "ContextMenu" || event.shiftKey && event.key === "F10") {
      openMenu(event, event.target.closest("tr"));
    }
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
        returnFocus?.focus();
      }
    }
  });
  function outside(event) { if (!menu.contains(event.target)) closeMenu(); }
  owner.addEventListener("pointerdown", outside);
  const linkDialog = section.querySelector("#editor-person-link");
  const linkSearch = linkDialog?.querySelector("#editor-person-search");
  const linkResults = linkDialog?.querySelector("#editor-person-results");
  const linkCurrent = linkDialog?.querySelector("#editor-person-current");
  const linkError = linkDialog?.querySelector("#editor-person-error");
  const linkName = linkDialog?.querySelector("#editor-person-new-name");
  const linkUri = linkDialog?.querySelector("#editor-person-new-uri");
  let linkRow = null;
  function closeLink() {
    if (linkDialog.close) linkDialog.close();
    else linkDialog.removeAttribute("open");
    linkRow?.editorFields.name.focus();
  }
  function applyLink(canonical) {
    const {name} = linkRow.editorFields;
    if (canonical && !linkRow.originalValue?.source_name && !linkRow.sourceName) {
      linkRow.sourceName = name.value.trim() || canonical.name;
    }
    linkRow.canonical = canonical;
    if (canonical) name.value = canonical.name;
    showLink(linkRow);
    update(people);
    closeLink();
  }
  async function request(url, options = {}) {
    const response = await fetch(url, {credentials: "same-origin", ...options});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || `Request failed (${response.status}).`);
    return body;
  }
  async function searchPeople() {
    linkError.textContent = "";
    const query = linkSearch.value.trim();
    if (!query) return;
    linkResults.replaceChildren(cell("li", "Searching…"));
    try {
      const url = new URL(section.dataset.peopleUrl, owner.baseURI);
      url.searchParams.set("q", query);
      const body = await request(url);
      const found = [...body.candidates, ...body.others];
      linkResults.replaceChildren(...found.map(author => {
        const choose = owner.createElement("button");
        choose.type = "button";
        choose.textContent = `Link ${author.name}`;
        choose.dataset.authorityUri = author.authority_uri;
        choose.addEventListener("click", () => applyLink({name: author.name, authority_uri: author.authority_uri}));
        const item = cell("li", choose);
        if (author.authority_uri) item.append(" ", cell("small", author.authority_uri));
        return item;
      }));
      if (!found.length) linkResults.replaceChildren(cell("li", "No registered author matches. Register one below."));
    } catch (failure) {
      linkResults.replaceChildren();
      linkError.textContent = failure.message;
    }
  }
  async function registerPerson() {
    linkError.textContent = "";
    try {
      const body = await request(section.dataset.registerUrl, {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRFToken": form.elements.csrfmiddlewaretoken?.value || ""},
        body: JSON.stringify({name: linkName.value, authority_uri: linkUri.value}),
      });
      applyLink({name: body.name, authority_uri: body.authority_uri});
    } catch (failure) { linkError.textContent = failure.message; }
  }
  function openLink(row) {
    if (!linkDialog) return;
    linkRow = row;
    const name = row.editorFields.name.value.trim();
    const canonical = linked({name, canonical: row.canonical});
    linkCurrent.textContent = canonical
      ? `Linked to registered author ${canonical.name}${canonical.authority_uri ? ` (${canonical.authority_uri})` : ""}.`
      : `“${name || "Unnamed person"}” is not linked to a registered author.`;
    linkDialog.querySelector("#editor-person-unlink").hidden = !canonical;
    linkSearch.value = linkName.value = name;
    linkUri.value = "";
    linkError.textContent = "";
    linkResults.replaceChildren();
    if (linkDialog.showModal) linkDialog.showModal();
    else linkDialog.setAttribute("open", "");
    linkSearch.focus();
    if (name) searchPeople();
  }
  if (linkDialog) {
    linkDialog.querySelector("#editor-person-search-run").addEventListener("click", searchPeople);
    linkSearch.addEventListener("keydown", event => {
      if (event.key === "Enter") { event.preventDefault(); searchPeople(); }
    });
    linkDialog.querySelector("#editor-person-register").addEventListener("click", registerPerson);
    linkDialog.querySelector("#editor-person-unlink").addEventListener("click", () => applyLink(null));
    linkDialog.querySelector("#editor-person-close").addEventListener("click", closeLink);
  }

  const importButton = section.querySelector("#editor-metadata-import");
  const importStatus = section.querySelector("#editor-metadata-import-status");
  function setControl(control, value) {
    control.value = value;
    control.dispatchEvent(new owner.defaultView.Event("input", {bubbles: true}));
  }
  function importEditorialNote() {
    const surface = form.querySelector("#editor-surface .ProseMirror") || form.querySelector("#editor-surface");
    const lines = surface ? editorialNoteLines(surface) : [];
    if (!lines.length) {
      importStatus.textContent = "No editorial note (two or more “Label: value” lines) was found in the content.";
      return;
    }
    const suggestion = parseEditorialNote(lines);
    const filled = [];
    for (const [type, date] of Object.entries(suggestion.dates)) {
      let row = [...dates.querySelectorAll('[data-metadata-row="date"]')]
        .find(other => other.editorFields.type.value === type);
      if (row?.editorFields.value.value.trim()) continue;
      row ||= addDate({type});
      row.editorFields.end_value.value = date.end_value || "";
      setControl(row.editorFields.value, date.value);
      filled.push(dateLabels[type]);
    }
    for (const [key, value] of Object.entries(suggestion.text)) {
      const row = sheet.querySelector(`tr[data-metadata-field="${key}"]`);
      const control = row?.querySelector("input, textarea");
      if (!control || control.value.trim()) continue;
      row.hidden = false;
      setControl(control, control.matches("[data-single-line], input") ? value.replaceAll("\n", "; ") : value);
      filled.push(fieldLabels[key] || key);
    }
    importStatus.textContent = filled.length
      ? `Filled ${filled.length} empty field(s) from the editorial note: ${filled.join(", ")}. Review before saving; content is unchanged.`
      : "The editorial note found no empty fields to fill; existing values were kept.";
  }
  importButton?.addEventListener("click", importEditorialNote);
  sheet.addEventListener("keydown", event => {
    if (event.key === "Enter" && event.target.matches("textarea[data-single-line]")) event.preventDefault();
  });
  sheet.addEventListener("input", event => {
    const control = event.target;
    if (control.matches("textarea[data-single-line]") && /[\r\n]/.test(control.value)) {
      control.value = control.value.replace(/\s*[\r\n]+\s*/g, " ");
    }
  }, true);
  if (importButton) importButton.disabled = false;

  topics.addEventListener("input", () => changed());
  book?.addEventListener("change", () => changed());
  populate(initial);
  return {read, populate, restore};
}
