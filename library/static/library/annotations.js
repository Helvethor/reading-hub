(() => {
  "use strict";
  const toolbox = document.getElementById("annotation-toolbox");
  const article = document.querySelector(".reader-content");
  const toggle = document.getElementById("annotation-toggle");
  if (!toolbox || !article || !toggle) return;
  const form = document.getElementById("annotation-form");
  const apply = form.querySelector("button");
  const status = document.getElementById("annotation-status");
  const error = document.getElementById("annotation-error");
  const selectionLabel = document.getElementById("annotation-selection");
  const list = document.getElementById("annotation-list");
  const token = form.querySelector("[name=csrfmiddlewaretoken]").value;
  const kinds = ["highlight", "underline"];
  const colors = ["yellow", "green", "blue", "pink"];
  const sourceText = article.textContent;
  let annotations = [], selection = null, busy = true, loaded = false;

  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    toolbox.hidden = !toolbox.hidden;
    toggle.setAttribute("aria-expanded", String(!toolbox.hidden));
  });

  async function request(url, method = "GET", data) {
    const response = await fetch(url, {
      method, credentials: "same-origin",
      headers: {"X-CSRFToken": token, "Content-Type": "application/json", "Accept": "application/json"},
      body: data === undefined ? undefined : JSON.stringify(data),
    });
    const result = response.headers.get("content-type")?.includes("application/json")
      ? await response.json() : null;
    if (!response.ok) {
      const validation = result?.errors
        ? Object.values(result.errors).flat().map(item => item.message).join(" ") : "";
      throw new Error(result?.error || validation || (
        response.status === 403 ? "Your security token changed. Reload this page and sign in again."
          : `Annotation request failed (HTTP ${response.status}). Please retry.`
      ));
    }
    if (!result) throw new Error("Unexpected annotation response. Reload this page and sign in again.");
    return result;
  }

  function showError(message) {
    error.textContent = message;
    toolbox.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
  }

  function captureSelection() {
    const selected = document.getSelection();
    if (!selected?.rangeCount) return;
    const range = selected.getRangeAt(0);
    if (!article.contains(range.startContainer) || !article.contains(range.endContainer)) return;
    const quote = range.toString();
    selection = null;
    if (quote.trim()) {
      const prefix = document.createRange();
      prefix.selectNodeContents(article);
      prefix.setEnd(range.startContainer, range.startOffset);
      const start = prefix.toString().length;
      selection = {start, end: start + quote.length, quote};
    }
    apply.disabled = busy || !loaded || !selection;
    selectionLabel.textContent = selection
      ? `${quote.length} characters selected.` : "Select text in the article to begin.";
  }
  document.addEventListener("selectionchange", captureSelection);

  function renderMarks() {
    article.querySelectorAll("[data-private-annotation]").forEach(span => {
      span.replaceWith(...span.childNodes);
    });
    article.normalize();
    const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    let offset = 0;
    for (const node of nodes) {
      const text = node.data, start = offset, end = start + text.length;
      offset = end;
      const marks = annotations.filter(item => item.start < end && item.end > start);
      if (!marks.length) continue;
      const cuts = [...new Set([start, end, ...marks.flatMap(item => [
        Math.max(start, item.start), Math.min(end, item.end),
      ])])].sort((a, b) => a - b);
      const fragment = document.createDocumentFragment();
      for (let i = 0; i < cuts.length - 1; i++) {
        const left = cuts[i], right = cuts[i + 1];
        const active = marks.filter(item => item.start <= left && item.end >= right);
        const value = text.slice(left - start, right - start);
        if (!active.length) {
          fragment.append(document.createTextNode(value));
          continue;
        }
        const span = document.createElement("span");
        span.dataset.privateAnnotation = active.map(item => item.id).join(",");
        span.classList.add("private-annotation");
        for (const kind of kinds) {
          const last = active.filter(item => item.kind === kind).at(-1);
          if (last) span.classList.add(`${kind}-${last.color}`);
        }
        span.textContent = value;
        fragment.append(span);
      }
      node.replaceWith(fragment);
    }
  }

  function styleSelect(labelText, options, value) {
    const label = document.createElement("label");
    label.append(`${labelText} `);
    const select = document.createElement("select");
    options.forEach(option => select.add(new Option(
      option[0].toUpperCase() + option.slice(1), option,
    )));
    select.value = value;
    label.append(select);
    return {label, select};
  }

  async function action(operation) {
    if (busy || !loaded) return;
    busy = true;
    toolbox.setAttribute("aria-busy", "true");
    toolbox.querySelectorAll("button, select").forEach(control => { control.disabled = true; });
    error.textContent = "";
    status.textContent = "Saving...";
    try {
      await operation();
    } catch (failure) {
      status.textContent = "";
      showError(`No change was confirmed: ${failure.message}`);
    } finally {
      busy = false;
      toolbox.removeAttribute("aria-busy");
      toolbox.querySelectorAll("button, select").forEach(control => { control.disabled = false; });
      apply.disabled = !loaded || !selection;
    }
  }

  function addListItem(annotation) {
    const item = document.createElement("li");
    const quote = document.createElement("blockquote");
    quote.textContent = annotation.quote.length > 180
      ? annotation.quote.slice(0, 180) + "..." : annotation.quote;
    const controls = document.createElement("div");
    controls.className = "annotation-controls";
    const kind = styleSelect("Style", kinds, annotation.kind);
    const color = styleSelect("Color", colors, annotation.color);
    const view = document.createElement("button");
    view.type = "button";
    view.className = "secondary";
    view.textContent = "Find text";
    view.addEventListener("click", () => {
      const mark = [...article.querySelectorAll("[data-private-annotation]")].find(span =>
        span.dataset.privateAnnotation.split(",").includes(String(annotation.id))
      );
      if (mark) {
        mark.tabIndex = -1;
        mark.scrollIntoView({block: "center", behavior: "smooth"});
        mark.focus({preventScroll: true});
      }
    });
    const save = document.createElement("button");
    save.type = "button";
    save.className = "secondary";
    save.textContent = "Save style";
    save.addEventListener("click", () => action(async () => {
      const result = await request(`${toolbox.dataset.url}${annotation.id}/`, "PATCH", {
        kind: kind.select.value, color: color.select.value,
      });
      Object.assign(annotation, result.annotation);
      renderMarks();
      status.textContent = "Annotation style saved.";
    }));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => action(async () => {
      await request(`${toolbox.dataset.url}${annotation.id}/`, "DELETE");
      annotations = annotations.filter(value => value.id !== annotation.id);
      item.remove();
      renderMarks();
      status.textContent = `Annotation deleted. ${annotations.length} remaining.`;
      toggle.focus();
    }));
    controls.append(kind.label, color.label, save, view, remove);
    item.append(quote, controls);
    list.append(item);
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    if (!selection) return;
    const data = {...selection, kind: form.elements.kind.value, color: form.elements.color.value};
    action(async () => {
      const result = await request(toolbox.dataset.url, "POST", data);
      annotations.push(result.annotation);
      renderMarks();
      addListItem(result.annotation);
      selection = null;
      document.getSelection()?.removeAllRanges();
      selectionLabel.textContent = "Select text in the article to begin.";
      status.textContent = `Annotation saved. ${annotations.length} private annotations on this version.`;
    });
  });

  status.textContent = "Loading private annotations...";
  request(toolbox.dataset.url).then(result => {
    annotations = result.annotations;
    if (!Array.isArray(annotations) || annotations.some(item =>
      !Number.isInteger(item.start) || !Number.isInteger(item.end) ||
      item.start < 0 || item.end <= item.start || item.end > sourceText.length ||
      !kinds.includes(item.kind) || !colors.includes(item.color) ||
      sourceText.slice(item.start, item.end) !== item.quote
    )) throw new Error("Saved annotations do not match this cached version. No marks were applied.");
    renderMarks();
    annotations.forEach(addListItem);
    loaded = true;
    status.textContent = `${annotations.length} private annotations on this version.`;
  }).catch(failure => {
    status.textContent = "";
    showError(`Unable to load private annotations: ${failure.message}`);
  }).finally(() => {
    busy = false;
    apply.disabled = !loaded || !selection;
  });
})();
