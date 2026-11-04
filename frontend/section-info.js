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
  return headings.find(item => item.node.attrs.id === section.attrs["data-section-title"]) || headings[0];
}
