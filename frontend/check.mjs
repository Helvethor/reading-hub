import {JSDOM} from "jsdom";
import {createBoundedEditor} from "./editor.js";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {url: "http://localhost/"});
for (const name of ["window", "document", "navigator", "Node", "HTMLElement",
  "MutationObserver", "DOMParser", "getComputedStyle"]) {
  Object.defineProperty(globalThis, name, {value: dom.window[name], configurable: true});
}
globalThis.requestAnimationFrame = callback => setTimeout(callback, 0);
globalThis.cancelAnimationFrame = clearTimeout;
let raw = "";
for await (const chunk of process.stdin) {
  raw += chunk;
  if (Buffer.byteLength(raw) > 8 * 1024 * 1024) throw new Error("Input exceeds 8 MiB.");
}
const input = JSON.parse(raw);
if (!Array.isArray(input.results) || !input.results.length || input.results.length > 50) {
  throw new Error("Provide semantic_document_check JSON with 1-50 document results.");
}
const results = input.results.map(item => {
  const target = document.createElement("div");
  document.body.append(target);
  let editor;
  try {
    if (!item.document || typeof item.document.html !== "string") {
      throw new Error("Document absent: use --preview-conversion --include-document.");
    }
    editor = createBoundedEditor(target, item.document.html);
    return {rendition: item.rendition, compatible: true};
  } catch (failure) {
    return {rendition: item.rendition, compatible: false, error: failure.message};
  } finally {
    editor?.destroy();
    target.remove();
  }
});
console.log(JSON.stringify({semantics: "editor_fidelity_not_review_certification", results}, null, 2));
if (results.some(item => !item.compatible)) process.exitCode = 1;
