const roleChoices = [
  ["author", "Author"], ["editor", "Editor"], ["translator", "Translator"],
  ["unknown", "Contributor (role unconfirmed)"], ["exclude", "Excluded attribution"],
];
const dateChoices = [
  ["publication", "Published"], ["written", "Written"],
  ["online_edition", "Online edition"], ["unknown", "Date (role unconfirmed)"],
];
const dateLabels = {publication: "Publication date", written: "Written date",
  online_edition: "Online edition date", unknown: "Date (role unconfirmed)"};
const fixedFields = new Set(["title", "book"]);
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

const peopleSignature = rows => JSON.stringify(rows.filter(row => row.name.trim())
  .map(row => [row.name.trim(), row.role]));
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
  const originalBook = book?.checked;
  let baseline = {}, organizationRestored = false;

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
  function addPerson(value = {}, after = null) {
    const role = field("select", {choices: roleChoices, selected: value.role || "unknown"}, "Role");
    const name = field("input", value.name, "Name", 500);
    const row = cell("tr", cell("th", role), cell("td", name));
    row.lastElementChild.colSpan = 2;
    row.dataset.metadataRow = "person";
    row.editorFields = {name, role};
    row.originalValue = value.name ? value : null;
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
  const currentPeople = () => [...people.children].map(row => ({
    name: row.editorFields.name.value, role: row.editorFields.role.value, original: row.originalValue,
  }));
  const currentDates = () => [...dates.children].map(row => ({
    value: row.editorFields.value.value, end_value: row.editorFields.end_value.value,
    type: row.editorFields.type.value,
  }));
  const peopleChanged = () => peopleSignature(currentPeople()) !== baseline.people;
  const datesChanged = () => dateSignature(currentDates()) !== baseline.dates;
  const topicsChanged = () => JSON.stringify(topicList(topics.value)) !== baseline.topics;
  const bookChanged = () => Boolean(book) && (organizationRestored || book.checked !== baseline.book);
  function syncAuthors() {
    author.value = peopleChanged()
      ? currentPeople().filter(row => row.role === "author" && row.name.trim())
        .map(row => row.name.trim()).join(", ")
      : baseline.author;
  }
  function update(container) {
    if (container === people) syncAuthors();
    changed();
  }
  function setBaseline(value) {
    baseline = {
      people: peopleSignature(personRows(value)), dates: dateSignature(dateRows(value)),
      topics: JSON.stringify(topicList((value.topics || []).join("\n"))), author: value.author || "",
      book: value.content_organization?.book ?? originalBook,
    };
  }
  function populate(value) {
    if (book) book.checked = value.content_organization?.book ?? originalBook;
    organizationRestored = false;
    people.replaceChildren();
    dates.replaceChildren();
    for (const person of personRows(value)) addPerson(person);
    for (const date of dateRows(value)) addDate(date);
    topics.value = (value.topics || []).join("\n");
    for (const row of sheet.querySelectorAll("tr[data-metadata-field]")) row.hidden = false;
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
        const result = {name, source_name: original.source_name || name, role: row.role};
        if (original.canonical && original.name === name) result.canonical = original.canonical;
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
    return value;
  }
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
  form.append(menu);
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
    if (row && !fixedFields.has(row.dataset.metadataField)) {
      menu.append(cell("p", "Remove field"));
      menuItem(`Remove ${rowLabel(row)}`, () => removeRow(row)).dataset.metadataRemove = "";
    }
    menu.hidden = false;
    const target = event.target.getBoundingClientRect(), bounds = menu.getBoundingClientRect();
    const x = event.type === "keydown" ? target.left : event.clientX;
    const y = event.type === "keydown" ? target.bottom : event.clientY;
    menu.style.left = `${Math.max(8, Math.min(x, owner.defaultView.innerWidth - bounds.width - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(y, owner.defaultView.innerHeight - bounds.height - 8))}px`;
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
  owner.addEventListener("scroll", outside, true);
  owner.defaultView.addEventListener("resize", closeMenu);
  topics.addEventListener("input", () => changed());
  book?.addEventListener("change", () => changed());
  populate(initial);
  return {read, populate, restore};
}
