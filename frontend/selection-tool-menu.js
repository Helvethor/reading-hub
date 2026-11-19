export function mountSelectionToolMenu(menu, trigger, close) {
  if (!menu || !trigger) return null;
  const categories = [...menu.querySelectorAll("[data-menu-category]")];
  const categoryList = menu.querySelector("[data-menu-category-list]");
  const submenus = categories.map(category =>
    menu.querySelector(`#${category.getAttribute("aria-controls")}`));
  if (!categoryList || categories.length === 0 ||
      submenus.some(submenu => !submenu)) return null;

  let activeIndex = -1;
  const visibleButtons = container => [...container.querySelectorAll("button:not([hidden]):not(:disabled)")]
    .filter(button => !button.closest("[hidden]"));

  function reset() {
    activeIndex = -1;
    categoryList.hidden = false;
    for (const [index, category] of categories.entries()) {
      category.setAttribute("aria-expanded", "false");
      submenus[index].hidden = true;
    }
  }

  function open(index, focus = true) {
    if (categories[index].hidden) return;
    reset();
    activeIndex = index;
    categoryList.hidden = true;
    categories[index].setAttribute("aria-expanded", "true");
    submenus[index].hidden = false;
    if (focus) visibleButtons(submenus[index])[0]?.focus();
  }

  function back(focus = true) {
    const category = categories[activeIndex];
    if (activeIndex < 0) return false;
    reset();
    if (focus) category.focus();
    return true;
  }

  function moveFocus(container, event) {
    const items = visibleButtons(container);
    const current = items.indexOf(menu.ownerDocument.activeElement);
    if (!items.length) return;
    const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 :
      (current + (["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1) + items.length) % items.length;
    event.preventDefault();
    items[next].focus();
  }

  function mount() {
    menu.addEventListener("click", event => {
      const category = event.target.closest("[data-menu-category]");
      if (category && categories.includes(category)) {
        open(categories.indexOf(category));
        return;
      }
      if (event.target.closest("[data-menu-back]")) back();
    });
    menu.addEventListener("keydown", event => {
      const target = event.target;
      if (event.key === "Escape") {
        if (activeIndex >= 0) {
          event.preventDefault();
          back();
        } else {
          event.preventDefault();
          close();
        }
        return;
      }
      if (event.key === "ArrowLeft" && activeIndex >= 0) {
        event.preventDefault();
        back();
        return;
      }
      if (event.key === "ArrowLeft" && activeIndex < 0) {
        moveFocus(menu, event);
        return;
      }
      if (event.key === "Tab") {
        reset();
        close();
        return;
      }
      if (event.key === "ArrowRight" && activeIndex < 0) {
        const index = categories.indexOf(target);
        if (index >= 0) {
          event.preventDefault();
          open(index);
        } else moveFocus(menu, event);
        return;
      }
      if (event.key === "ArrowRight" && activeIndex >= 0) {
        moveFocus(submenus[activeIndex], event);
        return;
      }
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        moveFocus(activeIndex < 0 ? menu : submenus[activeIndex], event);
      }
    });
    reset();
  }

  return {mount, reset, open};
}
