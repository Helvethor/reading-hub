export async function applyTheme(doc, theme) {
  const current = doc.querySelector("link[data-site-theme]");
  if (!current) return;
  const sheets = [[current, theme.stylesheet]];
  const reading = doc.querySelector("link[data-reading-style]");
  if (reading) {
    const url = new URL(reading.href);
    url.searchParams.set("theme_refresh", Date.now());
    sheets.push([reading, url.href]);
  }
  const staged = sheets.map(([old, href]) => {
    const replacement = old.cloneNode();
    replacement.href = href;
    replacement.media = "not all";
    return {old, replacement};
  });
  let timeout;
  try {
    const loading = Promise.all(staged.map(({old, replacement}) => new Promise((resolve, reject) => {
      replacement.addEventListener("load", resolve, {once: true});
      replacement.addEventListener("error", () => {
        reject(new Error("Theme saved, but its stylesheet could not load. Retry or reload."));
      }, {once: true});
      old.after(replacement);
    })));
    await Promise.race([loading, new Promise((resolve, reject) => {
      timeout = doc.defaultView.setTimeout(() => {
        reject(new Error("Theme stylesheet loading timed out. Retry or reload."));
      }, 15000);
    })]);
  } catch (error) {
    staged.forEach(({replacement}) => replacement.remove());
    throw error;
  } finally {
    doc.defaultView.clearTimeout(timeout);
  }
  staged.forEach(({old, replacement}) => {
    if (!old.isConnected) {
      replacement.remove();
      return;
    }
    replacement.media = "all";
    old.remove();
  });
  for (const select of doc.querySelectorAll(
    "[data-theme-form] select, [data-user-settings] select[name=theme]",
  )) select.value = theme.theme;
  for (const frame of doc.querySelectorAll("iframe")) {
    frame.contentWindow?.postMessage({type: "reading-hub-theme", theme}, doc.location.origin);
  }
}

export function mountThemes(doc) {
  const view = doc.defaultView;
  const showError = error => {
    let target = doc.querySelector("[data-theme-error]");
    if (!target) {
      target = doc.createElement("p");
      target.setAttribute("role", "alert");
      doc.querySelector("main").prepend(target);
    }
    target.hidden = false;
    target.textContent = error.message;
  };
  view.addEventListener("message", event => {
    if (event.origin !== view.location.origin || event.source !== view.parent ||
        event.data?.type !== "reading-hub-theme") return;
    applyTheme(doc, event.data.theme).catch(showError);
  });
  for (const form of doc.querySelectorAll("[data-theme-form]")) {
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const controls = [...form.querySelectorAll("button, select")];
      const body = new view.FormData(form);
      const error = form.querySelector("[data-theme-error]");
      error.hidden = true;
      controls.forEach(control => { control.disabled = true; });
      const controller = new view.AbortController();
      const timeout = view.setTimeout(() => controller.abort(), 15000);
      try {
        const response = await view.fetch(form.action, {
          method: "POST", body, signal: controller.signal, headers: {Accept: "application/json"},
        });
        if (!response.headers.get("content-type")?.includes("application/json")) {
          throw new Error("Theme change failed. Reload and retry.");
        }
        const result = await response.json();
        if (!response.ok) throw new Error(result.error);
        await applyTheme(doc, result);
      } catch (failure) {
        showError(failure);
      } finally {
        view.clearTimeout(timeout);
        controls.forEach(control => { control.disabled = false; });
      }
    });
  }
}

if (typeof document !== "undefined") mountThemes(document);
