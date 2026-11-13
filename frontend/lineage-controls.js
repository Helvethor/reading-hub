export function mountLineageControls(root) {
  root.addEventListener("change", event => {
    const control = event.target;
    if (control.matches?.(".lineage-controls select")) control.form.requestSubmit();
  });
}

export function replaceLineageContent(target, content) {
  const active = target.ownerDocument.activeElement;
  const name = target.contains(active) && active.matches(".lineage-controls select")
    ? active.name : "";
  target.replaceChildren(content);
  if (name) {
    [...target.querySelectorAll(".lineage-controls select")]
      .find(control => control.name === name)?.focus({preventScroll: true});
  }
}
