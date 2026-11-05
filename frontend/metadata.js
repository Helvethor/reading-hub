export function mountMetadata(form, initial, changed) {
  const people = form.querySelector("#editor-contributors");
  const dates = form.querySelector("#editor-dates");
  const topics = form.elements.subjects;
  const author = form.elements.author;
  const book = form.querySelector("#editor-organization-book");
  const originalBook = book?.checked;
  let peopleTouched = false, datesTouched = false, topicsTouched = false;
  let organizationTouched = false;
  function input(label, value, maximum) {
    const wrapper = document.createElement("label");
    wrapper.append(document.createTextNode(label));
    const field = document.createElement("input");
    field.value = value || "";
    field.maxLength = maximum;
    wrapper.append(field);
    return {wrapper, field};
  }
  function choice(label, values, value) {
    const wrapper = document.createElement("label");
    wrapper.append(document.createTextNode(label));
    const field = document.createElement("select");
    for (const [key, name] of values) {
      const option = document.createElement("option");
      option.value = key;
      option.textContent = name;
      field.append(option);
    }
    field.value = value;
    wrapper.append(field);
    return {wrapper, field};
  }
  const roleChoices = [
    ["author", "Author"], ["editor", "Editor"], ["translator", "Translator"],
    ["unknown", "Role unconfirmed"], ["exclude", "Excluded attribution"],
  ];
  const dateChoices = [
    ["publication", "Publication"], ["written", "Written"],
    ["online_edition", "Online edition"], ["unknown", "Role unconfirmed"],
  ];
  function addRow(container, fields, touch, original = null) {
    const row = document.createElement("fieldset");
    const controls = {};
    for (const [name, control] of Object.entries(fields)) {
      controls[name] = control.field;
      row.append(control.wrapper);
      control.field.addEventListener("input", touch);
      control.field.addEventListener("change", touch);
    }
    row.editorFields = controls;
    row.originalValue = original;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => { row.remove(); touch(); });
    row.append(remove);
    container.append(row);
  }
  function syncAuthors() {
    const rows = [...people.children].map(row => row.editorFields);
    author.value = rows.filter(row => row.role.value === "author").map(row => row.name.value).join(", ");
    author.readOnly = true;
  }
  function touchPeople() { peopleTouched = true; syncAuthors(); changed(); }
  function touchDates() { datesTouched = true; changed(); }
  function addPerson(value = {}) {
    addRow(people, {
      name: input("Name", value.name, 500),
      role: choice("Role", roleChoices, value.role || "unknown"),
    }, touchPeople, value);
  }
  function addDate(value = {}) {
    const controls = {
      value: input("Date (YYYY, YYYY-MM or YYYY-MM-DD)", value.value, 10),
      end_value: input("End date (optional, same precision)", value.end_value, 10),
      type: choice("Date describes", dateChoices, value.type || "unknown"),
    };
    addRow(dates, controls, touchDates, value);
  }
  function populate(value) {
    peopleTouched = datesTouched = topicsTouched = false;
    organizationTouched = false;
    if (book) book.checked = value.content_organization?.book ?? originalBook;
    people.replaceChildren();
    dates.replaceChildren();
    for (const person of value.contributors || []) addPerson(person);
    for (const date of value.date_facts || []) addDate(date);
    topics.value = (value.topics || []).join("\n");
    const publication = form.querySelector("#editor-original-publication");
    if (publication) {
      publication.textContent = value.published
        ? `Stored publication value: ${value.published}. Editing date rows replaces this value with the publication row, or clears it if no publication row remains.`
        : "No stored publication value. Untouched dates remain as captured.";
    }
    author.readOnly = false;
  }
  function read(value) {
    if (organizationTouched) value.content_organization = {book: book.checked};
    if (peopleTouched) {
      value.contributors = [...people.children].map(row => {
        const name = row.editorFields.name.value.trim();
        const original = row.originalValue || {};
        const result = {
          name, source_name: original.source_name || name,
          role: row.editorFields.role.value,
        };
        if (original.canonical && original.name === name) result.canonical = original.canonical;
        return result;
      });
      value.authors = value.contributors.filter(person => person.role === "author")
        .map(person => person.name);
      value.author = value.authors.join(", ");
      value.author_is_fallback = false;
    }
    if (datesTouched) {
      value.date_facts = [...dates.children].map(row => {
        const fields = row.editorFields;
        return {
          value: fields.value.value.trim(), type: fields.type.value,
          ...(fields.end_value.value.trim() ? {end_value: fields.end_value.value.trim()} : {}),
        };
      });
      const publication = value.date_facts.find(date => date.type === "publication");
      value.published = publication
        ? publication.value + (publication.end_value ? ` / ${publication.end_value}` : "") : "";
    }
    if (topicsTouched) {
      value.topics = topics.value.split("\n").map(value => value.trim()).filter(Boolean);
      value.topic = value.topics.join(", ");
    }
    return value;
  }
  function restore(value) {
    populate(value);
    peopleTouched = JSON.stringify(value.contributors) !== JSON.stringify(initial.contributors);
    datesTouched = JSON.stringify(value.date_facts) !== JSON.stringify(initial.date_facts);
    topicsTouched = JSON.stringify(value.topics) !== JSON.stringify(initial.topics);
    organizationTouched = JSON.stringify(value.content_organization) !==
      JSON.stringify(initial.content_organization);
    if (peopleTouched) syncAuthors();
  }
  form.querySelector("#editor-add-contributor").addEventListener("click", () => {
    if (!peopleTouched && !people.childElementCount && author.value.trim()) {
      const authors = initial.authors?.length && author.value === initial.author
        ? initial.authors : [author.value.trim()];
      for (const name of authors) addPerson({name, role: "author"});
    }
    addPerson();
    touchPeople();
    people.lastElementChild.querySelector("input").focus();
  });
  form.querySelector("#editor-add-date").addEventListener("click", () => {
    addDate();
    touchDates();
    dates.lastElementChild.querySelector("input").focus();
  });
  topics.addEventListener("input", () => { topicsTouched = true; changed(); });
  book?.addEventListener("change", () => { organizationTouched = true; changed(); });
  populate(initial);
  return {read, populate, restore};
}
