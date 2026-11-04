"""Source-bound presentation overrides with exact text-range evidence."""

from bs4 import Comment, NavigableString, Tag
from tinycss2 import parse_declaration_list, serialize

ALIGNMENTS = ("left", "right", "center", "justify")
STYLES = ("italic", "bold", "underline", "strikethrough", "superscript", "subscript")


def inline_alignment(node):
    if not isinstance(node, Tag):
        return ""
    declarations = [
        item for item in parse_declaration_list(node.get("style", ""))
        if item.type == "declaration" and item.lower_name == "text-align"
        and serialize(item.value).strip().lower() in ALIGNMENTS
    ]
    if not declarations:
        return ""
    item = next((item for item in reversed(declarations) if item.important), declarations[-1])
    return serialize(item.value).strip().lower()


def source_text(node):
    if isinstance(node, Tag):
        return "".join(str(text) for text in node.find_all(string=True)
                       if not isinstance(text, Comment))
    return str(node)


def validate_presentations(edits, nodes, excluded):
    if not isinstance(edits, list) or len(edits) > 500:
        raise ValueError("Presentation corrections must contain at most 500 blocks.")
    seen = set()
    for edit in edits:
        if (
            not isinstance(edit, dict) or "index" not in edit
            or set(edit) - {"index", "align", "styles", "ranges"}
        ):
            raise ValueError("Presentation requires index and alignment, styles or text ranges.")
        index = edit["index"]
        if type(index) is not int or not 0 <= index < len(nodes) or index in seen:
            raise ValueError("Select a unique existing presentation block.")
        seen.add(index)
        node = nodes[index]
        if not isinstance(node, Tag) or node.name in {"img", "hr"}:
            raise ValueError("Presentation requires a text-containing source block.")
        if any(node is nodes[value] or nodes[value] in node.parents for value in excluded):
            raise ValueError("Do not style an excluded block or its descendants.")
        if "align" in edit and edit["align"] not in ("", *ALIGNMENTS):
            raise ValueError("Choose left, right, center, justify or source alignment.")
        validate_styles(edit.get("styles", {}))
        ranges = edit.get("ranges", [])
        if not isinstance(ranges, list) or len(ranges) > 200:
            raise ValueError("Use at most 200 text style ranges per block.")
        text = source_text(node)
        for span in ranges:
            if (
                not isinstance(span, dict) or set(span) != {"start", "end", "text", "styles"}
                or type(span["start"]) is not int or type(span["end"]) is not int
                or not 0 <= span["start"] < span["end"] <= len(text)
                or span["text"] != text[span["start"]:span["end"]]
            ):
                raise ValueError("Selected text no longer matches the exact source block.")
            validate_styles(span["styles"])


def validate_styles(styles):
    if (
        not isinstance(styles, dict) or set(styles) - set(STYLES)
        or any(type(value) is not bool for value in styles.values())
        or styles.get("superscript") and styles.get("subscript")
    ):
        raise ValueError("Choose supported boolean styles; superscript and subscript conflict.")


def style_classes(styles):
    return [f"text-{key}-{'on' if value else 'off'}" for key, value in styles.items()]


def update_styles(target, values):
    target.update(values)
    if values.get("superscript"):
        target["subscript"] = False
    if values.get("subscript"):
        target["superscript"] = False


def apply_presentations(edits, nodes):
    targets = {}
    decorations = {}
    semantic = {"u": "underline", "s": "strikethrough", "sup": "superscript", "sub": "subscript"}
    for edit in sorted(edits, key=lambda item: len(list(nodes[item["index"]].parents))):
        node = nodes[edit["index"]]
        if "align" in edit:
            node.__dict__["_reviewed_alignment"] = edit["align"]
        block_styles = edit.get("styles", {})
        node.__dict__["_reviewed_presentation"] = style_classes(
            {key: value for key, value in block_styles.items() if key in {"bold", "italic"}}
        )
        ranges = edit.get("ranges", [])
        if not block_styles and not ranges:
            continue
        for decoration in node.find_all(list(semantic)):
            decorations[id(decoration)] = decoration
        offset = 0
        for text in list(node.find_all(string=True)):
            if isinstance(text, Comment):
                continue
            value = str(text)
            end = offset + len(value)
            target = targets.setdefault(id(text), {"text": text, "applications": []})
            if block_styles:
                target["applications"].append(
                    {"start": 0, "end": len(value), "styles": block_styles}
                )
            for span in ranges:
                if span["start"] < end and span["end"] > offset:
                    target["applications"].append({
                        "start": max(0, span["start"] - offset),
                        "end": min(len(value), span["end"] - offset), "styles": span["styles"],
                    })
            offset = end
    for target in targets.values():
        text, applications = target["text"], target["applications"]
        inherited = {}
        for parent in reversed(list(text.parents)):
            if id(parent) in decorations:
                update_styles(inherited, {semantic[parent.name]: True})
        value = str(text)
        points = sorted({0, len(value)} | {
            span[key] for span in applications for key in ("start", "end")
        })
        for start, stop in zip(points, points[1:], strict=False):
            part = NavigableString(value[start:stop])
            styles = dict(inherited)
            for span in applications:
                if span["start"] <= start and span["end"] >= stop:
                    update_styles(styles, span["styles"])
            if styles:
                wrapper = Tag(name="span")
                wrapper.__dict__["_reviewed_presentation"] = style_classes(styles)
                wrapper.append(part)
                text.insert_before(wrapper)
            else:
                text.insert_before(part)
        text.extract()
    for node in decorations.values():
        node.name = "span"
