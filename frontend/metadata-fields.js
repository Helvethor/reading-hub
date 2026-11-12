// Mirrors library/services/document_metadata.py so the editor preview matches publication.
export const textFields = [
  ["original_title", "Original title"], ["publisher", "Publisher"], ["series", "Series"],
  ["publication_note", "Publication history"], ["source_edition", "Source edition"],
  ["translation_note", "Translation"], ["online_version", "Online version"],
  ["transcription", "Transcription/markup"], ["proofreading", "Proofreading"],
  ["rights", "Rights"], ["notes", "Other notes"],
];
export const personKeys = {author: "author", editor: "editor", translator: "translator", unknown: "contributor"};
export const dateFields = {
  written: ["written", "Written"], delivered: ["delivered", "Delivered"],
  publication: ["publication", "Published"], online_edition: ["online_edition", "Online edition"],
  unknown: ["date", "Date (role unconfirmed)"],
};
export const workTypes = [
  ["book", "Book"], ["anthology", "Anthology"], ["pamphlet", "Pamphlet"], ["article", "Article"], ["essay", "Essay"],
  ["letter", "Letter"], ["speech", "Speech"], ["interview", "Interview"],
  ["report", "Report"], ["resolution", "Resolution"], ["other", "Other"],
];
const bookLike = new Set(["book", "anthology", "pamphlet", "report"]);
export const titleLayouts = ["full", "compact"];
export const titlePageFields = [
  "work_type", "original_title", "author", "editor", "translator", "contributor", "publisher", "series",
  "written", "delivered", "publication", "online_edition", "date", "publication_note",
  "source_edition", "translation_note", "online_version", "transcription", "proofreading",
  "rights", "notes", "language", "original_language", "subjects", "source_url",
];
// The title page is synthetic by default; the end-of-book metadata page lists everything.
export const defaultShown = new Set(["author", "translator", "written", "delivered", "publication", "rights",
  "source_url"]);
export const fieldLabels = {
  ...Object.fromEntries(textFields), work_type: "Type", author: "Author", editor: "Editor", translator: "Translator",
  contributor: "Contributor", ...Object.fromEntries(Object.values(dateFields)),
  language: "Language", original_language: "Original language", subjects: "Subjects", source_url: "Source URL",
};

export function titlePageSelection(metadata) {
  return Array.isArray(metadata.title_page_fields)
    ? new Set(metadata.title_page_fields)
    : new Set(defaultShown);
}

// Book-like works open with a full title page and a contents page; shorter works start
// right below a compact title block. Without a work type the book classification decides.
export function pagePreset(workType, book) {
  const full = workType ? bookLike.has(workType) : Boolean(book);
  return {title_layout: full ? "full" : "compact", contents_page: full, metadata_page: true};
}

export function bookPages(metadata, book) {
  const pages = pagePreset(metadata.work_type, book);
  if (titleLayouts.includes(metadata.title_layout)) pages.title_layout = metadata.title_layout;
  for (const key of ["contents_page", "metadata_page"]) {
    if (typeof metadata[key] === "boolean") pages[key] = metadata[key];
  }
  return pages;
}

const textValue = value => value.split("\n").map(line => line.trim()).filter(Boolean).join("; ");

export function metadataEntries(metadata, presentation = {}) {
  const entries = [];
  const type = workTypes.find(([key]) => key === metadata.work_type);
  if (type) entries.push(["work_type", "Type", type[1]]);
  if (metadata.original_title) entries.push(["original_title", "Original title", metadata.original_title]);
  const author = metadata.author || presentation.sourceName;
  if (author) entries.push(["author", !metadata.author || metadata.author_is_fallback ? "Source website" : "Author", author]);
  const roles = {editor: "Editor", translator: "Translator", unknown: "Contributor (role unconfirmed)"};
  for (const person of metadata.contributors || []) {
    if (roles[person.role]) entries.push([personKeys[person.role], roles[person.role], person.name]);
  }
  for (const key of ["publisher", "series"]) {
    if (metadata[key]) entries.push([key, fieldLabels[key], metadata[key]]);
  }
  for (const date of metadata.date_facts || []) {
    const [key, label] = dateFields[date.type] || dateFields.unknown;
    entries.push([key, label, date.value + (date.end_value ? ` / ${date.end_value}` : "")]);
  }
  if (metadata.published && !metadata.date_facts?.some(date => date.type === "publication")) {
    entries.push(["publication", "Published", metadata.published]);
  }
  for (const [key, label] of textFields.slice(3)) {
    if (metadata[key]) entries.push([key, label, textValue(metadata[key])]);
  }
  for (const key of ["language", "original_language"]) {
    if (!metadata[key]) continue;
    const code = metadata[key].toLowerCase().replaceAll("_", "-");
    const language = code === "und" ? "Unknown language" :
      presentation.languages?.[code] || presentation.languages?.[code.split("-")[0]] || code;
    entries.push([key, fieldLabels[key], language]);
  }
  if (metadata.topics?.length) entries.push(["subjects", "Subjects", metadata.topics.join(", ")]);
  if (presentation.sourceUrl) entries.push(["source_url", "Source", presentation.sourceUrl]);
  return entries;
}

// Packs compact title facts into rows of a six-track grid (mirrors document_metadata.fact_spans):
// short values share rows of up to three, a medium value limits its row to two, long ones fill it.
export function factSpans(lengths) {
  const spans = [];
  let row = [];
  const flush = () => {
    spans.push(...row.map(() => 6 / row.length));
    row = [];
  };
  for (const length of lengths) {
    if (length > 48) {
      if (row.length) flush();
      spans.push(6);
      continue;
    }
    const candidate = [...row, length];
    if (candidate.length > (candidate.every(item => item <= 24) ? 3 : 2)) {
      flush();
      row = [length];
    } else row = candidate;
  }
  if (row.length) flush();
  return spans;
}

export function titlePageRows(metadata, presentation = {}) {
  const shown = titlePageSelection(metadata);
  return metadataEntries(metadata, presentation).filter(([key]) => shown.has(key))
    .map(([, label, value]) => [label, value]);
}

const months = ["january", "february", "march", "april", "may", "june", "july", "august",
  "september", "october", "november", "december"];
const datePattern = new RegExp(String.raw`(?:(\d{1,2})(?:st|nd|rd|th)?\s+)?(?:(${months.join("|")}|` +
  String.raw`${months.map(month => month.slice(0, 3)).join("|")})\.?,?\s+)?(?:(\d{1,2})(?:st|nd|rd|th)?,?\s+)?` +
  String.raw`((?:1[5-9]|20)\d{2})\b`, "gi");

// Returns {value, end_value?} when the text names one date, or a range of two; otherwise null.
export function noteDates(text) {
  const found = [];
  for (const match of text.matchAll(datePattern)) {
    const [, before, month, after, year] = match;
    const monthIndex = month ? months.findIndex(name => name.startsWith(month.toLowerCase().slice(0, 3))) : -1;
    const day = month ? before || after : null;
    let value = year;
    if (monthIndex >= 0) value += `-${String(monthIndex + 1).padStart(2, "0")}`;
    if (monthIndex >= 0 && day && Number(day) <= 31) value += `-${day.padStart(2, "0")}`;
    found.push(value);
  }
  if (found.length === 1) return {value: found[0]};
  if (found.length !== 2) return null;
  let [start, end] = found;
  if (start.length !== end.length) [start, end] = [start.slice(0, 4), end.slice(0, 4)];
  if (start === end) return {value: start};
  return start < end ? {value: start, end_value: end} : null;
}

const noteLabels = [
  [/^written and (first )?published/, "written+published"],
  [/^written/, "written"], [/^delivered/, "delivered"],
  [/^(first )?published|^publication/, "publication"],
  [/^source/, "source_edition"], [/^publisher/, "publisher"],
  [/^(translat|edited)/, "translation_note"],
  [/^(online version|download|other formats)/, "online_version"],
  [/transcri|mark(ed)? ?up|html/, "transcription"],
  [/^proof/, "proofreading"],
  [/^(public domain|copyleft|copyright)/, "rights"],
];

// Parses a marxists.org-style editorial note ("Label: value" lines) into metadata suggestions.
export function parseEditorialNote(lines) {
  const result = {dates: {}, text: {}};
  const add = (key, value) => {
    result.text[key] = result.text[key] ? `${result.text[key]}\n${value}` : value;
  };
  for (const {label, value} of lines) {
    const normalized = label.toLowerCase().replace(/\s+/g, " ").trim();
    const kind = noteLabels.find(([pattern]) => pattern.test(normalized))?.[1];
    const dated = noteDates(value);
    if (kind === "written+published") {
      if (dated) result.dates.written ??= dated;
      add("publication_note", `${label}: ${value}`);
    } else if (["written", "delivered"].includes(kind)) {
      if (dated) result.dates[kind] ??= dated;
      else add("notes", `${label}: ${value}`);
    } else if (kind === "publication") {
      if (dated && /^(first )?published$|^publication$/.test(normalized)) result.dates.publication ??= dated;
      add("publication_note", /^(first )?published$/.test(normalized) ? value : `${label}: ${value}`);
    } else if (["source_edition", "publisher"].includes(kind)) {
      add(kind, value);
    } else if (["translation_note", "online_version", "transcription", "proofreading", "rights"].includes(kind)) {
      add(kind, kind === "translation_note" && /^translated$/.test(normalized) ? value : `${label}: ${value}`);
    } else {
      add("notes", `${label}: ${value}`);
    }
  }
  return result;
}

// Finds the first paragraph made of at least two "Label: value" lines separated by hard breaks.
export function editorialNoteLines(root) {
  for (const paragraph of root.querySelectorAll("p")) {
    const lines = [[]];
    for (const node of paragraph.childNodes) {
      if (node.nodeName === "BR") lines.push([]);
      else lines.at(-1).push(node.textContent);
    }
    const parsed = lines.map(parts => /^\s*([^:\n]{2,60}?)\s*:\s*(\S[\s\S]*?)\s*$/.exec(parts.join("")))
      .filter(Boolean).map(([, label, value]) => ({label: label.trim(), value: value.replace(/\s+/g, " ")}));
    if (parsed.length >= 2) return parsed;
  }
  return [];
}
