from bs4 import BeautifulSoup, Tag


def association_nodes(value, nodes, edits):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Media associations must be a list of at most 100 figures.")
    used = set()
    result = []
    for association in value:
        if not isinstance(association, dict) or set(association) != {"image", "caption", "credit"}:
            raise ValueError("Each media association requires image, caption and credit indices.")
        indices = [association["image"]]
        indices.extend(
            association[key] for key in ("caption", "credit") if association[key] is not None
        )
        if (
            type(association["image"]) is not int
            or len(indices) < 2
            or any(type(index) is not int or not 0 <= index < len(nodes) for index in indices)
            or len(set(indices)) != len(indices)
            or used.intersection(indices)
        ):
            raise ValueError(
                "Select one existing image and distinct caption/credit blocks, used once."
            )
        image = nodes[association["image"]]
        if not isinstance(image, Tag) or image.name != "img":
            raise ValueError("The media image must identify an image block.")
        texts = [nodes[index] for index in indices[1:]]
        if any(
            not isinstance(node, Tag)
            or node.name not in {"p", "figcaption"}
            or not node.get_text(strip=True)
            or node.find(["img", "figure", "table", "hr", "h1", "h2", "h3", "h4", "h5", "h6"])
            for node in texts
        ):
            raise ValueError(
                "Caption/credit must be non-empty paragraph or figcaption text blocks."
            )
        carrier = image
        while (
            carrier.parent.name in {"a", "p", "div"}
            and len(carrier.parent.find_all(True, recursive=False)) == 1
            and not carrier.parent.get_text(strip=True)
        ):
            carrier = carrier.parent
        figure = image.find_parent("figure")
        if figure:
            if len(figure.select("img")) != 1 or figure.find("blockquote"):
                raise ValueError(
                    "Choose a single-image figure, not a quotation or multi-image group."
                )
            carrier = figure
            if any(
                not any(caption is text for text in texts)
                for caption in figure.select("figcaption")
            ):
                raise ValueError("Select the figure's existing caption to preserve it explicitly.")
            if any(
                node.get_text(strip=True)
                and not any(
                    node is text or any(text is parent for parent in node.parents) for text in texts
                )
                for node in figure.find_all(["p", "figcaption"])
            ):
                raise ValueError(
                    "The existing figure has additional text. Review its blocks first."
                )
        peers = [text for text in texts if text.parent is not figure]
        if any(text.parent is not carrier.parent for text in peers):
            raise ValueError(
                "Image and caption/credit must share a container; "
                "cross-container moves are unsupported."
            )
        siblings = list(carrier.parent.find_all(True, recursive=False))
        positions_by_id = {id(node): index for index, node in enumerate(siblings)}
        selected_ids = {id(node) for node in [carrier, *peers]}
        positions = [positions_by_id[id(node)] for node in [carrier, *peers]]
        between = siblings[min(positions) : max(positions) + 1]
        if any(
            id(node) not in selected_ids
            and (
                node.name in {"img", "hr", "h1", "h2", "h3", "h4", "h5", "h6"}
                or node.find(["img", "hr", "h1", "h2", "h3", "h4", "h5", "h6"])
            )
            for node in between
        ):
            raise ValueError("A media association cannot cross another image, heading or divider.")
        affected = [carrier, *texts]
        for edit in edits:
            node = nodes[edit["index"]]
            if any(
                node is target
                or any(node is parent for parent in target.parents)
                or any(target is parent for parent in node.parents)
                for target in affected
            ):
                raise ValueError(
                    "Do not combine media associations with edits to their blocks or containers."
                )
        used.update(indices)
        result.append((carrier, figure, association, texts))
    return result


def apply_associations(associations):
    soup = BeautifulSoup("", "html.parser")
    for carrier, figure, association, texts in associations:
        if figure is None:
            figure = soup.new_tag("figure")
            carrier.insert_before(figure)
            figure.append(carrier.extract())
        caption = soup.new_tag("figcaption")
        figure.append(caption)
        for key, node in zip(
            [key for key in ("caption", "credit") if association[key] is not None],
            texts,
            strict=True,
        ):
            if node.name == "figcaption":
                node.name = "div"
            if key == "credit":
                node.__dict__["_reviewed_media_credit"] = True
            caption.append(node.extract())
