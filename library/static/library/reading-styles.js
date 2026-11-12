function csrfToken(panel) {
  return panel.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";
}

function validLayer(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

export function mountReadingStyles(panel) {
  const owner = panel.ownerDocument;
  const view = owner.defaultView;
  const form = panel.querySelector(".reading-style-settings");
  if (!form) return;

  const status = panel.querySelector(".reading-style-status");
  const error = panel.querySelector(".reading-style-error");
  const scopeSelect = panel.querySelector("[data-style-scope]");
  const typeSelect = panel.querySelector("[data-style-type]");
  const workspace = owner.querySelector("#unified-workspace");
  const accountSettings = panel.hasAttribute("data-account-settings");
  const authenticated = panel.dataset.authenticated === "true";
  const renditionId = panel.dataset.renditionId || "";
  const outputId = panel.dataset.outputId || "";
  const importBox = panel.querySelector(".reading-style-import");
  const importGuestButton = panel.querySelector("[data-import-guest]");
  const clearGuestButton = panel.querySelector("[data-clear-guest]");
  const guestKey = outputId ? `reading-hub:reading-style:v1:${outputId}` : "";
  const downloads = [...owner.querySelectorAll("[data-reading-pdf]")];
  const downloadPaths = downloads.map(link => new URL(link.href, view.location.href).pathname);
  const inputs = [...form.elements].filter(input => input.name);
  const mutations = new Set();
  let generation = 0;
  let controller = null;
  let guestLayer = {};
  let guestStorageError = "";
  let activeScope = panel.dataset.scope || "output";
  let activeType = panel.dataset.workType || "other";
  let activeLayers = {};

  function showError(message) {
    error.textContent = message;
    error.hidden = !message;
  }

  function readGuestLayer() {
    if (!guestKey) return {};
    try {
      const saved = view.localStorage.getItem(guestKey);
      if (!saved) return {};
      const parsed = JSON.parse(saved);
      if (!validLayer(parsed)) throw new Error("Stored preferences are not an object.");
      return parsed;
    } catch (failure) {
      guestStorageError = `Could not read this version’s guest settings (${failure.message}). ` +
        "Clear them to continue. Clearing browser storage also removes guest preferences.";
      showError(guestStorageError);
      return {};
    }
  }

  function writeGuestLayer(layer) {
    if (!guestKey) return false;
    try {
      if (Object.keys(layer).length) view.localStorage.setItem(guestKey, JSON.stringify(layer));
      else view.localStorage.removeItem(guestKey);
      guestStorageError = "";
      return true;
    } catch (failure) {
      guestStorageError = `Applied in this tab, but browser storage failed (${failure.message}). ` +
        "This guest choice may be lost when you leave or reload.";
      showError(guestStorageError);
      return false;
    }
  }

  function setInputs(settings) {
    for (const [key, value] of Object.entries(settings || {})) {
      const input = form.elements.namedItem(key);
      if (!input) continue;
      if (input.type === "checkbox") input.checked = value;
      else input.value = value;
    }
  }

  function setOriginLabels(origins = {}, layers = activeLayers) {
    const active = layers?.[activeScope] || {};
    for (const node of panel.querySelectorAll("[data-style-origin-for]")) {
      const key = node.dataset.styleOriginFor;
      node.textContent = origins[key]?.label || "Built-in";
    }
    for (const button of panel.querySelectorAll("[data-reset-setting]")) {
      button.disabled = !Object.hasOwn(active, button.dataset.resetSetting);
    }
  }

  function syncPresentation(data) {
    setInputs(data.settings);
    activeType = data.work_type || activeType;
    activeLayers = data.layers || activeLayers;
    panel.dataset.workType = activeType;
    panel.dataset.outputId = data.output_id || outputId;
    if (typeSelect) typeSelect.value = activeType;
    const typeLabel = panel.querySelector("[data-style-type-label]");
    if (typeLabel) typeLabel.textContent = `Work type: ${activeType[0].toUpperCase()}${activeType.slice(1)}`;
    setOriginLabels(data.origins, activeLayers);
    if (data.presentation && workspace) {
      workspace.dataset.readingPresentation = data.presentation;
      workspace.dataset.readingStyleUrl = data.stylesheet;
      workspace.dataset.readingStyleType = activeType;
      workspace.dataset.readingStyleGuest = JSON.stringify(guestLayer);
    }
    for (const [index, link] of downloads.entries()) {
      const url = new URL(downloadPaths[index], view.location.href);
      url.searchParams.set("presentation", data.presentation);
      link.href = `${url.pathname}${url.search}`;
    }
  }

  function prepareSheet(url, signal) {
    return new Promise((resolve, reject) => {
      const link = owner.createElement("link");
      link.rel = "stylesheet";
      link.media = "not all";
      link.href = url;
      link.dataset.readingStyle = "";
      const fail = () => {
        link.remove();
        reject(new Error(signal.aborted
          ? "Style update cancelled or timed out."
          : "The style sheet could not load. The previous style is still displayed."));
      };
      signal.addEventListener("abort", fail, {once: true});
      link.onerror = fail;
      link.onload = () => {
        signal.removeEventListener("abort", fail);
        resolve(link);
      };
      owner.head.append(link);
    });
  }

  async function responseData(response) {
    const data = response.headers.get("content-type")?.includes("application/json")
      ? await response.json() : null;
    if (!response.ok) {
      throw new Error(data?.error || `Reading style request failed (${response.status}).`);
    }
    if (!data) throw new Error("The server returned an invalid reading style response.");
    return data;
  }

  async function requestStyle({
    scope = activeScope, workType = activeType, changes = {}, reset = [],
  } = {}) {
    const current = ++generation;
    controller?.abort();
    controller = new view.AbortController();
    const signal = controller.signal;
    const activeController = controller;
    const timeout = view.setTimeout(() => activeController.abort(), 15000);
    status.textContent = "Applying reading style…";
    showError("");
    let sheet;
    try {
      const payload = {
        scope, work_type: workType, changes, reset,
        ...(renditionId ? {rendition_id: Number(renditionId)} : {}),
        ...(!authenticated && scope === "output" ? {guest_overrides: guestLayer} : {}),
      };
      const response = await view.fetch(panel.dataset.previewUrl, {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": csrfToken(panel),
        },
        body: JSON.stringify(payload),
        signal,
      });
      const data = await responseData(response);
      if (current !== generation) return null;
      if (!accountSettings) sheet = await prepareSheet(data.stylesheet, signal);
      if (current !== generation) { sheet?.remove(); return null; }
      if (signal.aborted) throw new Error("Style update timed out.");
      if (!authenticated && scope === "output") {
        guestLayer = data.layer || {};
        writeGuestLayer(guestLayer);
      }
      const old = owner.querySelector("link[data-reading-style]");
      if (!accountSettings) {
        old?.remove();
        sheet.media = "all";
        if (workspace && workspace.dataset.activeTab === "read") {
          sheet.dataset.workspaceReadingStyle = "";
        }
      }
      activeScope = scope;
      if (scopeSelect) scopeSelect.value = scope;
      syncPresentation(data);
      panel.dataset.scope = scope;
      importBox?.removeAttribute("hidden");
      if (importBox && (!authenticated || !Object.keys(guestLayer).length)) {
        importBox.hidden = true;
      }
      status.textContent = guestStorageError || (
        accountSettings || scope === "account"
          ? "My defaults are saved privately to your account."
          : authenticated
            ? "This version’s style is saved privately to your account."
            : "This version’s style is saved in this browser only."
      );
      if (guestStorageError) showError(guestStorageError);
      return data;
    } catch (failure) {
      sheet?.remove();
      if (current !== generation) return null;
      showError(failure.message);
      status.textContent = "Style not applied; the previous displayed style remains.";
      return null;
    } finally {
      view.clearTimeout(timeout);
    }
  }

  function settingValue(input) {
    return input.type === "checkbox" ? input.checked : input.value;
  }

  function currentType() {
    return typeSelect?.value || activeType;
  }

  function setFontMode(input) {
    if (["body_font", "title_font", "metadata_font", "contents_font", "code_font"].includes(input.name)) {
      form.elements.font_mode.value = "mixed";
      return {font_mode: "mixed", [input.name]: settingValue(input)};
    }
    return {[input.name]: settingValue(input)};
  }

  for (const input of inputs) {
    input.addEventListener("change", () => {
      if (!input.name) return;
      requestStyle({workType: currentType(), changes: setFontMode(input)});
    });
  }

  for (const button of panel.querySelectorAll("[data-reset-setting]")) {
    button.addEventListener("click", () => requestStyle({
      workType: currentType(), reset: [button.dataset.resetSetting],
    }));
  }

  scopeSelect?.addEventListener("change", () => {
    activeScope = scopeSelect.value;
    requestStyle({scope: activeScope, workType: currentType()});
  });

  typeSelect?.addEventListener("change", () => {
    const url = new URL(view.location.href);
    url.searchParams.set("style_type", typeSelect.value);
    view.history.replaceState(view.history.state, "", url);
    requestStyle({scope: "account", workType: typeSelect.value});
  });

  form.addEventListener("submit", event => event.preventDefault());

  clearGuestButton?.addEventListener("click", async () => {
    try {
      view.localStorage.removeItem(guestKey);
      guestLayer = {};
      guestStorageError = "";
      await requestStyle({scope: "output", workType: currentType()});
      status.textContent = "Guest style cleared for this exact version; inherited settings are restored.";
      showError("");
    } catch (failure) {
      showError(`Could not clear browser storage (${failure.message}).`);
    }
  });

  importGuestButton?.addEventListener("click", async () => {
    try {
      if (!Object.keys(guestLayer).length) throw new Error("There are no guest settings to import.");
      const response = await view.fetch(panel.dataset.importGuestUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": csrfToken(panel),
        },
        body: JSON.stringify({rendition_id: Number(renditionId), settings: guestLayer}),
      });
      const data = await responseData(response);
      await requestStyle({scope: "output", workType: data.work_type});
      try { view.localStorage.removeItem(guestKey); } catch (failure) {
        throw new Error(`Imported successfully, but guest storage could not be cleared (${failure.message}).`);
      }
      guestLayer = {};
      importBox.hidden = true;
      status.textContent = data.message;
      showError("");
    } catch (failure) {
      showError(failure.message);
    }
  });

  const importProfileButton = panel.querySelector("[data-import-profile-url]");
  importProfileButton?.addEventListener("click", async () => {
    const profileId = panel.querySelector("[data-legacy-profile]")?.value;
    if (!profileId) {
      showError("Choose a legacy profile to import.");
      return;
    }
    try {
      const response = await view.fetch(importProfileButton.dataset.importProfileUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": csrfToken(panel),
        },
        body: JSON.stringify({profile_id: profileId, work_type: currentType()}),
      });
      const data = await responseData(response);
      await requestStyle({scope: "account", workType: data.work_type});
      status.textContent = data.message;
      showError("");
    } catch (failure) {
      showError(failure.message);
    }
  });

  workspace?.addEventListener("reading-style-snapshot", event => {
    const appearance = event.detail;
    if (!appearance) return;
    activeType = appearance.work_type;
    if (typeSelect) typeSelect.value = activeType;
    setInputs(appearance.settings);
    activeLayers = {...(appearance.layers || activeLayers)};
    if (!authenticated && activeScope === "output") {
      activeLayers.output = {...(activeLayers.output || {}), ...guestLayer};
    }
    panel.dataset.workType = activeType;
    setOriginLabels(appearance.origins, activeLayers);
  });

  if (guestKey) guestLayer = readGuestLayer();
  if (importBox) {
    importBox.hidden = !authenticated || !Object.keys(guestLayer).length;
  }
  requestStyle({
    scope: activeScope,
    workType: currentType(),
    changes: {},
  });
}

if (typeof document !== "undefined") {
  for (const panel of document.querySelectorAll(".reading-style-controls")) {
    mountReadingStyles(panel);
  }
}
