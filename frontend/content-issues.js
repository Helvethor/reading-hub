import {revealDocumentPosition} from "./workspace.js";

function cleanText(value) {
  return value.replace(/\s+/g, " ").trim();
}

function missingTarget(value, ids) {
  const target = value.slice(1).replace(/(?:%[0-9a-f]{2})+/gi, bytes => {
    const encoded = bytes.match(/%[0-9a-f]{2}/gi).map(value => parseInt(value.slice(1), 16));
    return new TextDecoder().decode(new Uint8Array(encoded));
  });
  return !ids.has(target);
}

export function contentIssueDetails(html) {
  const template = document.createElement("template");
  template.innerHTML = html;
  const root = template.content;
  const issues = [];
  const occurrences = new Map();
  const sections = [...root.querySelectorAll("section")];
  const sectionById = id => sections.find(section => section.id === id) || null;

  function add(code, message, node, target = "", locator = {kind: "document"}) {
    const key = `${code}\u0000${target}`;
    const occurrence = (occurrences.get(key) || 0) + 1;
    occurrences.set(key, occurrence);
    const section = node?.localName === "section" ? node : node?.closest("section");
    const heading = section?.querySelector("h2, h3, h4, h5, h6");
    const context = node ? cleanText(node.textContent || "").slice(0, 240) : "";
    issues.push({
      code, message, target, context,
      section: section?.dataset.sectionLabel || cleanText(heading?.textContent || "")
        || section?.id || "",
      occurrence,
      locator: {...locator, occurrence},
    });
  }

  for (const section of root.querySelectorAll("section[data-excerpt-parent], section[data-excerpt-url]")) {
    const parentId = section.getAttribute("data-excerpt-parent");
    let parent = parentId ? sectionById(parentId) : null;
    if (!parent || parent === section) {
      const target = parentId || "(none)";
      add(
        "missing-excerpt-origin",
        `Excerpt origin must identify another section: ${target}`,
        section,
        target,
        {kind: "section", sectionIndex: sections.indexOf(section)},
      );
    }
    const visited = new Set([section]);
    while (parent) {
      if (visited.has(parent)) {
        add(
          "cyclic-excerpt-origin",
          "Excerpt origin linkage must not contain a cycle.",
          section,
          parentId || "",
          {kind: "section", sectionIndex: sections.indexOf(section)},
        );
        break;
      }
      visited.add(parent);
      parent = sectionById(parent.getAttribute("data-excerpt-parent"));
    }
  }

  const ids = new Set([...root.querySelectorAll("[id]")].map(node => node.id));
  for (const section of root.querySelectorAll("section[data-section-title]")) {
    const target = section.getAttribute("data-section-title");
    const heading = [...root.querySelectorAll("[id]")].find(node => node.id === target);
    if (
      !heading || !/^h[2-6]$/.test(heading.localName)
      || heading.closest("section") !== section
    ) {
      add(
        "missing-section-title",
        `Section title must identify a heading owned by that section: ${target}`,
        section,
        target,
        {kind: "section", sectionIndex: sections.indexOf(section)},
      );
    }
  }
  for (const anchor of root.querySelectorAll("a[href^='#']")) {
    const href = anchor.getAttribute("href");
    if (missingTarget(href, ids)) {
      add(
        "unresolved-internal-link",
        `Unresolved internal target: ${href}`,
        anchor,
        href,
        {kind: "anchor", href},
      );
    }
  }
  for (const [placeholderIndex, placeholder] of
    [...root.querySelectorAll(".missing-image")].entries()) {
    add(
      "unavailable-image",
      "The document contains an unavailable-image placeholder.",
      placeholder,
      placeholder.getAttribute("data-source") || "",
      {kind: "missing-image", placeholderIndex},
    );
  }
  if (!cleanText(root.textContent || "") && !root.querySelector("img, hr")) {
    add("no-readable-content", "The document has no readable content.", null);
  }
  return issues;
}

function issueNode(surface, issue) {
  const {kind, occurrence = 1} = issue.locator;
  if (kind === "anchor") {
    return [...surface.querySelectorAll("a[href]")].filter(
      anchor => anchor.getAttribute("href") === issue.locator.href,
    )[occurrence - 1] || null;
  }
  if (kind === "section") {
    return surface.querySelectorAll("section")[issue.locator.sectionIndex] || null;
  }
  if (kind === "missing-image") {
    return surface.querySelectorAll(".missing-image")[issue.locator.placeholderIndex] || null;
  }
  return surface;
}

export function navigateToContentIssue(editor, issue) {
  const target = issueNode(editor.view.dom, issue);
  if (!target?.isConnected) throw new Error("This issue location is no longer available. Recheck issues.");
  let position;
  try {
    position = editor.view.posAtDOM(target, 0);
  } catch {
    throw new Error("This issue location is stale. Recheck issues before navigating.");
  }
  if (!Number.isInteger(position) || position < 0 || position > editor.state.doc.content.size) {
    throw new Error("This issue location is stale. Recheck issues before navigating.");
  }
  revealDocumentPosition(editor, position);
  const currentTarget = issueNode(editor.view.dom, issue);
  if (!currentTarget?.isConnected) {
    throw new Error("This issue location could not be resolved. Recheck issues.");
  }
  currentTarget.dataset.issueHighlight = "true";
  editor.view.focus();
  currentTarget.scrollIntoView?.({block: "center", inline: "nearest"});
  setTimeout(() => {
    if (currentTarget.isConnected) delete currentTarget.dataset.issueHighlight;
  }, 1800);
}

export function renderContentIssues(list, status, issues, onLocate) {
  list.replaceChildren();
  if (!issues.length) {
    status.textContent = "No content issues found.";
    return;
  }
  for (const [index, issue] of issues.entries()) {
    const item = document.createElement("li");
    const message = document.createElement("p");
    message.textContent = issue.message;
    item.append(message);
    if (issue.target) {
      const target = document.createElement("p");
      target.textContent = `Target: ${issue.target}`;
      item.append(target);
    }
    if (issue.section) {
      const section = document.createElement("p");
      section.textContent = `Section: ${issue.section}`;
      item.append(section);
    }
    if (issue.context) {
      const context = document.createElement("p");
      context.textContent = `Context: ${issue.context}`;
      item.append(context);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Go to location";
    button.setAttribute(
      "aria-label",
      `Go to location: ${issue.message}${issue.target ? ` ${issue.target}` : ""}`,
    );
    button.addEventListener("click", () => onLocate(issue, index));
    item.append(button);
    list.append(item);
  }
  status.textContent = `${issues.length} content issue${issues.length === 1 ? "" : "s"} found.`;
}
