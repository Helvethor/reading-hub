(() => {
  "use strict";
  const text = document.getElementById("organization-specification");
  const container = document.getElementById("organization-parts");
  const add = document.getElementById("organization-add");
  const sections = document.getElementById("organization-sections");
  const candidates = JSON.parse(document.getElementById("organization-section-candidates").textContent) || [];
  let definitions = JSON.parse(document.getElementById("organization-excerpt-definitions").textContent) || [];
  let spec;
  function save() { text.value = JSON.stringify(spec, null, 2); }
  function field(label, value, change, choices) {
    const wrapper = document.createElement("label");
    wrapper.append(document.createTextNode(label + " "));
    const input = document.createElement(choices ? "select" : "input");
    if (choices) choices.forEach(choice => {
      const option = document.createElement("option");
      option.value = choice; option.textContent = choice; input.append(option);
    });
    input.value = value;
    input.addEventListener("change", () => { change(input.value); save(); });
    wrapper.append(input);
    return wrapper;
  }
  function button(label, action) {
    const node = document.createElement("button");
    node.type = "button"; node.textContent = label;
    node.addEventListener("click", () => { action(); save(); draw(); });
    return node;
  }
  function insertPart(part, keep = () => true) {
    const position = document.getElementById("excerpt-position").value;
    const boundary = position === "end" ? spec.parts.length : Number(position);
    const insertionIndex = spec.parts.slice(0, boundary).filter(keep).length;
    spec.parts = spec.parts.filter(keep);
    spec.parts.splice(insertionIndex, 0, part);
    spec.book = true;
  }
  function draw() {
    container.replaceChildren();
    container.append(field("Work title", spec.title, value => { spec.title = value; }));
    container.append(field("Work type", spec.book ? "book" : "separate work",
      value => { spec.book = value === "book"; }, ["book", "separate work"]));
    spec.parts.forEach((part, index) => {
      const row = document.createElement("fieldset");
      const legend = document.createElement("legend");
      legend.textContent = "Part " + (index + 1); row.append(legend);
      row.append(field("URL", part.url, value => { part.url = value; }));
      if (part.section) {
        const evidence = document.createElement("p");
        evidence.textContent = "Bounded contents-page section: " + part.section;
        row.append(evidence);
      }
      if (part.excerpt) {
        const evidence = document.createElement("p");
        const range = part.excerpt.version === 2 ? part.excerpt.blocks.join(", ")
          : `${part.excerpt.start}–${part.excerpt.end}`;
        evidence.textContent = `Source excerpt: blocks ${range}, digest ${part.excerpt.source_digest}. Original retained HTML; no chapter correction overrides.`;
        row.append(evidence);
        if (part.excerpt.version === 2) {
          const latest = definitions.find(item => item.definition === part.excerpt.definition);
          const revision = document.createElement("p");
          revision.textContent = `Pinned definition revision ${part.excerpt.revision}.`;
          row.append(revision);
          if (latest && latest.revision > part.excerpt.revision) {
            row.append(button(`Adopt revision ${latest.revision}: ${latest.name}`, () => {
              part.excerpt = structuredClone(latest.excerpt);
            }));
          }
        }
        row.append(field("Heading presentation", part.use_source_headings ? "Source headings" : "Part title",
          value => { part.use_source_headings = value === "Source headings"; },
          ["Part title", "Source headings"]));
      }
      row.append(field("Title", part.title, value => { part.title = value; }));
      row.append(field("Role", part.role, value => { part.role = value; },
        ["preface", "chapter", "appendix", "postscript"]));
      if (index > 0) row.append(button("Move up", () => {
        [spec.parts[index - 1], spec.parts[index]] = [part, spec.parts[index - 1]];
      }));
      if (index < spec.parts.length - 1) row.append(button("Move down", () => {
        [spec.parts[index], spec.parts[index + 1]] = [spec.parts[index + 1], part];
      }));
      row.append(button(part.section || part.excerpt ? "Omit section from book" : "Detach into separate work",
        () => { spec.parts.splice(index, 1); }));
      container.append(row);
    });
    sections.replaceChildren();
    candidates.filter(candidate => !spec.parts.some(part => part.section === candidate.section))
      .forEach(candidate => sections.append(button("Include index section: " + candidate.title, () => {
        spec.parts.push({...candidate});
        spec.book = true;
      })));
    const position = document.getElementById("excerpt-position");
    const selectedPosition = position.value;
    position.replaceChildren(new Option("At the end", "end"));
    spec.parts.forEach((part, index) => position.add(new Option(
      `Before part ${index + 1}: ${part.title}`, String(index)
    )));
    position.value = [...position.options].some(option => option.value === selectedPosition)
      ? selectedPosition : "end";
    drawDefinitions();
  }
  function drawDefinitions() {
    const target = document.getElementById("organization-definitions");
    target.replaceChildren();
    const urls = [...new Set(definitions.map(item => item.url))];
    for (const url of urls) {
      const group = document.createElement("fieldset");
      const legend = document.createElement("legend");
      legend.textContent = url; group.append(legend);
      const items = definitions.filter(item => item.url === url);
      const link = document.createElement("a");
      const context = new URLSearchParams(location.search);
      context.set("review_capture", items[0].capture);
      link.href = `/corrections/${items[0].capture}/?${context}`;
      link.textContent = "Define / revise excerpts on source parsing page"; group.append(link);
      const label = document.createElement("label");
      const replace = document.createElement("input"); replace.type = "checkbox";
      label.append(replace, document.createTextNode(" Replace whole-page part when including excerpts (omit unselected material)."));
      group.append(label);
      const replaceLabel = document.createElement("label");
      const replaceExcerpts = document.createElement("input"); replaceExcerpts.type = "checkbox";
      replaceLabel.append(replaceExcerpts, document.createTextNode(" Replace excerpt parts when including the whole source."));
      group.append(replaceLabel);
      const whole = button("Include whole source", () => {
        const existing = spec.parts.find(part => part.url === url && !part.excerpt);
        insertPart({url, title: existing ? existing.title : url, role: "chapter",
          group: "", use_source_headings: true},
        part => !replaceExcerpts.checked || part.url !== url || !part.excerpt);
      });
      whole.disabled = spec.parts.some(part => part.url === url && !part.section && !part.excerpt);
      group.append(whole);
      for (const item of items) {
        const included = spec.parts.some(part => part.excerpt?.definition === item.definition);
        const node = button(`Include ${item.name} · r${item.revision} · blocks ${item.excerpt.blocks.join(", ")}`, () => {
          insertPart({url, title: item.name, role: "chapter",
            group: "", use_source_headings: false, excerpt: structuredClone(item.excerpt)},
          part => !replace.checked || part.url !== url || part.section || part.excerpt);
        });
        node.disabled = included;
        group.append(node);
      }
      target.append(group);
    }
    if (!urls.length) target.textContent = "No saved excerpt definitions for these retained sources yet.";
  }
  function load() {
    try {
      spec = JSON.parse(text.value);
      if (!Array.isArray(spec.parts)) throw new Error("Missing parts");
      draw(); add.hidden = false;
      document.getElementById("organization-advanced").open = false;
    } catch {
      container.textContent = "Edit the JSON specification to load the part editor.";
      add.hidden = true;
      document.getElementById("organization-advanced").open = true;
    }
  }
  text.addEventListener("change", load);
  add.addEventListener("click", () => {
    spec.parts.push({url: "", title: "", role: "chapter", group: "", use_source_headings: false});
    spec.book = true; save(); draw();
  });
  const sourceURL = document.getElementById("excerpt-source-url");
  const first = document.getElementById("excerpt-start");
  const last = document.getElementById("excerpt-end");
  const excerptAdd = document.getElementById("excerpt-add");
  const excerptError = document.getElementById("excerpt-error");
  const excerptStatus = document.getElementById("excerpt-status");
  const excerptEvidence = document.getElementById("excerpt-evidence");
  let loadedSource = null;
  let loading = false;
  function selection() {
    return {
      version: 1,
      source_digest: loadedSource.source_digest,
      start: Number(first.value), end: Number(last.value),
    };
  }
  function showRange(clearError = true) {
    if (!loadedSource) return;
    const {start, end} = selection();
    const startBlock = loadedSource.blocks.find(block => block.index === start);
    const endBlock = loadedSource.blocks.find(block => block.index === end);
    const valid = startBlock && endBlock && start <= end && startBlock.container === endBlock.container;
    excerptAdd.disabled = !valid || loading;
    if (!valid) excerptError.textContent = "Choose ordered boundaries in the same container.";
    else if (clearError) excerptError.textContent = "";
    excerptEvidence.textContent = loadedSource.blocks
      .filter(block => block.index >= start && block.index <= end)
      .map(block => `Block ${block.index} (${block.tag}): ${block.text}`).join("\n\n");
  }
  async function fetchEvidence(extra = {}) {
    const url = new URL(location.href);
    url.search = "";
    url.searchParams.set("source_evidence", "1");
    url.searchParams.set("source_url", loadedSource ? loadedSource.url : sourceURL.value.trim());
    Object.entries(extra).forEach(([key, value]) => url.searchParams.set(key, value));
    const response = await fetch(url, {credentials: "same-origin"});
    if (response.redirected || !response.headers.get("content-type")?.includes("application/json")) {
      throw new Error("Session expired. Reload before retrying.");
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  document.getElementById("excerpt-load").addEventListener("click", async () => {
    if (loading) return;
    loading = true;
    loadedSource = null;
    excerptAdd.disabled = true;
    first.disabled = last.disabled = true;
    excerptError.textContent = "";
    excerptEvidence.textContent = "";
    sourceURL.disabled = true;
    try {
      const result = await fetchEvidence();
      loadedSource = {...result, url: sourceURL.value.trim()};
      definitions = definitions.filter(item => item.url !== loadedSource.url)
        .concat(result.definitions || []);
      drawDefinitions();
      for (const select of [first, last]) {
        select.replaceChildren();
        result.blocks.forEach(block => select.add(new Option(
          `Block ${block.index} (${block.tag}, container ${block.container}): ${block.text.slice(0, 160)}`,
          String(block.index)
        )));
        select.disabled = false;
      }
      excerptStatus.textContent = "Original source loaded. Choose inclusive boundaries, title and role.";
    } catch (failure) {
      excerptError.textContent = `Unable to load source: ${failure.message}`;
    } finally {
      loading = false;
      sourceURL.disabled = false;
      showRange(false);
    }
  });
  first.addEventListener("change", showRange);
  last.addEventListener("change", showRange);
  sourceURL.addEventListener("input", () => {
    loadedSource = null;
    excerptAdd.disabled = true;
    first.disabled = last.disabled = true;
    excerptStatus.textContent = "Load this source before selecting its blocks.";
  });
  excerptAdd.addEventListener("click", async () => {
    if (!loadedSource || loading) return;
    const title = document.getElementById("excerpt-title").value.trim();
    if (!title) {
      excerptError.textContent = "Enter an excerpt title.";
      return;
    }
    loading = true;
    excerptAdd.disabled = true;
    sourceURL.disabled = first.disabled = last.disabled = true;
    excerptError.textContent = "";
    try {
      const result = await fetchEvidence(selection());
      const nextPart = {
        url: loadedSource.url, title,
        role: document.getElementById("excerpt-role").value,
        excerpt: result.selection, group: "", use_source_headings: false,
      };
      const replace = document.getElementById("excerpt-replace").checked;
      const keep = part => !replace || part.url !== loadedSource.url || part.section || part.excerpt;
      insertPart(nextPart, keep);
      save(); draw();
      excerptEvidence.textContent = result.text;
      excerptStatus.textContent = "Excerpt added to draft. Move it among the parts, then Preview changes to save. Nothing is published yet.";
    } catch (failure) {
      excerptError.textContent = `Unable to add excerpt: ${failure.message}`;
    } finally {
      loading = false;
      sourceURL.disabled = first.disabled = last.disabled = false;
      showRange(false);
    }
  });
  load();
})();
