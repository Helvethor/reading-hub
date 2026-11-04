import json
import logging
import re
from html import unescape
from urllib.parse import parse_qsl, urljoin, urlsplit

from library.profile import get_profile
from library.services.errors import ImportFailure
from library.sources.base import meta, parse_html
from library.sources.catalogue import CatalogueLink
from library.sources.classification import (
    clean_attribution,
    clean_authors,
    infer_topics,
    split_authors,
    unique,
)
from profiles.marxist import archive
from profiles.marxist.adapters import (
    ARTICLE_SELECTORS,
    clean_site_author,
    is_site_language_url,
    italian_source_byline,
    source_language,
)

logger = logging.getLogger("library")


def text_at(node, selector):
    found = node.select_one(selector)
    return found.get_text(" ", strip=True) if found else ""


def byline(node):
    for found in node.select(
        ".createdby [itemprop=name], .author, .byline, .dipi-author a, "
        ".createdby, #article-byline-author, [rel=author], [itemprop=author] [itemprop=name]",
    ):
        if in_chrome(found):
            continue
        value = re.sub(
            r"^(?:Written by|By|Par|de|von)\s*:?\s+",
            "",
            found.get_text(" ", strip=True),
            flags=re.I,
        )
        value = clean_attribution(value)
        if value:
            return value
    return ""


def in_chrome(node):
    return bool(
        node.find_parent(["nav", "footer"])
        or node.find_parent(class_=re.compile(r"^(?:related-posts|sharedaddy)$"))
        or node.find_parent(id="jp-relatedposts")
    )


def article_data(soup, url):
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.get_text())
        except json.JSONDecodeError:
            logger.warning("Invalid source JSON-LD metadata at %s", url)
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph", [])
            for item in [node, *(graph if isinstance(graph, list) else [])]:
                if not isinstance(item, dict):
                    continue
                types = item.get("@type", [])
                types = [types] if isinstance(types, str) else types
                if not isinstance(types, list):
                    continue
                types = [kind.rsplit("/", 1)[-1] for kind in types if isinstance(kind, str)]
                if any(
                    kind in types
                    for kind in (
                        "Article",
                        "NewsArticle",
                        "BlogPosting",
                        "ScholarlyArticle",
                        "Book",
                    )
                ):
                    return item
    return {}


def structured_names(value):
    if isinstance(value, str):
        return unescape(value)
    if isinstance(value, dict):
        return structured_names(value.get("name", ""))
    if isinstance(value, list):
        return ", ".join(filter(None, (structured_names(item) for item in value)))
    return ""


def structured_authors(value):
    items = value if isinstance(value, list) else [value]
    return clean_authors(structured_names(item) for item in items)


def topic_at(node):
    value = text_at(node, "[rel=category], [rel='category tag'], [itemprop=articleSection]")
    if not value:
        categories = [
            value.removeprefix("category-").replace("-", " ")
            for value in node.get("class", [])
            if value.startswith("category-")
            and value not in {"category-highlights", "category-featured"}
        ]
        value = ", ".join(categories)
    return value


class MarxistCatalogue:
    @staticmethod
    def book_source(soup, url):
        if urlsplit(url).hostname != "www.marxists.org":
            return None
        try:
            source = archive.discover(soup, url)
        except ImportFailure as exc:
            if exc.code not in {"layout", "discovery"}:
                raise
            return None
        return source if source.book else None

    @staticmethod
    def is_discovery_page(soup, url):
        return urlsplit(url).hostname == "www.marxists.org" and archive.is_discovery_page(soup, url)

    @staticmethod
    def date_facts(soup, url):
        return archive.date_facts(soup) if urlsplit(url).hostname == "www.marxists.org" else []

    @staticmethod
    def media_types(url):
        parts = urlsplit(url)
        if parts.hostname in {
            "kommunismus.ch",
            "communist.red",
            "comunismo.ch",
            "rivoluzione.red",
        } and parts.path.endswith(".xml"):
            return {"application/xml", "text/xml", "text/html"}
        if (
            parts.hostname == "www.marxiste.qc.ca"
            and parts.path == "/archive"
            and dict(parse_qsl(parts.query)).get("type") == "ajax"
        ):
            return {"application/json"}
        return None

    @staticmethod
    def parse_response(response):
        if response.media_type == "application/json":
            try:
                data = json.loads(response.body)
                if not isinstance(data, dict) or not isinstance(data.get("content"), str):
                    raise ValueError("Missing article listing content")
                next_page = data.get("nextPage", "")
                if not isinstance(next_page, str):
                    raise ValueError("Invalid next-page cursor")
            except (ValueError, UnicodeDecodeError) as exc:
                raise ImportFailure("Invalid source archive JSON response.", "layout") from exc
            soup = parse_html(data["content"].encode())
            if next_page:
                soup.append(soup.new_tag("div", attrs={"data-next-page": next_page}))
            return soup
        return parse_html(response.body, response.headers)

    @staticmethod
    def links(soup, url):
        host = urlsplit(url).hostname
        if host in {
            "kommunismus.ch",
            "communist.red",
            "comunismo.ch",
            "rivoluzione.red",
        } and urlsplit(url).path.endswith(".xml"):
            for loc in soup.select("url > loc"):
                target = loc.get_text(strip=True)
                if not is_site_language_url(target):
                    continue
                slug = urlsplit(target).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
                yield CatalogueLink(target, slug, True, language=source_language(None, target))
            return
        if host == "www.marxiste.qc.ca":
            for node in soup.select("[data-next-page]"):
                if node["data-next-page"]:
                    yield CatalogueLink(
                        urljoin(url, node["data-next-page"]), "More articles", False
                    )
        for anchor in soup.select("a[href], area[href], link[rel=alternate][href]"):
            target = urljoin(url, anchor["href"])
            parts = urlsplit(target)
            if parts.scheme not in {"http", "https"}:
                continue
            if not is_site_language_url(target):
                continue
            path = parts.path.lower()
            if re.search(
                r"/(?:wp-admin|wp-json|wp-content|feed|login|shop|donate|contact|admin|audio|ebooks)(?:/|$)",
                path,
            ):
                continue
            if any(key not in {"page", "start", "limitstart"} for key, _ in parse_qsl(parts.query)):
                continue
            if path.rsplit("/", 1)[-1].count(".") and not path.endswith((".htm", ".html", ".php")):
                continue
            title = anchor.get_text(" ", strip=True) or anchor.get("alt", "")
            heading = anchor.find_parent(["h1", "h2", "h3", "h4"])
            if host == "www.marxiste.qc.ca":
                article = path.startswith("/article/") and bool(title)
            elif host == "www.marxists.org":
                filename = path.rsplit("/", 1)[-1]
                article = (
                    path.endswith((".htm", ".html"))
                    and not filename.startswith(("index", "english"))
                    and filename not in {"authors.htm", "liens.htm"}
                )
            elif host == "marxist.com":
                article = bool(heading and anchor.find_parent("article"))
            elif host == "marxiste.org":
                if path.startswith((
                    "/administrator/", "/api/", "/component/", "/components/",
                    "/modules/", "/plugins/",
                )):
                    continue
                article = bool(heading or anchor.find_parent(class_="jt-title")) and path != "/"
            elif host == "communistusa.org":
                article = bool(heading)
                category_menu = anchor.find_parent("li", class_="menu-item-object-category")
                if (
                    path.startswith(("/category/", "/tag/", "/author/", "/page/"))
                    or path == "/"
                    or category_menu
                ):
                    article = False
                elif not article:
                    continue
            elif host in {"kommunismus.ch", "communist.red"}:
                article = (
                    bool(heading)
                    and not path.startswith(("/category/", "/tag/", "/author/", "/page/"))
                    and path != "/"
                )
            elif host == "comunismo.ch":
                article = bool(heading) and path.startswith("/it/")
            else:
                article = bool(heading)
            if article and not title:
                continue
            container = (
                anchor.find_parent("article")
                or anchor.find_parent(class_="dipi-blog-post")
                or anchor.find_parent(class_="card")
            )
            time_node = container.find("time") if container else None
            topic = topic_at(container) if container else ""
            if not topic and host == "communisme.ch" and article:
                # These are the source's own category URL segments, not inferred subjects.
                categories = [part for part in parts.path.split("/") if part][1:-1]
                topic = " / ".join(
                    part.removesuffix("-fr").replace("-", " ") for part in categories
                )
            yield CatalogueLink(
                target,
                title,
                article,
                author=clean_site_author(byline(container), host) if container else "",
                published=str(time_node.get("datetime", "")) if time_node else "",
                topic=topic,
                language=source_language(None, target),
            )

    @staticmethod
    def metadata(soup, url):
        host = urlsplit(url).hostname
        if host in {"communisme.ch", "kommunismus.ch", "comunismo.ch"} and not is_site_language_url(
            url
        ):
            return None
        if host == "www.marxists.org":
            if MarxistCatalogue.is_discovery_page(soup, url):
                return None
            if soup.body is None and soup.select_one(".titre") and soup.find("h1"):
                title, author = archive.title_author(soup)
                return CatalogueLink(
                    url, title, True, author=author, authors=tuple(split_authors(author))
                )
            try:
                source = archive.discover(soup, url)
            except ImportFailure as exc:
                if exc.code not in {"layout", "discovery"}:
                    raise
                return None
            return CatalogueLink(
                url,
                source.title,
                True,
                source.metadata["author"],
                published=source.metadata["published"],
                topic=source.metadata["topic"],
                authors=tuple(source.metadata["authors"]),
                language=source_language(soup, url),
                topics=tuple(
                    unique(
                        source.metadata["topic"].split(",")
                        + infer_topics(
                            source.title + " " + parse_content(soup.body),
                            get_profile().topic_rules,
                        )
                    )
                ),
            )
        selector = ARTICLE_SELECTORS.get(host)
        if not selector or not soup.select_one(selector):
            return None
        data = article_data(soup, url)
        title_node = soup.select_one(
            "#article-title, h1.article-title, h2.article-title, h1.entry-title, h1"
        )
        title = (
            meta(soup, "og:title")
            or (title_node.get_text(" ", strip=True) if title_node else "")
            or structured_names(data.get("headline"))
        )
        if host in {"www.marxiste.qc.ca", "communist.red"} and title_node:
            title = title_node.get_text(" ", strip=True) or title
        if host == "communistusa.org":
            title = title.removesuffix(" - Revolutionary Communists of America")
        if host == "www.marxiste.qc.ca":
            title = title.removesuffix(" | Révolution communiste")
        if not title:
            return None
        time_node = next(
            (
                node
                for selector in ("[itemprop=datePublished]", "time[datetime]")
                for node in soup.select(selector)
                if not in_chrome(node)
            ),
            None,
        )
        author = clean_site_author(
            clean_attribution(
                meta(soup, "author") or meta(soup, "dc.creator") or meta(soup, "dcterms.creator")
            )
            or (italian_source_byline(soup) if host == "rivoluzione.red" else byline(soup)),
            host,
        )
        if host == "communist.red":
            author = byline(soup) or author
        authors = split_authors(author) if author else structured_authors(data.get("author"))
        if not authors:
            authors = clean_authors(
                str(node.get("content", ""))
                for node in soup.select("meta[name]")
                if node["name"].casefold() == "citation_author"
            )
        author = author or ", ".join(authors)
        published = (
            meta(soup, "article:published_time")
            or meta(soup, "dcterms.issued")
            or meta(soup, "dc.date")
            or (
                str(
                    time_node.get("datetime")
                    or time_node.get("content")
                    or time_node.get_text(" ", strip=True)
                )
                if time_node
                else ""
            )
            or structured_names(data.get("datePublished"))
        )
        if host == "www.marxiste.qc.ca" and not published:
            raw_date = text_at(soup, "#article-byline-date")
            months = {
                "janv": 1,
                "févr": 2,
                "mars": 3,
                "avr": 4,
                "mai": 5,
                "juin": 6,
                "juil": 7,
                "août": 8,
                "sept": 9,
                "oct": 10,
                "nov": 11,
                "déc": 12,
            }
            match = re.search(r"(\d{1,2})\s+([^\s.]+)\.?\s+(\d{4})", raw_date)
            if match and match[2].lower() in months:
                from datetime import date

                try:
                    published = date(
                        int(match[3]), months[match[2].lower()], int(match[1])
                    ).isoformat()
                except ValueError:
                    logger.warning("Invalid Quebec publication date at %s: %s", url, raw_date)
            elif raw_date:
                logger.warning("Unrecognized Quebec publication date at %s: %s", url, raw_date)
        sections = [
            str(node.get("content", "")).strip()
            for node in soup.select(
                'meta[property="article:section"], meta[name="article:section"]'
            )
        ]
        topic = (
            ", ".join(unique(sections))
            or topic_at(soup)
            or structured_names(data.get("articleSection"))
            or structured_names(data.get("about"))
        )
        body = soup.select_one(selector)
        content = parse_content(body)
        topics = unique(
            [part.strip() for part in re.split(r",| / ", topic) if part.strip()]
            + infer_topics(title + " " + content, get_profile().topic_rules)
        )
        return CatalogueLink(
            url,
            title,
            True,
            author=author,
            published=published,
            topic=topic,
            authors=tuple(authors),
            topics=tuple(topics),
            language=source_language(soup, url),
        )

    language = staticmethod(source_language)


def parse_content(body):
    from bs4 import BeautifulSoup

    clean = BeautifulSoup(str(body), "html.parser")
    for heading in list(clean.find_all("h1", recursive=False)) + list(
        clean.select(".post-text > h1")
    ):
        divider = heading.find_previous_sibling()
        if divider and divider.name == "hr":
            for sibling in list(divider.next_siblings):
                sibling.extract()
            divider.decompose()
            break
    for node in clean.select(
        "script, style, nav, footer, .related-posts, #jp-relatedposts, .sharedaddy"
    ):
        node.decompose()
    return clean.get_text(" ", strip=True)
