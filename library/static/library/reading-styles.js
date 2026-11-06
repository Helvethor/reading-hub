export function mountReadingStyles(panel) {
  const owner = panel.ownerDocument, view = owner.defaultView;
  const form = panel.querySelector(".reading-style-settings");
  const profile = form.elements.style_profile;
  const save = panel.querySelector(".reading-style-save");
  const status = panel.querySelector(".reading-style-status");
  const error = panel.querySelector(".reading-style-error");
  const downloads = [...owner.querySelectorAll("[data-reading-pdf]")];
  const mutations = new Set();
  let generation = 0, controller = null, timer = null, pending = false;
  const pdfPaths = downloads.map(link => new URL(link.href).pathname);
  const settingNames = [...form.elements].map(input => input.name).filter(name =>
    name && !["style_profile", "style_action", "draft", "revision"].includes(name));
  panel.classList.add("reading-style-live");

  function showError(message) {
    error.textContent = message;
    error.hidden = !message;
  }
  function syncControls() {
    if (save) {
      save.querySelector("[value=update]").disabled =
        pending || mutations.has(save) || !save.elements.profile_id.value;
      save.querySelector("[value=create]").disabled = pending || mutations.has(save);
    }
    for (const link of downloads) {
      link.setAttribute("aria-disabled", String(pending));
      if (pending) link.removeAttribute("href");
    }
  }
  downloads.forEach(link => link.addEventListener("click", event => {
    if (pending) event.preventDefault();
  }));
  async function responseData(response) {
    const json = response.headers.get("content-type")?.includes("application/json");
    const data = json ? await response.json() : null;
    if (!response.ok) {
      const message = data?.error || (json ? "" : await response.text());
      throw new Error(message && !message.trim().startsWith("<")
        ? message : `Request failed (${response.status}). Reload and retry.`);
    }
    if (!data) throw new Error("The server returned an invalid style response.");
    return data;
  }
  function prepareSheet(url, signal) {
    return new Promise((resolve, reject) => {
      const link = owner.createElement("link");
      link.rel = "stylesheet";
      link.media = "not all";
      link.href = url;
      const fail = () => {
        link.remove();
        reject(new Error(signal.aborted ? "Style update cancelled or timed out." :
          "The style sheet could not load. The previous style is still displayed."));
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
  async function apply(loadProfile = false) {
    const current = ++generation;
    controller?.abort();
    controller = new view.AbortController();
    const signal = controller.signal;
    const activeController = controller;
    const timeout = view.setTimeout(() => activeController.abort(), 15000);
    pending = true;
    const oldLinks = downloads.map(link => link.href || link.dataset.appliedHref);
    downloads.forEach((link, index) => { if (oldLinks[index]) link.dataset.appliedHref = oldLinks[index]; });
    syncControls();
    showError("");
    status.textContent = "Updating displayed style and PDF…";
    let sheet;
    try {
      if (!loadProfile && !form.reportValidity()) throw new Error("Check the highlighted settings.");
      const params = loadProfile ? new URLSearchParams({
        style_profile: profile.value, style_action: "load",
      }) : new URLSearchParams(new view.FormData(form));
      if (!loadProfile) params.set("style_action", "apply");
      const data = await responseData(await view.fetch(`${panel.dataset.previewUrl}?${params}`, {
        signal, headers: {Accept: "application/json"},
      }));
      if (current !== generation) return;
      sheet = await prepareSheet(data.stylesheet, signal);
      if (current !== generation) { sheet.remove(); return; }
      if (signal.aborted) throw new Error("Style update timed out.");
      const url = new URL(view.location.href);
      for (const name of [...settingNames, "style_action"]) url.searchParams.delete(name);
      url.searchParams.set("style", data.token);
      if (loadProfile && profile.value) url.searchParams.set("style_profile", profile.value);
      else url.searchParams.delete("style_profile");
      view.history.replaceState(null, "", url);
      if (loadProfile) {
        for (const [key, value] of Object.entries(data.settings)) {
          const input = form.elements[key];
          if (input.type === "checkbox") input.checked = value;
          else input.value = value;
        }
      }
      owner.querySelector("[data-reading-style]")?.remove();
      sheet.media = "all";
      sheet.dataset.readingStyle = "";
      for (const input of panel.querySelectorAll('input[name="style"]')) input.value = data.token;
      downloads.forEach((link, index) => {
        link.href = `${pdfPaths[index]}?style=${encodeURIComponent(data.token)}`;
        link.dataset.appliedHref = link.href;
      });
      if (loadProfile && save) {
        save.elements.profile_id.value = profile.value === "marxist" ? "" : profile.value;
      }
      if (!loadProfile) profile.value = "";
      status.textContent = "Displayed style and PDF are in sync. Profile changes are saved only with Update or Save as new.";
    } catch (failure) {
      sheet?.remove();
      if (current !== generation) return;
      showError(`${failure.message} The previous displayed style and PDF are unchanged.`);
      status.textContent = "Style not applied.";
    } finally {
      view.clearTimeout(timeout);
      if (current === generation) {
        pending = false;
        downloads.forEach(link => { if (link.dataset.appliedHref) link.href = link.dataset.appliedHref; });
        syncControls();
      }
    }
  }
  function schedule() {
    view.clearTimeout(timer);
    // Cancel an older in-flight response as soon as the controls change.
    generation++;
    controller?.abort();
    timer = view.setTimeout(() => apply(false), 120);
  }
  function chooseFont(input) {
    if (["body_font", "title_font", "metadata_font", "contents_font", "code_font"].includes(input.name)) {
      form.elements.font_mode.value = "mixed";
    }
  }
  form.addEventListener("input", event => {
    if (event.target !== profile) {
      chooseFont(event.target);
      schedule();
    }
  });
  form.addEventListener("change", event => {
    view.clearTimeout(timer);
    if (event.target === profile) {
      apply(Boolean(profile.value));
    } else {
      chooseFont(event.target);
      apply(false);
    }
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    view.clearTimeout(timer);
    apply(event.submitter?.value === "load");
  });
  save?.elements.profile_id.addEventListener("change", syncControls);
  for (const mutation of panel.querySelectorAll(".reading-style-save,.reading-style-default")) {
    mutation.addEventListener("submit", async event => {
      event.preventDefault();
      if (pending || mutations.has(mutation)) return;
      mutations.add(mutation);
      const data = new view.FormData(mutation);
      if (event.submitter?.name) data.set(event.submitter.name, event.submitter.value);
      const buttons = [...mutation.querySelectorAll("button")];
      buttons.forEach(button => { button.disabled = true; });
      showError("");
      try {
        const result = await responseData(await view.fetch(mutation.action, {
          method: "POST", body: data, headers: {Accept: "application/json"},
        }));
        if (result.id) {
          for (const select of panel.querySelectorAll(
            'select[name="style_profile"],select[name="profile_id"]',
          )) {
            let option = [...select.options].find(item => item.value === String(result.id));
            if (!option) { option = new view.Option(result.name, result.id); select.add(option); }
            option.textContent = result.name;
          }
          save.elements.profile_id.value = result.id;
          save.elements.profile_name.value = "";
          const current = save.elements.style.value === data.get("style");
          profile.value = current ? result.id : "";
          if (current) {
            const url = new URL(view.location.href);
            url.searchParams.set("style_profile", result.id);
            view.history.replaceState(null, "", url);
          }
          status.textContent = `Saved profile “${result.name}”. ` + (current ?
            "Reuse it from the Profile list." : "The display has newer unsaved style changes.");
        } else status.textContent = "Default profile updated for other publications.";
        panel.dataset.default = result.default;
        panel.querySelector(".reading-style-default select").value = result.default;
      } catch (failure) { showError(failure.message); }
      finally {
        mutations.delete(mutation);
        buttons.forEach(button => { button.disabled = false; });
        syncControls();
      }
    });
  }
  status.textContent = "Live preview. PDF follows the displayed settings.";
  syncControls();
}

if (typeof document !== "undefined") {
  for (const panel of document.querySelectorAll(".reading-style-controls")) mountReadingStyles(panel);
}
