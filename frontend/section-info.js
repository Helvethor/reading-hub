export function sectionHeadings(section, from = 0) {
  const headings = [];
  section.descendants((node, offset) => {
    if (node.type.name === "section") return false;
    if (/^h[2-6]$/.test(node.type.name)) headings.push({node, from: from + 1 + offset});
  });
  return headings;
}

export function sectionHeading(section, from = 0) {
  const headings = sectionHeadings(section, from);
  const target = section.attrs["data-section-title"];
  return (target && headings.find(item => item.node.attrs.id === target)) || headings[0];
}

// Mirrors heading_label() in library/services/book_views.py: navigation and ToC
// labels omit note references such as "[8]" while the heading keeps them.
const bracketedNote = /^\[\s*(?:\d{1,4}|[a-z]|[*\u2020\u2021\u00a7\u00b6]{1,3})\s*\]$/i;
const bareNote = /^(?:\d{1,4}|[*\u2020\u2021\u00a7\u00b6]{1,3})$/;

function isNoteText(node) {
  const text = node.text.trim();
  const superscript = node.marks.some(mark => mark.attrs.tag === "sup" ||
    (mark.attrs.class || "").split(/\s+/).includes("text-superscript-on"));
  const internal = node.marks.some(mark => mark.attrs.tag === "a" && (mark.attrs.href || "").startsWith("#"));
  if (bracketedNote.test(text)) return superscript || internal;
  return bareNote.test(text) && superscript && internal;
}

export function headingLabel(heading) {
  let label = "", removed = false;
  heading.descendants(node => {
    if (!node.isText) return;
    if (isNoteText(node)) removed = true;
    else label += node.text;
  });
  return removed ? label.split(/\s+/).filter(Boolean).join(" ") : heading.textContent;
}
