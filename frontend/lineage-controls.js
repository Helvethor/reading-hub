export function mountLineageControls(root) {
  (root.nodeType === 9 ? root.documentElement : root)
    .classList.add("has-lineage-controls");
  root.addEventListener("change", event => {
    const control = event.target;
    if (control.matches?.(".lineage-controls select, .lineage-compare-form select")) {
      control.form.requestSubmit();
    }
  });
}

export function replaceLineageContent(target, content) {
  const active = target.ownerDocument.activeElement;
  const name = target.contains(active)
      && active.matches(".lineage-controls select, .lineage-compare-form select")
    ? active.name : "";
  const lineageId = target.contains(active)
      && active.matches(".lineage-timeline-item > a")
    ? active.closest(".lineage-timeline-item").dataset.lineageId : "";
  target.replaceChildren(content);
  if (name) {
    [...target.querySelectorAll(".lineage-controls select, .lineage-compare-form select")]
      .find(control => control.name === name)?.focus({preventScroll: true});
  } else if (lineageId) {
    [...target.querySelectorAll(".lineage-timeline-item")]
      .find(item => item.dataset.lineageId === lineageId)
      ?.querySelector("a[href]")?.focus({preventScroll: true});
  }
}
