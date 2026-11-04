(() => {
  const helpTargets = {
    "correction-workflow-help": "h1",
    "correction-preview-help": ".correction-preview-workspace > h2, #correction-preview",
    "correction-menu-help": "#open-preview-block-menu",
    "correction-metadata-help": '[data-override="title"], [name="title"], [data-override="subtitle"], [name="subtitle"], [data-override="language"], [name="language"], [data-override="topics"], [name="topics"]',
    "correction-covers-help": '[data-override="excluded_covers"], [data-exclude-cover]',
    "correction-dates-help": '[data-override="dates"], [data-date-field="value"], [data-date-field="type"], #add-correction-date, [data-remove-date]',
    "correction-range-help": '[data-date-field="end_value"]',
    "correction-people-help": '[data-override="people"], [data-person-field], #add-correction-person',
    "correction-identity-help": ".correction-person input:not([data-person-field]), .correction-person button, .correction-person select:not([data-person-field])",
    "correction-media-help": "[data-media-field], [data-remove-media], #add-correction-media",
    "correction-notes-help": "[data-note-field], [data-remove-note], #add-correction-note",
    "correction-save-help": '[name="reason"], button[name="action"], #reset-correction',
    "correction-history-help": ".correction-workspace > h2",
  };
  const mobileHelp = matchMedia("(max-width: 800px), (hover: none)");
  document.querySelectorAll(".context-help").forEach(help => {
    const button = help.querySelector(".help-trigger");
    const popup = help.querySelector("[popover]");
    let pinned = false;
    let dismissing = false;
    let timer;
    let revealTimer;
    let anchorElement = button;
    const selector = helpTargets[popup.id];
    function targetFor(node) {
      return node instanceof Element && selector ? node.closest(selector) : null;
    }
    function describe(target) {
      const ids = new Set((target.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
      ids.add(popup.id);
      target.setAttribute("aria-describedby", [...ids].join(" "));
      if (target.matches("h1, h2")) target.tabIndex = 0;
    }
    document.querySelectorAll(selector).forEach(describe);
    function position() {
      const anchor = anchorElement.getBoundingClientRect();
      const rect = popup.getBoundingClientRect();
      popup.style.left = `${Math.max(8, Math.min(anchor.left, innerWidth - rect.width - 8))}px`;
      const top = anchor.bottom + rect.height + 8 <= innerHeight
        ? anchor.bottom + 8 : anchor.top - rect.height - 8;
      popup.style.top = `${Math.max(8, Math.min(top, innerHeight - rect.height - 8))}px`;
    }
    function show(target = anchorElement) {
      if (dismissing) return;
      anchorElement = target;
      clearTimeout(timer);
      popup.showPopover();
      position();
    }
    function schedule(target = anchorElement) {
      clearTimeout(timer);
      clearTimeout(revealTimer);
      anchorElement = target;
      if (popup.matches(":popover-open")) return;
      revealTimer = setTimeout(() => show(target), 650);
    }
    function dismiss() {
      dismissing = true;
      pinned = false;
      clearTimeout(timer);
      clearTimeout(revealTimer);
      popup.hidePopover();
      setTimeout(() => { dismissing = false; }, 0);
    }
    function dismissLater() {
      clearTimeout(revealTimer);
      clearTimeout(timer);
      timer = setTimeout(() => {
        const active = document.activeElement;
        if (!pinned && !help.matches(":hover") && !help.contains(active)
          && (mobileHelp.matches || (!anchorElement.matches(":hover") && !targetFor(active)))) popup.hidePopover();
      }, 150);
    }
    help.addEventListener("pointerenter", event => {
      if (event.pointerType !== "touch") schedule();
    });
    help.addEventListener("pointerleave", dismissLater);
    help.addEventListener("focusin", () => schedule());
    help.addEventListener("focusout", dismissLater);
    button.addEventListener("click", event => {
      event.preventDefault();
      if (pinned) {
        dismiss();
      } else {
        clearTimeout(revealTimer);
        show(button);
        pinned = true;
      }
    });
    document.addEventListener("correction-block-menu", dismiss);
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && popup.matches(":popover-open")) dismiss();
    });
    document.addEventListener("pointerdown", event => {
      if (!help.contains(event.target) && !targetFor(event.target) && popup.matches(":popover-open")) dismiss();
    });
    document.addEventListener("pointerover", event => {
      if (mobileHelp.matches || event.pointerType === "touch") return;
      const target = targetFor(event.target);
      if (target && !target.contains(event.relatedTarget)) schedule(target);
    });
    document.addEventListener("pointerout", event => {
      if (targetFor(event.target)) dismissLater();
    });
    document.addEventListener("focusin", event => {
      if (mobileHelp.matches) return;
      const target = targetFor(event.target);
      if (target) {
        describe(target);
        schedule(target);
      }
    });
    document.addEventListener("focusout", event => {
      if (targetFor(event.target)) dismissLater();
    });
    popup.addEventListener("toggle", () => {
      const open = popup.matches(":popover-open");
      button.setAttribute("aria-expanded", String(open));
      if (!open) pinned = false;
    });
    window.addEventListener("resize", () => {
      if (popup.matches(":popover-open")) position();
    });
    window.addEventListener("scroll", () => {
      if (popup.matches(":popover-open")) position();
    }, true);
  });
  const form = document.querySelector("#correction-form");
  if (!form) return;
  const root = form.closest(".correction-workspace");
  const expected = JSON.parse(document.querySelector("#correction-expected").textContent);
  const original = JSON.parse(document.querySelector("#correction-original-metadata").textContent);
  const metadata = expected.metadata || {};
  const error = document.querySelector("#correction-error");
  const status = document.querySelector("#correction-status");
  const people = document.querySelector("#correction-people");
  const peopleOverride = form.querySelector('[data-override="people"]');
  const parsedPeople = JSON.parse(document.querySelector("#correction-parsed-people").textContent);
  const dates = document.querySelector("#correction-dates");
  const media = document.querySelector("#correction-media");
  function addMedia(association = {}) {
    const row = document.querySelector("#correction-media-template").content.firstElementChild.cloneNode(true);
    row.querySelectorAll("[data-media-field]").forEach(select => {
      select.value = association[select.dataset.mediaField] ?? "";
    });
    row.querySelector("[data-remove-media]").addEventListener("click", () => row.remove());
    media.append(row);
    return row;
  }
  (expected.media || []).forEach(addMedia);
  document.querySelector("#add-correction-media").addEventListener("click", () => {
    addMedia().querySelector("select").focus();
  });
  const notes = document.querySelector("#correction-notes");
  function addNote(repair = {}) {
    const row = document.querySelector("#correction-note-template").content.firstElementChild.cloneNode(true);
    row.querySelectorAll("[data-note-field]").forEach(select => {
      const value = repair[select.dataset.noteField];
      select.value = value && typeof value === "object" ? `${value.block}:${value.link}` : value ?? "";
    });
    row.querySelector("[data-remove-note]").addEventListener("click", () => row.remove());
    notes.append(row);
    return row;
  }
  (expected.notes || []).forEach(addNote);
  document.querySelector("#add-correction-note").addEventListener("click", () => {
    addNote().querySelector("select").focus();
  });
  const dateOverride = form.querySelector('[data-override="dates"]');
  function syncDates() {
    dates.querySelectorAll("input, select").forEach(input => {
      input.disabled = !dateOverride.checked;
    });
  }
  function addDate(date = {}) {
    const row = document.querySelector("#correction-date-template").content.firstElementChild.cloneNode(true);
    row.querySelector('[data-date-field="value"]').value = date.value || "";
    row.querySelector('[data-date-field="end_value"]').value = date.end_value || "";
    row.querySelector('[data-date-field="type"]').value = date.type || "unknown";
    row.querySelector("[data-remove-date]").addEventListener("click", () => {
      row.remove();
      dateOverride.checked = true;
      syncDates();
    });
    dates.append(row);
    return row;
  }
  for (const date of metadata.dates || original.date_facts || []) addDate(date);
  dateOverride.addEventListener("change", syncDates);
  document.querySelector("#add-correction-date").addEventListener("click", () => {
    dateOverride.checked = true;
    const row = addDate();
    syncDates();
    row.querySelector("input").focus();
  });
  function addPerson(person = {}) {
    const row = document.createElement("div");
    row.className = "correction-person";
    for (const [key, title] of [["source_name", "Source component"], ["name", "Corrected person name"]]) {
      const label = document.createElement("label");
      label.textContent = title;
      const input = document.createElement("input");
      input.dataset.personField = key;
      input.maxLength = 500;
      input.value = person[key] || "";
      input.required = true;
      label.append(input);
      row.append(label);
    }
    const label = document.createElement("label");
    label.textContent = "Role";
    const role = document.createElement("select");
    role.dataset.personField = "role";
    for (const value of ["unknown", "author", "editor", "translator", "exclude"]) {
      role.add(new Option(value, value));
    }
    role.value = person.role || "unknown";
    label.append(role);
    row.append(label);
    row.canonicalPerson = person.canonical || null;
    const identityStatus = document.createElement("p");
    identityStatus.className = "help";
    identityStatus.setAttribute("role", "status");
    function showIdentity() {
      identityStatus.textContent = row.canonicalPerson
        ? `Selected canonical person: ${row.canonicalPerson.name}. Role remains your separate decision.`
        : "Scoped name only; no canonical person selected.";
    }
    showIdentity();
    row.append(identityStatus);
    row.addEventListener("input", event => {
      if (!event.target.matches("[data-person-field]")) return;
      peopleOverride.checked = true;
      syncPeople();
      if (event.target.dataset.personField === "name") {
        row.canonicalPerson = null;
        search.value = event.target.value;
        clearMatches();
        showIdentity();
      }
    });
    row.addEventListener("change", event => {
      if (!event.target.matches("[data-person-field]")) return;
      peopleOverride.checked = true;
      syncPeople();
    });
    const searchLabel = document.createElement("label");
    searchLabel.textContent = "Canonical person search";
    const search = document.createElement("input");
    search.maxLength = 500;
    search.value = person.name || "";
    searchLabel.append(search);
    row.append(searchLabel);
    const find = document.createElement("button");
    find.type = "button";
    find.className = "secondary";
    find.textContent = "Find matching people";
    const matches = document.createElement("select");
    matches.setAttribute("aria-label", "Matching canonical people");
    matches.hidden = true;
    const use = document.createElement("button");
    use.type = "button";
    use.className = "secondary";
    use.textContent = "Use selected canonical person";
    use.hidden = true;
    const lookupStatus = document.createElement("p");
    lookupStatus.setAttribute("role", "status");
    let candidates = [];
    let generation = 0;
    function clearMatches() {
      generation++;
      matches.hidden = true;
      use.hidden = true;
      candidates = [];
      lookupStatus.textContent = "";
    }
    search.addEventListener("input", clearMatches);
    find.addEventListener("click", async () => {
      const query = search.value.trim() || row.querySelector('[data-person-field="name"]').value.trim();
      clearMatches();
      const requestGeneration = generation;
      if (!query) {
        lookupStatus.textContent = "Enter a name to search.";
        return;
      }
      find.disabled = true;
      lookupStatus.textContent = "Finding canonical people...";
      try {
        const url = new URL(root.dataset.personMatchesUrl, location.href);
        url.searchParams.set("q", query);
        const response = await fetch(url, {credentials: "same-origin"});
        if (response.redirected || !response.headers.get("content-type")?.includes("application/json")) {
          throw new Error("Session expired. Reload before retrying.");
        }
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
        if (requestGeneration !== generation || !row.isConnected) return;
        candidates = [...result.candidates, ...result.others];
        matches.replaceChildren();
        candidates.forEach((candidate, index) => matches.add(new Option(
          `${index < result.candidates.length ? "Suggested: " : ""}${candidate.name}${candidate.authority_uri ? ` (${candidate.authority_uri})` : ""}`,
          String(index)
        )));
        matches.hidden = !candidates.length;
        use.hidden = !candidates.length;
        lookupStatus.textContent = candidates.length
          ? "Best candidate is preselected when available. Confirm it explicitly; matching does not assign a role."
          : "No matching canonical people. Keep a scoped name or search another spelling.";
      } catch (failure) {
        if (requestGeneration === generation) lookupStatus.textContent = `Unable to find people: ${failure.message}`;
      } finally {
        find.disabled = false;
      }
    });
    use.addEventListener("click", () => {
      const person = candidates[Number(matches.value)];
      if (!person) return;
      row.canonicalPerson = {...person};
      row.querySelector('[data-person-field="name"]').value = person.name;
      peopleOverride.checked = true;
      syncPeople();
      showIdentity();
    });
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "secondary";
    clear.textContent = "Use scoped name instead";
    clear.addEventListener("click", () => {
      row.canonicalPerson = null;
      peopleOverride.checked = true;
      syncPeople();
      showIdentity();
    });
    row.append(find, matches, use, clear, lookupStatus);
    const separatorLabel = document.createElement("label");
    separatorLabel.textContent = "Split source component using";
    const separator = document.createElement("select");
    separator.setAttribute("aria-label", "Component separator");
    for (const [value, text] of [["/", "Slash (/)"], [";", "Semicolon (;)"], ["&", "Ampersand (&)"], [",", "Comma (,)"]]) {
      separator.add(new Option(text, value));
    }
    separatorLabel.append(separator);
    const split = document.createElement("button");
    split.type = "button";
    split.className = "secondary";
    split.textContent = "Split into separate components";
    split.addEventListener("click", () => {
      const parts = row.querySelector('[data-person-field="source_name"]').value
        .split(separator.value).map(value => value.trim()).filter(Boolean);
      if (parts.length < 2) {
        error.textContent = "The source component does not contain two names separated by the chosen separator. Edit components manually if needed.";
        return;
      }
      if (people.children.length - 1 + parts.length > 30) {
        error.textContent = "At most 30 person components are supported.";
        return;
      }
      error.textContent = "";
      for (const part of parts) {
        const component = addPerson({source_name: part, name: part, role: "unknown"});
        row.before(component);
      }
      row.remove();
      peopleOverride.checked = true;
      syncPeople();
      status.textContent = "Component split from source text. Corrected names and canonical selections were reset; assign each role explicitly. Original parsed evidence is unchanged.";
    });
    row.append(separatorLabel, split);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary";
    remove.textContent = "Remove component";
    remove.addEventListener("click", () => {
      row.remove();
      peopleOverride.checked = true;
      syncPeople();
    });
    row.append(remove);
    people.append(row);
    syncPeople();
    return row;
  }
  function syncPeople() {
    people.querySelectorAll("input[data-person-field]").forEach(input => {
      input.required = peopleOverride.checked;
    });
  }
  for (const person of metadata.people || parsedPeople) addPerson(person);
  peopleOverride.addEventListener("change", syncPeople);
  document.querySelector("#add-correction-person").addEventListener("click", () => {
    if (people.children.length >= 30) {
      error.textContent = "At most 30 person components are supported.";
      return;
    }
    peopleOverride.checked = true;
    const row = addPerson();
    row.querySelector("input").focus();
  });
  for (const checkbox of form.querySelectorAll("[data-override]")) {
    const key = checkbox.dataset.override;
    checkbox.checked = Object.hasOwn(metadata, key);
    if (key === "topics") form.elements.topics.value = (metadata.topics || original.topics || []).join("\n");
    else if (key === "excluded_covers") {
      form.querySelectorAll("[data-exclude-cover]").forEach(input => {
        input.checked = (metadata.excluded_covers || []).includes(input.value);
        input.addEventListener("change", () => { checkbox.checked = true; });
      });
    }
    else if (key !== "people" && key !== "dates" && Object.hasOwn(metadata, key)) form.elements.namedItem(key).value = metadata[key];
  }
  syncDates();
  syncPeople();
  for (const edit of expected.blocks || []) {
    const select = form.querySelector(`[data-block-action="${edit.index}"]`);
    if (select) select.value = edit.action;
  }
  const previewBody = document.querySelector("#correction-preview");
  const menuLauncher = document.querySelector("#open-preview-block-menu");
  const blockMenu = document.querySelector("#preview-block-menu");
  let headingNumbers = (expected.heading_numbers || []).map(pair => ({...pair}));
  let presentations = structuredClone(expected.presentation || []);
  let textTargets = [];
  let textTargetError = "";
  let pendingTextTargets = [];
  let menuTarget = blockMenu;
  let menuAnchor = null;
  let menuPosition = {x: 8, y: 8};
  const previousActions = new Map();
  let previewBlocks = new Map();
  let selectedBlock = null;
  const selectedBlocks = new Set();
  let dirty = false;
  function blockControl(index) {
    return form.querySelector(`[data-block-action="${index}"]`);
  }
  function blockLabel(index) {
    const block = previewBlocks.get(Number(index));
    return block ? `Block ${block.index} (${block.tag}): ${block.text.slice(0, 180)}` : `Block ${index}`;
  }
  function updateBlockSelection() {
    menuLauncher.disabled = form.getAttribute("aria-busy") === "true";
    previewBody.querySelectorAll("[data-preview-block]").forEach(node => {
      const index = Number(node.dataset.previewBlock);
      if (document.querySelector("#source-excerpts")?.dataset.selectionReady !== "true") {
        node.classList.toggle("preview-block-selected", selectedBlocks.has(index));
      }
      node.classList.toggle("preview-block-excluded", blockControl(index)?.value === "exclude");
    });
  }
  function blockDraftChanged() {
    dirty = true;
    error.textContent = "";
    status.textContent = "Block draft changed. Preview to refresh the layout; save to record a revision. Existing readers are unchanged.";
    updateBlockSelection();
  }
  function toggleBlockExclusion() {
    if (form.getAttribute("aria-busy") === "true") return;
    const restore = [...selectedBlocks].every(index => blockControl(index)?.value === "exclude");
    for (const index of selectedBlocks) {
      const control = blockControl(index);
      if (!control) continue;
      if (restore) {
        control.value = previousActions.get(index) || "";
        previousActions.delete(index);
      } else if (control.value !== "exclude") {
        previousActions.set(index, control.value);
        control.value = "exclude";
      }
    }
    presentations = presentations.filter(item => ![...selectedBlocks].some(index =>
      blockControl(index)?.value === "exclude" &&
      (item.index === index || previewBlocks.get(item.index)?.parents.includes(index))));
    blockDraftChanged();
  }
  function changeBlockType(value) {
    if (form.getAttribute("aria-busy") === "true") return;
    for (const index of selectedBlocks) {
      const control = blockControl(index);
      if (!control || control.value === "exclude") continue;
      control.value = value;
      previousActions.delete(index);
    }
    blockDraftChanged();
  }
  function closeBlockMenu(restoreFocus = false) {
    blockMenu.hidePopover();
    if (restoreFocus && menuAnchor?.isConnected) menuAnchor.focus({preventScroll: true});
  }
  function menuText(text) {
    const paragraph = document.createElement("p");
    paragraph.setAttribute("role", "none");
    paragraph.textContent = text;
    menuTarget.append(paragraph);
  }
  function menuItem(label, callback, current = null, submenu = false, keepOpen = false) {
      const button = document.createElement("button");
      button.type = "button";
      button.tabIndex = -1;
      button.textContent = label;
      button.setAttribute("role", current === null ? "menuitem" : "menuitemradio");
      if (current !== null) button.setAttribute("aria-checked", String(current));
      if (submenu) button.setAttribute("aria-haspopup", "menu");
      button.addEventListener("click", () => {
        if (!submenu && !keepOpen) closeBlockMenu(true);
        callback();
      });
      button.addEventListener("pointerenter", () => {
        if (submenu) return;
        for (const panel of button.parentElement.querySelectorAll(":scope > .preview-submenu")) {
          panel.hidden = true;
          panel.previousElementSibling?.setAttribute("aria-expanded", "false");
        }
      });
      menuTarget.append(button);
      return button;
  }
  function menuSubmenu(label, populate) {
    const parent = menuTarget;
    const panel = document.createElement("div");
    panel.className = "preview-submenu";
    panel.setAttribute("role", "menu");
    panel.setAttribute("aria-label", label);
    panel.hidden = true;
    const trigger = menuItem(label, () => open(true), null, true);
    trigger.setAttribute("aria-expanded", "false");
    parent.append(panel);
    menuTarget = panel;
    const back = menuItem("Back", () => {
      panel.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
      trigger.focus();
    }, null, false, true);
    back.className = "preview-submenu-back";
    populate();
    menuTarget = parent;
    function open(focus = false) {
      if (trigger.disabled) return;
      for (const sibling of parent.querySelectorAll(":scope > .preview-submenu")) {
        sibling.hidden = sibling !== panel;
        sibling.previousElementSibling?.setAttribute("aria-expanded", String(sibling === panel));
      }
      panel.hidden = false;
      const rect = trigger.getBoundingClientRect();
      const bounds = panel.getBoundingClientRect();
      panel.style.left = `${Math.max(8, rect.right + bounds.width + 4 < innerWidth
        ? rect.right + 4 : rect.left - bounds.width - 4)}px`;
      panel.style.top = `${Math.max(8, Math.min(rect.top, innerHeight - bounds.height - 8))}px`;
      if (focus) panel.querySelector("button:not(:disabled)")?.focus();
    }
    trigger.addEventListener("pointerenter", () => open());
    trigger.addEventListener("keydown", event => {
      if (event.key === "ArrowRight") { event.preventDefault(); event.stopPropagation(); open(true); }
    });
    panel.addEventListener("keydown", event => {
      if (event.key === "ArrowLeft" || event.key === "Escape") {
        event.preventDefault(); event.stopPropagation();
        panel.hidden = true; trigger.setAttribute("aria-expanded", "false"); trigger.focus();
      }
    });
    return trigger;
  }
  function captureTextTarget() {
    textTargets = []; textTargetError = "";
    const selection = getSelection();
    if (!selection || selection.isCollapsed || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    if (!previewBody.contains(range.commonAncestorContainer)) return;
    if (document.querySelector("#excerpt-preview-content")?.value !== "parsed") {
      textTargetError = "Switch to Parsed page to style selected text.";
      return;
    }
    const groups = new Map();
    const walker = document.createTreeWalker(previewBody, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!range.intersectsNode(node) || !node.length) continue;
      const block = node.parentElement.closest("[data-preview-block]");
      if (!block || !previewBody.contains(block)) {
        if (node.textContent.trim()) textTargetError = "The selection includes generated text without a source block.";
        continue;
      }
      const start = node === range.startContainer ? range.startOffset : 0;
      const end = node === range.endContainer ? range.endOffset : node.length;
      if (start === end) continue;
      const prefix = document.createRange();
      prefix.selectNodeContents(block); prefix.setEnd(node, 0);
      const base = [...prefix.toString()].length;
      const first = base + [...node.textContent.slice(0, start)].length;
      const last = base + [...node.textContent.slice(0, end)].length;
      const index = Number(block.dataset.previewBlock);
      const row = previewBlocks.get(index);
      const mapped = row?.text_map?.slice(first, last);
      if (!mapped?.length || mapped.some((value, i) => value === null ||
          (i && value !== mapped[i - 1] + 1))) {
        textTargetError = "This selection includes generated or changed text. Select unchanged source text.";
        continue;
      }
      const group = groups.get(index) || [];
      group.push({start: mapped[0], end: mapped.at(-1) + 1, element: node.parentElement});
      groups.set(index, group);
    }
    for (const [index, spans] of groups) {
      const merged = [];
      for (const span of spans) {
        const previous = merged.at(-1);
        if (previous?.end === span.start) {
          previous.end = span.end; previous.elements.push(span.element);
        } else merged.push({...span, elements: [span.element]});
      }
      for (const span of merged) {
        textTargets.push({index, ...span,
          text: [...previewBlocks.get(index).source_text].slice(span.start, span.end).join("")});
      }
    }
    if (!textTargets.length && !textTargetError) {
      textTargetError = "Select source text inside the normalized preview.";
    }
  }
  function presentation(index) {
    let value = presentations.find(item => item.index === index);
    if (!value) { value = {index}; presentations.push(value); }
    return value;
  }
  function previewPresentation() {
    pendingTextTargets = textTargets.map(({index, start, end}) => ({index, start, end}));
    blockDraftChanged();
    getSelection()?.removeAllRanges();
    form.requestSubmit(form.querySelector('button[value="preview"]'));
  }
  function restoreTextTarget() {
    if (!pendingTextTargets.length) return;
    const first = pendingTextTargets[0], last = pendingTextTargets.at(-1);
    function endpoint(target, end) {
      const block = previewBody.querySelector(`[data-preview-block="${target.index}"]`);
      const map = previewBlocks.get(target.index)?.text_map;
      const offset = map?.indexOf(end ? target.end - 1 : target.start);
      if (!block || offset === undefined || offset < 0) return null;
      let remaining = offset + (end ? 1 : 0);
      const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const length = [...node.textContent].length;
        if (remaining <= length) {
          return {node, offset: [...node.textContent].slice(0, remaining).join("").length};
        }
        remaining -= length;
      }
      return null;
    }
    const start = endpoint(first, false), end = endpoint(last, true);
    pendingTextTargets = [];
    if (!start || !end) return;
    const range = document.createRange();
    range.setStart(start.node, start.offset); range.setEnd(end.node, end.offset);
    const selection = getSelection();
    selection.removeAllRanges(); selection.addRange(range);
  }
  function styleActive(element, style) {
    if (element.classList.contains(`text-${style}-off`)) return false;
    const computed = getComputedStyle(element);
    const active = {
      italic: computed.fontStyle === "italic",
      bold: Number(computed.fontWeight) >= 600 || computed.fontWeight === "bold",
      underline: computed.textDecorationLine.includes("underline"),
      strikethrough: computed.textDecorationLine.includes("line-through"),
      superscript: computed.verticalAlign === "super",
      subscript: computed.verticalAlign === "sub",
    }[style];
    if (active || element === previewBody || !element.parentElement) return active;
    return styleActive(element.parentElement, style);
  }
  function presentationMenus() {
    const indices = [...selectedBlocks].filter(index => {
      const row = previewBlocks.get(index);
      return row && !["img", "hr", "unwrapped text"].includes(row.tag) && blockControl(index)?.value !== "exclude";
    });
    const selectedText = textTargets.length > 0 || Boolean(textTargetError);
    const unsupportedBlocks = indices.length !== selectedBlocks.size;
    const blockTargetError = unsupportedBlocks
      ? "Select only included text blocks to change block alignment or styling." : "";
    menuText(selectedText ? `Target: selected text${textTargets.length ? ` (${textTargets.length} ranges)` : ""}`
      : `Target: ${selectedBlocks.size} selected ${selectedBlocks.size === 1 ? "block" : "blocks"}`);
    if (textTargetError) menuText(textTargetError);
    if (!selectedText && blockTargetError) menuText(blockTargetError);
    const align = menuSubmenu("Text-align", () => {
      const current = index => presentations.find(item => item.index === index)?.align ??
        previewBlocks.get(index)?.align ?? "";
      for (const value of ["left", "right", "center", "justify"]) {
        menuItem(value[0].toUpperCase() + value.slice(1), () => {
          for (const index of indices) presentation(index).align = value;
          previewPresentation();
        }, indices.length > 0 && indices.every(index => current(index) === value));
      }
      menuItem("Use source alignment", () => {
        for (const index of indices) delete presentation(index).align;
        previewPresentation();
      });
    });
    align.disabled = selectedText || !indices.length || unsupportedBlocks;
    align.title = selectedText ? "Alignment applies to blocks; clear the text selection first." : blockTargetError;
    const styles = menuSubmenu("Styling", () => {
      const labels = {italic: "Italic", bold: "Bold", underline: "Underline",
        strikethrough: "Strikethrough", superscript: "Superscript", subscript: "Subscript"};
      for (const [style, label] of Object.entries(labels)) {
        const elements = selectedText ? textTargets.flatMap(item => {
          const block = previewBody.querySelector(`[data-preview-block="${item.index}"]`);
          return block ? item.elements : [];
        }) : indices.flatMap(index => {
          const node = previewBody.querySelector(`[data-preview-block="${index}"]`);
          if (!node) return [];
          const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
          const elements = [];
          for (let text = walker.nextNode(); text; text = walker.nextNode()) {
            if (text.textContent.trim()) elements.push(text.parentElement);
          }
          return elements;
        });
        const active = elements.length > 0 && elements.every(node => styleActive(node, style));
        const item = menuItem(label, () => {
          const values = {[style]: !active};
          if (style === "superscript" && !active) values.subscript = false;
          if (style === "subscript" && !active) values.superscript = false;
          if (selectedText) {
            for (const target of textTargets) {
              const item = presentation(target.index);
              item.ranges ||= [];
              item.ranges.push({start: target.start, end: target.end, text: target.text, styles: values});
            }
          } else {
            for (const index of indices) {
              const item = presentation(index);
              item.styles = {...item.styles, ...values};
            }
          }
          previewPresentation();
        }, active);
        item.setAttribute("role", "menuitemcheckbox");
      }
      menuItem("Reset presentation", () => {
        if (selectedText) {
          for (const target of textTargets) {
            const item = presentation(target.index);
            const source = [...previewBlocks.get(target.index).source_text];
            item.ranges = (item.ranges || []).flatMap(span => {
              if (span.end <= target.start || span.start >= target.end) return [span];
              const remaining = [];
              if (span.start < target.start) remaining.push({...span, end: target.start,
                text: source.slice(span.start, target.start).join("")});
              if (span.end > target.end) remaining.push({...span, start: target.end,
                text: source.slice(target.end, span.end).join("")});
              return remaining;
            });
          }
        } else presentations = presentations.filter(item => !indices.includes(item.index));
        previewPresentation();
      });
    });
    styles.disabled = Boolean(textTargetError) ||
      (!textTargets.length && (!indices.length || unsupportedBlocks));
    styles.title = selectedText ? textTargetError : blockTargetError;
  }
  function blockTypeMenus(controls, currentType) {
    const options = [...controls[0].options].filter(option => option.value !== "exclude" &&
      controls.every(control => [...control.options].some(other => other.value === option.value)));
    for (const option of options.filter(option => !/^h[2-6]$/.test(option.value))) {
      menuItem(option.text, () => changeBlockType(option.value),
        controls.every(control => (control.value || currentType) === option.value));
    }
    const headings = options.filter(option => /^h[2-6]$/.test(option.value));
    if (headings.length) menuSubmenu("Headings", () => {
      for (const option of headings) menuItem(option.value.toUpperCase(), () => changeBlockType(option.value),
        controls.every(control => (control.value || currentType) === option.value));
    });
  }
  function positionBlockMenu(focus = false) {
    blockMenu.showPopover();
    const rect = blockMenu.getBoundingClientRect();
    blockMenu.style.left = `${Math.max(8, Math.min(menuPosition.x, innerWidth - rect.width - 8))}px`;
    blockMenu.style.top = `${Math.max(8, Math.min(menuPosition.y + 6, innerHeight - rect.height - 8))}px`;
    if (focus) blockMenu.querySelector("button:not(:disabled)")?.focus({preventScroll: true});
  }
  function showBlockChooser(excludedOnly = false) {
    blockMenu.replaceChildren();
    menuText(excludedOnly ? "Excluded blocks" : "All source blocks");
    if (selectedBlock !== null) menuItem("Back to selected block", () => renderBlockMenu(true), null, true);
    const blocks = [...previewBlocks.values()].filter(block =>
      !excludedOnly || blockControl(block.index)?.value === "exclude");
    if (!blocks.length) menuText("No excluded blocks.");
    blocks.forEach(block => menuItem(blockLabel(block.index), () => {
      selectPreviewBlock(block.index);
      renderBlockMenu(true);
    }, null, true));
    positionBlockMenu(true);
  }
  function chooseHeadingNumber(heading) {
    blockMenu.replaceChildren();
    menuText(`Attach number to: ${heading.text}`);
    menuItem("Back to block actions", () => renderBlockMenu(true), null, true);
    const candidates = [...previewBlocks.values()].filter(block =>
      block.index < heading.index && /^(?:[0-9]{1,6}|[IVXLCDM]{1,12}|[A-Za-z])[.)]?$/.test(block.text.trim())
      && ["p", "h1", "h2", "h3", "h4", "h5", "h6"].includes(block.tag)
      && JSON.stringify(block.parents) === JSON.stringify(heading.parents)
      && blockControl(block.index)?.value !== "exclude"
      && !headingNumbers.some(pair => pair.number === block.index && pair.heading !== heading.index)
    ).reverse();
    if (!candidates.length) menuText("No preceding source number found in this container.");
    candidates.forEach(number => menuItem(blockLabel(number.index), () => {
      blockMenu.replaceChildren();
      menuText(`Number source: ${number.text}`);
      menuText(`Heading source: ${heading.text}`);
      menuText("Choose the separator. Preview validates adjacency and conflicting operations.");
      menuItem("Back to number choices", () => chooseHeadingNumber(heading), null, true);
      for (const [separator, label] of [[". ", "Period and space"], [" ", "Space only"], [") ", "Closing parenthesis and space"]]) {
        const join = /[.)]$/.test(number.text.trim()) ? " " : separator;
        menuItem(`${label}: ${number.text.trim()}${join}${heading.text}`, () => {
          headingNumbers = headingNumbers.filter(pair => pair.heading !== heading.index);
          headingNumbers.push({number: number.index, heading: heading.index, separator});
          blockDraftChanged();
          status.textContent = "Heading number attached in draft. Preview, save, then reformat to update readers. Source text is unchanged.";
        });
      }
      positionBlockMenu(true);
    }, null, true));
    positionBlockMenu(true);
  }
  function renderBlockMenu(focus = false) {
    blockMenu.replaceChildren();
    menuTarget = blockMenu;
    presentationMenus();
    document.dispatchEvent(new CustomEvent("correction-selection-menu", {
      detail: {menuItem, menuText, back: () => renderBlockMenu(true),
        position: () => positionBlockMenu(true), close: () => closeBlockMenu()},
    }));
    const block = previewBlocks.get(selectedBlock);
    const control = block ? blockControl(block.index) : null;
    if (textTargets.length || textTargetError) {
      const headings = menuSubmenu("Headings", () => {
        menuText("Clear selected text to change block headings.");
      });
      headings.disabled = true;
      menuText("Clear selected text for heading, alignment and exclusion actions on blocks.");
      positionBlockMenu(focus);
      return;
    }
    if (!control) {
      menuText("Select blocks in the preview.");
      if (document.querySelector("#excerpt-preview-content")?.value !== "parsed") {
        menuText("Parsing corrections are available in Parsed page.");
      }
      menuItem("Find excluded blocks", () => showBlockChooser(true), null, true);
      menuItem("Find source block", () => showBlockChooser(), null, true);
      positionBlockMenu(focus);
      return;
    }
    if (selectedBlocks.size > 1) {
      menuText(`${selectedBlocks.size} blocks selected`);
      const controls = [...selectedBlocks].map(blockControl);
      const restore = controls.every(value => value?.value === "exclude");
      menuItem(restore ? "Restore selected blocks" : "Exclude selected blocks", toggleBlockExclusion);
      if (controls.every(value => value && value.value !== "exclude")) {
        blockTypeMenus(controls, "");
      }
      positionBlockMenu(focus);
      return;
    }
    const currentType = control.value === "exclude"
      ? previousActions.get(selectedBlock) || block.tag : control.value || block.tag;
    const names = {p: "Paragraph", subtitle: "Subtitle", h1: "Heading 1", h2: "Heading 2",
      h3: "Heading 3", h4: "Heading 4", h5: "Heading 5", h6: "Heading 6"};
    menuText(`Current draft type: ${names[currentType] || currentType}${control.value === "exclude" ? " (excluded)" : ""}`);
    menuText(`Source: Block ${block.index} (${block.tag})`);
    const numberPair = headingNumbers.find(pair => pair.heading === block.index || pair.number === block.index);
    if (numberPair) {
      menuText(`Number relationship: ${blockLabel(numberPair.number)} → ${blockLabel(numberPair.heading)}`);
      menuItem("Detach heading number", () => {
        headingNumbers = headingNumbers.filter(pair => pair !== numberPair);
        blockDraftChanged();
      });
    }
    const nested = [...previewBlocks.values()].filter(value => value.parents.includes(block.index)).length;
    if (nested) menuText(`Container scope: includes ${nested} nested source blocks.`);
    menuItem(control.value === "exclude" ? "Restore block" : "Exclude block", toggleBlockExclusion);
    if (control.value !== "exclude" && control.options.length > 2) {
      blockTypeMenus([control], currentType);
    }
    if (control.value !== "exclude" && /^h[1-6]$/.test(currentType) && !numberPair) {
      menuItem("Attach preceding number…", () => chooseHeadingNumber(block), null, true);
    }
    menuItem("Show source block", () => {
      blockMenu.replaceChildren();
      menuText(`Source: Block ${block.index} (${block.tag})`);
      menuItem("Back to block actions", () => renderBlockMenu(true), null, true);
      const evidence = document.createElement("pre");
      evidence.className = "correction-source";
      evidence.setAttribute("role", "none");
      evidence.textContent = block.text || "This source block contains no text.";
      blockMenu.append(evidence);
      positionBlockMenu(true);
    }, null, true);
    block.parents.forEach(index => menuItem(`Select container: ${blockLabel(index)}`, () => {
      selectPreviewBlock(index);
      renderBlockMenu(true);
    }, null, true));
    menuItem("Find excluded blocks", () => showBlockChooser(true), null, true);
    menuItem("Find source block", () => showBlockChooser(), null, true);
    positionBlockMenu(focus);
  }
  function openBlockMenu(node, x, y, keyboard = false) {
    if (form.getAttribute("aria-busy") === "true") return;
    captureTextTarget();
    if (node !== menuLauncher) selectPreviewBlock(Number(node.dataset.previewBlock));
    document.dispatchEvent(new Event("correction-block-menu"));
    menuAnchor = node;
    menuPosition = {x, y};
    renderBlockMenu(keyboard);
  }
  blockMenu.addEventListener("keydown", event => {
    if (event.target.matches("input")) return;
    const scope = event.target.closest('[role="menu"]') || blockMenu;
    const items = [...scope.querySelectorAll(":scope > button:not(:disabled)")];
    const index = items.indexOf(document.activeElement);
    let next;
    if (event.key === "ArrowDown") next = (index + 1) % items.length;
    else if (event.key === "ArrowUp") next = (index - 1 + items.length) % items.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    else if (event.key === "Tab") {
      closeBlockMenu(true);
      return;
    }
    if (next !== undefined) {
      event.preventDefault();
      items[next].focus();
    }
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && blockMenu.matches(":popover-open")) {
      event.preventDefault();
      closeBlockMenu(true);
    }
  });
  document.addEventListener("pointerdown", event => {
    if (!blockMenu.contains(event.target) && blockMenu.matches(":popover-open")) closeBlockMenu();
  });
  window.addEventListener("resize", () => closeBlockMenu());
  window.addEventListener("scroll", event => {
    if (!blockMenu.contains(event.target)) closeBlockMenu();
  }, true);
  function selectPreviewBlock(index) {
    const block = previewBlocks.get(index);
    if (!block) return;
    selectedBlock = index;
    selectedBlocks.clear(); selectedBlocks.add(index);
    document.dispatchEvent(new CustomEvent("correction-select-block", {detail: {index}}));
    updateBlockSelection();
  }
  document.addEventListener("preview-selection-changed", event => {
    selectedBlocks.clear();
    for (const index of event.detail.indices) {
      if (previewBlocks.has(index)) selectedBlocks.add(index);
    }
    selectedBlock = [...selectedBlocks].at(-1) ?? null;
    updateBlockSelection();
  });
  document.addEventListener("preview-selection-actions", event => {
    openBlockMenu(menuLauncher, event.detail.x, event.detail.y, event.detail.keyboard);
  });
  menuLauncher.addEventListener("click", event => {
    const rect = menuLauncher.getBoundingClientRect();
    openBlockMenu(menuLauncher, rect.left, rect.bottom, true);
  });
  previewBody.addEventListener("click", event => {
    if (event.defaultPrevented) return;
    if (form.getAttribute("aria-busy") === "true") return;
    if (!getSelection()?.isCollapsed) return;
    const node = event.target.closest("[data-preview-block]");
    if (node && previewBody.contains(node)) selectPreviewBlock(Number(node.dataset.previewBlock));
  });
  previewBody.addEventListener("contextmenu", event => {
    if (event.defaultPrevented) return;
    const node = event.target.closest("[data-preview-block]");
    if (!node || !previewBody.contains(node)) return;
    event.preventDefault();
    openBlockMenu(node, event.clientX, event.clientY, event.clientX === 0 && event.clientY === 0);
  });
  previewBody.addEventListener("keydown", event => {
    if (event.defaultPrevented) return;
    if (form.getAttribute("aria-busy") === "true") return;
    if (!["Enter", " ", "ContextMenu"].includes(event.key) && !(event.shiftKey && event.key === "F10")) return;
    const node = event.target.closest("[data-preview-block]");
    if (!node || !previewBody.contains(node)) return;
    event.preventDefault();
    if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
      const rect = node.getBoundingClientRect();
      openBlockMenu(node, rect.left, rect.top, true);
    } else selectPreviewBlock(Number(node.dataset.previewBlock));
  });
  form.querySelectorAll("[data-block-action]").forEach(control => {
    control.addEventListener("change", () => {
      previousActions.delete(Number(control.dataset.blockAction));
      blockDraftChanged();
    });
  });
  function showPreview(result) {
    closeBlockMenu();
    document.querySelector("#correction-preview-warning").textContent = result.error || "";
    document.querySelector("#correction-preview-title").textContent = result.title;
    document.querySelector("#correction-preview-metadata").textContent = JSON.stringify(result.metadata, null, 2);
    previewBody.innerHTML = result.html;
    previewBlocks = new Map((result.blocks || []).map(block => [block.index, block]));
    if (!previewBlocks.has(selectedBlock)) selectedBlock = null;
    previewBody.querySelectorAll("[data-preview-block]").forEach(node => {
      node.tabIndex = 0;
      node.setAttribute("aria-label", blockLabel(Number(node.dataset.previewBlock)));
      node.setAttribute("aria-haspopup", "menu");
    });
    dirty = false;
    textTargets = [];
    for (const index of selectedBlocks) if (!previewBlocks.has(index)) selectedBlocks.delete(index);
    updateBlockSelection();
    document.dispatchEvent(new CustomEvent("correction-preview-rendered", {detail: result}));
    restoreTextTarget();
  }
  showPreview(JSON.parse(document.querySelector("#correction-initial-preview").textContent));
  form.addEventListener("invalid", event => {
    for (let parent = event.target.parentElement; parent && parent !== form; parent = parent.parentElement) {
      if (parent.tagName === "DETAILS") parent.open = true;
    }
  }, true);
  document.querySelector("#reset-correction").addEventListener("click", () => {
    closeBlockMenu();
    media.replaceChildren();
    notes.replaceChildren();
    headingNumbers = [];
    presentations = [];
    textTargets = [];
    previousActions.clear();
    form.querySelectorAll("[data-override]").forEach(input => { input.checked = false; });
    form.querySelectorAll("[data-block-action]").forEach(select => { select.value = ""; });
    syncDates();
    syncPeople();
    dirty = true;
    updateBlockSelection();
    status.textContent = "Baseline selected. Preview or save to create a superseding revision.";
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!event.submitter || form.getAttribute("aria-busy") === "true") return;
    closeBlockMenu();
    const controls = [...form.querySelectorAll("button, input, select, textarea")]
      .map(control => [control, control.disabled]);
    error.textContent = "";
    status.textContent = "";
    try {
      const metadata = {};
      for (const checkbox of form.querySelectorAll("[data-override]:checked")) {
        const key = checkbox.dataset.override;
        if (key === "people") {
          metadata.people = [...people.children].map(row => {
            const person = Object.fromEntries(
              [...row.querySelectorAll("[data-person-field]")].map(input => [input.dataset.personField, input.value.trim()])
            );
            if (row.canonicalPerson) person.canonical = row.canonicalPerson;
            return person;
          });
        } else if (key === "topics") {
          metadata.topics = form.elements.topics.value.split("\n").map(text => text.trim()).filter(Boolean);
        } else if (key === "dates") {
          metadata.dates = [...dates.children].map(row => Object.fromEntries(
            [...row.querySelectorAll("[data-date-field]")]
              .filter(input => input.dataset.dateField !== "end_value" || input.value.trim())
              .map(input => [input.dataset.dateField, input.value.trim()])
          ));
        } else if (key === "excluded_covers") {
          metadata.excluded_covers = [...form.querySelectorAll("[data-exclude-cover]:checked")].map(input => input.value);
        } else metadata[key] = form.elements.namedItem(key).value.trim();
      }
      const blocks = [...form.querySelectorAll("[data-block-action]")].filter(select => select.value)
        .map(select => ({index: Number(select.dataset.blockAction), action: select.value}));
      const expected = {};
      if (headingNumbers.length) expected.heading_numbers = headingNumbers.map(pair => ({...pair}));
      const activePresentation = presentations.filter(item =>
        item.align !== undefined || Object.keys(item.styles || {}).length || item.ranges?.length);
      if (activePresentation.length) expected.presentation = activePresentation;
      if (notes.children.length) expected.notes = [...notes.children].map(row =>
        Object.fromEntries([...row.querySelectorAll("[data-note-field]")].map(select => {
          let value = null;
          if (select.value !== "") {
            if (select.dataset.noteField === "target") value = Number(select.value);
            else {
              const [block, link] = select.value.split(":").map(Number);
              value = {block, link};
            }
          }
          return [select.dataset.noteField, value];
        }))
      );
      if (Object.keys(metadata).length) expected.metadata = metadata;
      if (blocks.length) expected.blocks = blocks;
      if (media.children.length) expected.media = [...media.children].map(row =>
        Object.fromEntries([...row.querySelectorAll("[data-media-field]")].map(select =>
          [select.dataset.mediaField, select.value === "" ? null : Number(select.value)]
        ))
      );
      form.setAttribute("aria-busy", "true");
      controls.forEach(([control]) => { control.disabled = true; });
      const response = await fetch(root.dataset.updateUrl, {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": form.elements.csrfmiddlewaretoken.value},
        body: JSON.stringify({action: event.submitter.value, expected, revision: Number(root.dataset.revision), reason: form.elements.reason.value})
      });
      if (response.redirected || !response.headers.get("content-type")?.includes("application/json")) {
        throw new Error("Session or security token expired. Reload before retrying.");
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      showPreview(result);
      dirty = !result.revision;
      if (result.revision) {
        previousActions.clear();
        root.dataset.revision = result.revision;
        status.textContent = `Saved revision ${result.revision}. New imports/reformats will use it; existing versions are unchanged. Reload to see the updated history.`;
      } else status.textContent = "Preview updated; changes are not saved yet.";
    } catch (failure) {
      error.textContent = `Unable to complete correction: ${failure.message} Inputs have been kept.`;
    } finally {
      form.removeAttribute("aria-busy");
      controls.forEach(([control, disabled]) => { control.disabled = disabled; });
      updateBlockSelection();
    }
  });
  for (const type of ["input", "change"]) form.addEventListener(type, event => {
    if (!event.target.closest("#source-excerpts, .excerpt-menu-name")) dirty = true;
  });
  window.addEventListener("beforeunload", event => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
})();
