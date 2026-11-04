"""Explicit number-to-heading relationships over unchanged source block indices."""

import re

from bs4 import NavigableString, Tag

NUMBER = re.compile(r"(?:[0-9]{1,6}|[IVXLCDM]{1,12}|[A-Za-z])[.)]?", re.ASCII)
SEPARATORS = {". ", " ", ") "}


def number_heading_pairs(value, nodes, edits, media, notes):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Heading numbers must be a list of at most 100 relationships.")
    used = set()
    pairs = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"number", "heading", "separator"}:
            raise ValueError("Heading numbers require number, heading and separator.")
        indices = [item["number"], item["heading"]]
        if (
            any(type(index) is not int or not 0 <= index < len(nodes) for index in indices)
            or len(set(indices)) != 2
            or used.intersection(indices)
            or not isinstance(item["separator"], str)
            or item["separator"] not in SEPARATORS
        ):
            raise ValueError("Select distinct existing number and heading blocks and a separator.")
        number, heading = (nodes[index] for index in indices)
        if (
            not isinstance(number, Tag)
            or number.name not in {"p", "h1", "h2", "h3", "h4", "h5", "h6"}
            or not NUMBER.fullmatch(number.get_text(" ", strip=True))
            or number.find(["img", "br", "p", "sup", "sub"])
            or not isinstance(heading, Tag)
            or heading.name not in {"h1", "h2", "h3", "h4", "h5", "h6"}
            or not heading.get_text(strip=True)
            or heading.find(["img", "p", "br"])
            or number.parent is not heading.parent
        ):
            raise ValueError("Choose a standalone number and a heading in the same container.")
        siblings = list(number.next_siblings)
        position = next((i for i, node in enumerate(siblings) if node is heading), None)
        if position is None or any(
            (
                isinstance(node, Tag)
                and (
                    node.name in {"img", "hr", "br", "table"}
                    or node.get_text(strip=True)
                    or node.find(["img", "hr"])
                )
            )
            or (isinstance(node, NavigableString) and node.strip())
            for node in siblings[:position]
        ):
            raise ValueError("The number must precede its heading without intervening content.")

        def overlaps(index, targets=(number, heading)):
            node = nodes[index]
            return any(
                node is target or node in target.parents or target in node.parents
                for target in targets
            )

        for edit in edits:
            if overlaps(edit["index"]) and not (
                edit["index"] == item["heading"]
                and edit["action"] in {"h2", "h3", "h4", "h5", "h6"}
            ):
                raise ValueError(
                    "Remove conflicting block edits before attaching a heading number."
                )
        other_indices = [
            index for association in media for index in association.values() if index is not None
        ]
        for note in notes:
            other_indices.extend([note["reference"]["block"], note["target"]])
            if note["backlink"] is not None:
                other_indices.append(note["backlink"]["block"])
        if any(overlaps(index) for index in other_indices):
            raise ValueError("Heading numbers cannot overlap media associations or note repairs.")
        used.update(indices)
        pairs.append((number, heading, item["separator"]))
    return pairs


def apply_number_heading_pairs(pairs):
    for number, heading, separator in pairs:
        heading.__dict__["_reviewed_numbered_title"] = heading.get_text(" ", strip=True)
        strings = list(number.find_all(string=True))
        if strings:
            strings[0].replace_with(NavigableString(str(strings[0]).lstrip()))
            strings = list(number.find_all(string=True))
            strings[-1].replace_with(NavigableString(str(strings[-1]).rstrip()))
        number.name = "span"
        number.__dict__.pop("_reviewed_heading_level", None)
        number.__dict__.pop("_reviewed_original_level", None)
        if number.get_text(strip=True).endswith((".", ")")):
            separator = " "
        heading.insert(0, NavigableString(separator))
        heading.insert(0, number.extract())
