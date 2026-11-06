(() => {
  "use strict";
  const text = document.getElementById("organization-specification");
  const container = document.getElementById("organization-parts");
  const add = document.getElementById("organization-add");
  if (!text || !container || !add) return;

  let specification;
  const save = () => { text.value = JSON.stringify(specification, null, 2); };

  function field(label, value, update, type = "text") {
    const wrapper = document.createElement("label");
    wrapper.append(document.createTextNode(`${label} `));
    const input = document.createElement("input");
    input.type = type;
    input.value = value;
    input.addEventListener("change", () => {
      update(input.value);
      save();
    });
    wrapper.append(input);
    return wrapper;
  }

  function action(label, callback, disabled = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.disabled = disabled;
    button.addEventListener("click", () => {
      callback();
      save();
      draw();
    });
    return button;
  }

  function draw() {
    container.replaceChildren();
    container.append(field("Work title", specification.title, value => {
      specification.title = value;
    }));

    const typeLabel = document.createElement("label");
    typeLabel.append(document.createTextNode("Work type "));
    const type = document.createElement("select");
    const separateWorkAllowed = specification.parts.length === 1 &&
      specification.parts[0].url === specification.url &&
      !specification.parts[0].section &&
      !specification.parts[0].excerpt;
    for (const [label, value] of [["Book", true], ["Separate work", false]]) {
      const option = new Option(label, String(value));
      if (!value && !separateWorkAllowed) option.disabled = true;
      type.add(option);
    }
    type.value = String(specification.book);
    type.addEventListener("change", () => {
      specification.book = type.value === "true";
      save();
    });
    typeLabel.append(type);
    container.append(typeLabel);

    specification.parts.forEach((part, index) => {
      const row = document.createElement("fieldset");
      const legend = document.createElement("legend");
      legend.textContent = `Page ${index + 1}`;
      row.append(legend);
      if (part.section) {
        const note = document.createElement("p");
        note.textContent = `Retained index section: ${part.section}`;
        row.append(note);
      } else if (part.excerpt) {
        const note = document.createElement("p");
        note.textContent = "Existing source-excerpt binding is preserved in the work specification.";
        row.append(note);
      }
      row.append(field("Retained source URL", part.url, value => { part.url = value; }, "url"));
      row.append(field("Title", part.title, value => { part.title = value; }));

      const roleLabel = document.createElement("label");
      roleLabel.append(document.createTextNode("Role "));
      const role = document.createElement("select");
      for (const value of ["preface", "chapter", "appendix", "postscript"]) {
        role.add(new Option(value, value));
      }
      role.value = part.role;
      role.addEventListener("change", () => {
        part.role = role.value;
        save();
      });
      roleLabel.append(role);
      row.append(roleLabel);

      if (index > 0) {
        row.append(action("Move up", () => {
          [specification.parts[index - 1], specification.parts[index]] =
            [specification.parts[index], specification.parts[index - 1]];
        }));
      }
      if (index < specification.parts.length - 1) {
        row.append(action("Move down", () => {
          [specification.parts[index], specification.parts[index + 1]] =
            [specification.parts[index + 1], specification.parts[index]];
        }));
      }
      const isRootPage = part.url === specification.url && !part.section && !part.excerpt;
      row.append(action(
        part.section || part.excerpt ? "Remove from this work" : "Detach into a separate work",
        () => {
          specification.parts.splice(index, 1);
        },
        isRootPage,
      ));
      if (isRootPage) {
        const note = document.createElement("p");
        note.className = "muted";
        note.textContent = "The work's own contents source cannot be detached here.";
        row.append(note);
      }
      container.append(row);
    });

    add.hidden = false;
  }

  function load() {
    try {
      const next = JSON.parse(text.value);
      if (!next || !Array.isArray(next.parts)) throw new Error("Missing page list");
      specification = next;
      draw();
    } catch {
      specification = null;
      container.textContent = "Edit the JSON specification to load the page controls.";
      add.hidden = true;
    }
  }

  text.addEventListener("change", load);
  add.addEventListener("click", () => {
    if (!specification) return;
    specification.parts.push({
      url: "",
      title: "",
      role: "chapter",
      group: "",
      use_source_headings: false,
    });
    specification.book = true;
    save();
    draw();
  });
  load();
})();
