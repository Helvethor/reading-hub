(() => {
  "use strict";
  document.querySelectorAll("[data-source-switcher]").forEach(select => {
    select.addEventListener("change", () => select.form.requestSubmit());
  });
})();
