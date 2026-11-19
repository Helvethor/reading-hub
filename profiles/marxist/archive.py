import re
from urllib.parse import urljoin, urlsplit

from bs4 import Tag

from library.services.errors import ImportFailure
from library.services.fetch import canonical_url
from library.sources.base import Part, Source, image_url
from library.sources.classification import fold, split_authors

LANGUAGES = {
    "archive": "en",
    "history": "en",
    "subject": "en",
    "reference": "en",
    "glossary": "en",
    "english": "en",
    "francais": "fr",
    "deutsch": "de",
    "espanol": "es",
    "portugues": "pt",
    "italiano": "it",
    "russkij": "ru",
    "chinese": "zh",
    "arabic": "ar",
    "nihon": "ja",
    "japanese": "ja",
    "korean": "ko",
    "farsi": "fa",
    "turkce": "tr",
    "turkish": "tr",
    "polski": "pl",
    "nederlands": "nl",
    "svenska": "sv",
    "norsk": "no",
    "dansk": "da",
    "suomi": "fi",
    "ellinika": "el",
    "hebrew": "he",
    "indonesia": "id",
    "vietnamese": "vi",
    "cestina": "cs",
    "romana": "ro",
    "magyar": "hu",
    "bulgarsky": "bg",
    "srpshrva": "sh",
    "slovenian": "sl",
    "slovak": "sk",
    "catala": "ca",
    "euskara": "eu",
    "galego": "gl",
    "ukrainian": "uk",
    "hindi": "hi",
    "bangla": "bn",
    "tamil": "ta",
    "urdu": "ur",
    "afrikaans": "af",
    "shqip": "sq",
    "amharic": "am",
    "hayeren": "hy",
    "asamiya": "as",
    "azerbaycan": "az",
    "burmese": "my",
    "kernowek": "kw",
    "esperanto": "eo",
    "eesti": "et",
    "tagalog": "tl",
    "latvian": "lv",
    "lietuviu": "lt",
    "thai": "th",
    "mongolian": "mn",
    "kurdi": "ku",
    "makedonski": "mk",
    "nepali": "ne",
}
CHROME = (
    "nav, footer, script, style, .toplink, .footer, .updat, .download, .colab, .versoes, p.title"
)


def language(url):
    path = urlsplit(url).path.strip("/").split("/")
    return LANGUAGES.get(path[0], "und")


def metadata_value(soup, *keys):
    keys = {key.casefold() for key in keys}
    for node in soup.select("meta[content]"):
        if str(node.get("name") or node.get("property", "")).casefold() in keys:
            return str(node["content"]).strip()
    return ""


def publication_date(soup):
    return next(
        (fact["value"] for fact in date_facts(soup) if fact["type"] == "publication"),
        "",
    )


def subtitle(soup):
    declared = metadata_value(soup, "subtitle", "dc.alternative", "dcterms.alternative")
    if declared:
        return declared
    node = soup.select_one(".subtitle, .sous-titre, [itemprop=alternativeHeadline]")
    if node:
        return node.get_text(" ", strip=True)
    for heading in soup.select("body > h3"):
        preceding = heading.find_previous_sibling()
        following = heading.find_next_sibling()
        if preceding and preceding.name == "h2" and following and following.name == "h4":
            return following.get_text(" ", strip=True)
    return ""


def date_facts(soup):
    facts = []
    declared = metadata_value(
        soup,
        "dc.date",
        "dcterms.issued",
        "date",
        "article:published_time",
        "citation_publication_date",
    )
    if declared:
        facts.append(
            {
                "value": declared,
                "type": "publication",
                "evidence": declared,
                "method": "archive-date-metadata",
            }
        )
    years = {
        node.get_text(" ", strip=True)
        for node in soup.select(".an_pub")
        if re.fullmatch(r"[12]\d{3}", node.get_text(" ", strip=True))
    }
    if not declared and len(years) == 1:
        value = years.pop()
        facts.append(
            {
                "value": value,
                "type": "publication",
                "evidence": value,
                "method": "archive-publication-marker",
            }
        )
    labels = (
        (
            "publication",
            r"first published|first publication|premiere publication|"
            r"publie pour la premiere fois|po raz pierwszy opublikowane|erstveroffentlichung",
        ),
        ("written", r"written|composed|drafted|redacted|ecrit|écrit|geschrieben"),
        (
            "online_edition",
            r"online edition|digital edition|first online|edicion digital|edizione digitale",
        ),
    )
    cue_pattern = re.compile(
        r"(?:^|[\s.;])(?P<label>"
        + "|".join(f"(?:{pattern})" for _, pattern in labels)
        + r")\s*:\s*",
        re.I,
    )
    kinds = {
        pattern.casefold(): kind for kind, patterns in labels for pattern in patterns.split("|")
    }
    for node in soup.select(".information, .info, .pagenote"):
        text = " ".join(node.get_text(" ", strip=True).split())[:4000]
        matches = list(cue_pattern.finditer(text))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            evidence = text[match.end() : end].strip(" .;")
            years = set(re.findall(r"\b[12]\d{3}\b", evidence))
            if len(years) != 1:
                continue
            label = fold(match["label"])
            kind = next((value for key, value in kinds.items() if fold(key) == label), "unknown")
            facts.append(
                {
                    "value": years.pop(),
                    "type": kind,
                    "evidence": f"{match['label']}: {evidence}"[:1000],
                    "method": "archive-labelled-date",
                }
            )
    unique_facts = {}
    for fact in facts:
        unique_facts.setdefault((fact["type"], fact["value"]), fact)
    return list(unique_facts.values())


def title_author(soup, url=""):
    legacy_title = next(
        (node for node in soup.select(".titre") if not node.select_one(".titre")), None
    )
    author_node = soup.select_one(".author, .auteur, [rel=author], [itemprop=author]")
    heading = soup.find("h1")
    title_node = legacy_title or heading
    title = title_node.get_text(" ", strip=True) if title_node else ""
    author = author_node.get_text(" ", strip=True) if author_node else ""
    if author_node and "auteur" in author_node.get("class", []):
        author = re.sub(r"\s*\([12]\d{3}\s*[-\u2013\u2014]\s*[12]\d{3}\)\s*$", "", author)
    modern_header = soup.select_one("div.titre")
    if modern_header and soup.select_one("div.corps"):
        for extra in modern_header.select(".date-pub"):
            text = " ".join(extra.get_text(" ", strip=True).split())
            if re.match(r"^(?:chapitre|partie|livre)\s+[IVXLCDM\d]+\b", text, re.I):
                title = f"{title} - {text}"
                break
    if legacy_title:
        author = author or (heading.get_text(" ", strip=True) if heading else "")
    if not author and heading:
        previous = heading.find_previous_sibling(["h2", "h3"])
        if previous:
            author = previous.get_text(" ", strip=True)
        elif language(url) in {"pt", "da", "ko"}:
            following = heading.find_next_sibling(["h2", "p", "table", "div"])
            if following and following.name == "h2":
                author = following.get_text(" ", strip=True)
    author = author or metadata_value(soup, "author", "dc.creator")
    title = title or metadata_value(soup, "og:title", "dc.title")
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    return title.strip(), author.strip()


def contents_links(soup):
    containers = soup.select(".contents, .table-of-contents, #toc")
    containers += soup.find_all(class_=re.compile(r"^toc\d*$"))
    links = [anchor for node in containers for anchor in node.select("a[href]")]
    if links:
        return links
    labels = {
        "contents", "table of contents", "sommaire", "table des matieres",
        "inhalt", "inhaltsverzeichnis", "indice", "sumario",
    }
    marker = next(
        (node for node in soup.select("h1, h2, h3, h4, h5, h6, p")
         if fold(node.get_text(" ", strip=True)).strip(" :.") in labels),
        None,
    )
    return list(marker.find_all_next("a", href=True)) if marker else None


def chapter_parts(soup, url, *, force_book=False):
    directory = url.rsplit("/", 1)[0] + "/"
    origin = urlsplit(url)
    directory_path = urlsplit(directory).path
    filename = urlsplit(url).path.rsplit("/", 1)[-1].lower()
    is_index = filename in {"", "index.htm", "index.html", "er00t.htm"} or bool(
        re.search(r"(?:contents?|toc|index\d*|sommaire|indice|inhalt)\.html?$", filename)
    )
    marked_links = contents_links(soup)
    if not is_index and marked_links is None and not force_book:
        return []
    parts = {}
    fragments = {}
    anchors = (
        marked_links if not is_index and marked_links is not None else soup.select("a[href]")
    )
    for anchor in anchors:
        if anchor.find_parent(["nav", "footer"]):
            continue
        if anchor.find_parent(
            class_=re.compile(r"^(?:footer|final|toplink|information|info|title|versoes)$")
        ):
            continue
        paragraph = anchor.find_parent("p")
        if not is_index and paragraph and (
            len(paragraph.get_text(" ", strip=True))
            - sum(len(link.get_text(" ", strip=True)) for link in paragraph.select("a"))
        ) >= 100:
            continue
        raw = str(anchor["href"])
        target = urljoin(url, raw)
        parsed = urlsplit(target)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.netloc != origin.netloc
            or parsed.query
        ):
            continue
        local = parsed.path.startswith(directory_path)
        cross_work = (
            marked_links is not None
            and anchor in marked_links
            and parsed.path.split("/")[1:2] == origin.path.split("/")[1:2]
            and re.search(r"/works/\d{4}/", parsed.path)
            and anchor.find_parent(["h2", "h3", "h4", "h5", "h6", "li"])
        )
        if not local and not cross_work:
            continue
        relative = parsed.path[len(directory_path) :]
        if not parsed.path.lower().endswith((".htm", ".html")):
            continue
        if local and "/" in relative:
            if (
                marked_links is not None and anchor in marked_links
                or anchor.find_parent(["ul", "ol"])
                or anchor.find_parent(class_=re.compile(r"^(?:toc\d*|index)$"))
            ):
                raise ImportFailure(
                    "Archive contents link to nested chapter directories; "
                    "this structure needs explicit adapter support before importing.",
                    "archive_structure",
                )
            continue
        target = canonical_url(target)
        if target == canonical_url(url):
            continue
        label = anchor.get_text(" ", strip=True)
        if not label:
            continue
        fragments[target] = fragments.get(target, True) and bool(parsed.fragment)
        if target in parts:
            continue
        group = ""
        li = anchor.find_parent("li")
        parent = li.find_parent("li") if li else None
        if parent:
            group = " ".join(
                str(n).strip() for n in parent.contents if not isinstance(n, Tag)
            ).strip()
        parts[target] = Part(target, label, group)
    for target, part in parts.items():
        part.use_source_headings = fragments[target]
    if not is_index and not force_book and len(parts) < 2:
        return []
    return list(parts.values())


def is_discovery_page(soup, url):
    path = urlsplit(url).path.strip("/").split("/")
    filename = path[-1].lower()
    # Author/language library indexes are discovery pages, never whole books.
    directory_index = len(path) <= 2 or (
        len(path) <= 3
        and (urlsplit(url).path.endswith("/") or re.fullmatch(r"index\d*\.html?", filename))
        and not soup.select_one(".titre")
    )
    year_index = (
        len(path) > 1
        and re.fullmatch(r"\d{4}", path[-2])
        and path[-1].lower() in {"index.htm", "index.html"}
    )
    author_index = re.fullmatch(r"index\d*\.html?", path[-1].lower()) and (
        path[-2:-1] in (["works"], ["obras"], ["oeuvres"])
        or (
            len(path) == 4
            and path[1] in {"archive", "archiv", "biblioteka", "arhiva", "referenz", "reference"}
        )
    )
    named_index = filename in {"txtindex.htm", "txtindex.html"} or (
        len(path) <= 3 and re.fullmatch(r"works(?:-\d+)?\.html?", filename)
    )
    japanese_period_index = (
        language(url) == "ja"
        and len(path) > 2
        and re.fullmatch(r"\d{4}-\d+", path[-2])
        and filename in {"index.htm", "index.html"}
    )
    gallery_index = urlsplit(url).path.startswith("/espanol/m-e/imagen/") and filename in {
        "index.htm",
        "index.html",
    }
    return bool(
        directory_index
        or year_index
        or author_index
        or named_index
        or japanese_period_index
        or gallery_index
    )


def discover(soup, url, *, force_book=False):
    if is_discovery_page(soup, url):
        raise ImportFailure(
            "This is a discovery index/listing, not an article or a book.", "discovery"
        )
    if soup.body is None:
        raise ImportFailure("Archive page has no HTML body.", "layout")
    title, author = title_author(soup, url)
    if not title:
        raise ImportFailure("Archive work title was not found.", "layout")
    filename = urlsplit(url).path.rstrip("/").split("/")[-1].lower()
    parts = chapter_parts(soup, url, force_book=force_book)
    if force_book and not parts:
        raise ImportFailure("No linked HTML sections were found on this contents page.", "layout")
    if not parts and not has_prose(soup) and not soup.select_one(".titre"):
        raise ImportFailure("Archive directory or unsupported work layout.", "layout")
    if (
        filename in {"index.htm", "index.html", "er00t.htm"}
        and not parts
        and soup.select_one(".titre")
    ):
        raise ImportFailure("Book index contains no recognized HTML chapters.", "layout")
    metadata = {
        "author": author,
        "authors": split_authors(author),
        "language": language(url),
        "published": publication_date(soup),
        "date_facts": date_facts(soup),
        "subtitle": subtitle(soup),
        "topic": metadata_value(soup, "dc.subject", "classification"),
    }
    if parts:
        metadata["covers"] = [
            {"url": image_url(image, url), "alt": image.get("alt", "")}
            for image in soup.select("img")
            if "/img/" not in image_url(image, url)
        ]
    return Source(title, metadata, parts or [Part(url, title)], bool(parts))


def has_prose(soup):
    return any(
        len(node.get_text(" ", strip=True))
        - sum(len(link.get_text(" ", strip=True)) for link in node.select("a"))
        >= 100
        for node in soup.select("p, pre, .text, .chapter")
        if not node.find_parent(["nav", "footer"])
    )


def extract(soup, url, *, book=False, group="", chapter_title=""):
    body = soup.body
    if body is None:
        raise ImportFailure("Archive chapter has no HTML body.", "layout")
    title, author = title_author(soup, url)
    legacy = body.select_one(".titre")
    modern = body.select_one("div.corps")
    modern_header = body.select_one("div.titre")
    if modern and modern_header and modern.parent is body and modern_header.parent is body:
        for node in list(body.select("div.entete, div.titre, div.final")):
            if node.parent:
                preserve_targets(soup, node)
                node.decompose()
    elif legacy:
        header = body.find("h1")
        if not header:
            raise ImportFailure("Legacy archive author header was not found.", "layout")
        for sibling in list(header.previous_siblings):
            sibling.extract()
        header.decompose()
        for node in list(body.select(".titre")):
            node.decompose()
    else:
        for node in list(body.select("h1, h2, h3, .author"))[:4]:
            text = node.get_text(" ", strip=True)
            if text in {title, author}:
                preserve_targets(soup, node)
                node.decompose()
            elif re.fullmatch(r"\([12]\d{3}\)", text) and not any(
                len(previous.get_text(" ", strip=True)) >= 100
                for previous in node.find_all_previous(["p", "pre", "blockquote"])
            ):
                node.name = "p"
    for node in list(body.select(CHROME)):
        if node.parent:
            if node.name == "p" and node.select_one("p, h1, h2, h3, table, blockquote, pre"):
                continue
            preserve_targets(soup, node)
            node.decompose()
    for image in list(body.select("img")):
        if "/img/" in urljoin(url, image.get("src", "")):
            parent = image.find_parent("a")
            (parent or image).decompose()
    for node in reversed(list(body.select("table"))):
        if not node.get_text(strip=True) and not node.find("img"):
            preserve_targets(soup, node)
            node.decompose()
    for table in list(body.select("table")):
        paragraphs = table.select("p")
        if (
            paragraphs
            and table.select_one("p.ref")
            and all(set(p.get("class", [])) & {"an", "ref"} for p in paragraphs)
            and table.get_text(" ", strip=True)
            == " ".join(p.get_text(" ", strip=True) for p in paragraphs)
            and not any(
                len(p.get_text(" ", strip=True)) >= 100
                for p in table.find_all_previous("p")
                if not p.find_parent("table")
            )
        ):
            for paragraph in paragraphs:
                table.insert_before(paragraph.extract())
            preserve_targets(soup, table)
            table.decompose()
    for divider in list(body.select("hr")):
        if not divider.find_previous(["h2", "h3", "h4", "blockquote", "pre"]) and not any(
            len(p.get_text(" ", strip=True)) >= 100 for p in divider.find_all_previous("p")
        ):
            preserve_targets(soup, divider)
            divider.decompose()
    for node in body.select(".ss-titre, .chapit, .chapter, .sect"):
        if node.select_one("p, h1, h2, h3, table, blockquote, pre"):
            continue
        if group and node.get_text(" ", strip=True).casefold() == group.casefold():
            preserve_targets(soup, node)
            node.decompose()
        else:
            node.name = "h3" if "ss-titre" in node.get("class", []) else "h2"
    for node in body.select("p.exerg, p.citation"):
        node.name = "blockquote"
    if book:
        first = body.find(["h2", "h3"])
        if first and (
            first.name == "h2"
            or "ss-titre" not in first.get("class", [])
            or first.get_text(" ", strip=True).casefold() == chapter_title.casefold()
        ):
            preserve_targets(soup, first)
            first.decompose()
    return body


def preserve_targets(soup, node):
    if node.get("id"):
        node.insert_before(soup.new_tag("span", id=node["id"]))
    for target in list(node.select("a[name], [id]")):
        node.insert_before(target.extract())
