export function mountSelectionToolMenu(menu, trigger, close) {
  if (!menu || !trigger) return null;
  const categories = [...menu.querySelectorAll("[data-menu-category]")];
  const categoryList = menu.querySelector("[data-menu-category-list]");
  const submenus = categories.map(category =>
    menu.querySelector(`#${category.getAttribute("aria-controls")}`));
  if (!categoryList || categories.length === 0 ||
      submenus.some(submenu => !submenu)) return null;

  let activeIndex = -1;
  const owner = menu.ownerDocument;
  const visibleButtons = container => [...container.querySelectorAll("button:not([hidden]):not(:disabled)")]
    .filter(button => !button.closest("[hidden]"));

  function reset() {
    activeIndex = -1;
    categoryList.hidden = false;
    delete menu.dataset.submenuSide;
    menu.style.removeProperty("margin-top");
    for (const [index, category] of categories.entries()) {
      category.setAttribute("aria-expanded", "false");
      submenus[index].hidden = true;
    }
  }

  function placeSubmenu(category, submenu) {
    const inset = 8;
    const {clientWidth, clientHeight} = owner.documentElement;
    const root = menu.getBoundingClientRect();
    const anchor = category.getBoundingClientRect();
    const {width, height} = submenu.getBoundingClientRect();
    const rightEdge = root.right - 1, leftEdge = root.left - width + 1;
    const fitsRight = rightEdge + width <= clientWidth - inset;
    if (!width || (!fitsRight && leftEdge < inset)) {
      delete menu.dataset.submenuSide;
      categoryList.hidden = true;
      const backButton = submenu.querySelector("[data-menu-back]");
      if (backButton) backButton.hidden = false;
      const {bottom} = menu.getBoundingClientRect();
      menu.style.marginTop = `${Math.min(0, clientHeight - inset - bottom)}px`;
      return;
    }
    menu.dataset.submenuSide = fitsRight ? "right" : "left";
    submenu.style.left = `${fitsRight ? rightEdge : leftEdge}px`;
    submenu.style.top = `${Math.max(inset, Math.min(anchor.top, clientHeight - height - inset))}px`;
  }

  function open(index, focus = true) {
    if (categories[index].hidden) return;
    const category = categories[index], submenu = submenus[index];
    if (index !== activeIndex) {
      const restoreFocus = activeIndex >= 0 && submenus[activeIndex].contains(owner.activeElement);
      reset();
      activeIndex = index;
      category.setAttribute("aria-expanded", "true");
      submenu.hidden = false;
      menu.dataset.submenuSide = "right";
      const backButton = submenu.querySelector("[data-menu-back]");
      if (backButton) backButton.hidden = true;
      placeSubmenu(category, submenu);
      if (!focus && restoreFocus && !categoryList.hidden) category.focus({preventScroll: true});
      if (categoryList.hidden && (restoreFocus || categoryList.contains(owner.activeElement))) focus = true;
    }
    if (focus) visibleButtons(submenu)[0]?.focus({preventScroll: true});
  }

  function back() {
    const category = categories[activeIndex];
    if (activeIndex < 0) return false;
    reset();
    category.focus({preventScroll: true});
    return true;
  }

  function moveFocus(items, event) {
    const current = items.indexOf(owner.activeElement);
    if (!items.length) return;
    const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 :
      (current + (["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1) + items.length) % items.length;
    event.preventDefault();
    items[next].focus();
  }

  function mount() {
    menu.addEventListener("pointerover", event => {
      if (event.pointerType !== "mouse") return;
      const category = event.target.closest("[data-menu-category]");
      const index = categories.indexOf(category);
      if (index >= 0 && !category.contains(event.relatedTarget)) open(index, false);
    });
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
      const submenu = submenus[activeIndex];
      const inSubmenu = submenu?.contains(target);
      if (event.key === "Escape") {
        event.preventDefault();
        if (inSubmenu) back();
        else close();
        return;
      }
      if (event.key === "ArrowLeft" && inSubmenu) {
        event.preventDefault();
        back();
        return;
      }
      if (event.key === "Tab") {
        close();
        return;
      }
      if (event.key === "ArrowRight" && !inSubmenu) {
        const index = categories.indexOf(target);
        if (index >= 0) {
          event.preventDefault();
          open(index);
          return;
        }
      }
      if (["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
        moveFocus(inSubmenu ? visibleButtons(submenu) :
          visibleButtons(menu).filter(button => !submenu?.contains(button)), event);
      }
    });
    menu.addEventListener("scroll", () => {
      if (menu.dataset.submenuSide) placeSubmenu(categories[activeIndex], submenus[activeIndex]);
    });
    reset();
  }

  return {mount, reset, open};
}
