import re
from functools import lru_cache
from urllib.parse import unquote, urljoin, urlsplit

from django.conf.locale import LANG_INFO

from library.services.errors import ImportFailure
from library.sources.base import Part, Source, image_url, meta
from library.sources.classification import fold, normalize_language
from profiles.marxist import archive

ARTICLE_SELECTORS = {
    "communistusa.org": ".et_pb_post_content",
    "marxist.com": ".article-content",
    "marxiste.org": ".com-content-article__body[itemprop=articleBody]",
    "communisme.ch": ".post-text",
    "kommunismus.ch": ".post-text",
    "communist.red": "main#content > article[id] .entry-content",
    "www.marxiste.qc.ca": "#article-content",
    "comunismo.ch": ".post-text",
    "rivoluzione.red": ".post-wrapper-content",
}
REMOVE = (
    "script, style, iframe, object, embed, form, input, button, noscript, "
    ".sharedaddy, #jp-relatedposts, .related-posts, .sd-sharing, "
    ".subscription-form, .code-block, .simplesocialbuttons"
)
SITE_LANGUAGES = {
    "marxiste.org": "fr",
    "communisme.ch": "fr",
    "kommunismus.ch": "de",
    "comunismo.ch": "it",
    "rivoluzione.red": "it",
}
LANGUAGE_PATHS = {"de", "en", "es", "fr", "it", "pt", "ru"}


@lru_cache(maxsize=256)
def language_code(value):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value or value.casefold() in {"und", "unknown", "undetermined"}:
        return ""
    for code, info in sorted(LANG_INFO.items(), key=lambda item: len(item[0])):
        if fold(value) in {fold(info.get("name", "")), fold(info.get("name_local", ""))}:
            return normalize_language(code)
    code = normalize_language(value)
    return "" if code == "und" else code


def source_language(soup, url):
    host = urlsplit(url).hostname
    if host in SITE_LANGUAGES:
        return SITE_LANGUAGES[host]
    html = soup.html if soup is not None else None
    if soup is not None:
        candidates = [str(html.get(key, "")) for key in ("lang", "xml:lang")] if html else []
        candidates += [meta(soup, key) for key in ("og:locale", "dc.language", "dcterms.language")]
        candidates += [
            str(node.get("content", ""))
            for node in soup.select("meta[http-equiv]")
            if node["http-equiv"].casefold() == "content-language"
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and (code := language_code(candidate)):
                return code
        from profiles.marxist.catalogue import article_data

        structured = article_data(soup, url).get("inLanguage", "")
        if isinstance(structured, dict):
            structured = structured.get("alternateName") or structured.get("name", "")
        if isinstance(structured, str) and (code := language_code(structured)):
            return code
    if urlsplit(url).hostname == "www.marxists.org":
        return archive.language(url)
    if urlsplit(url).hostname == "www.marxiste.qc.ca":
        return "fr"
    return "en"


def is_site_language_url(url):
    parts = urlsplit(url)
    language = SITE_LANGUAGES.get(parts.hostname)
    if not language:
        return True
    path = parts.path.lower()
    first_segment = path.strip("/").split("/", 1)[0]
    if parts.hostname in {"communisme.ch", "kommunismus.ch"}:
        return first_segment not in LANGUAGE_PATHS or first_segment == language
    if parts.hostname == "comunismo.ch":
        return path.startswith("/it/")
    return True


def discover(soup, url, *, force_book=False):
    host = urlsplit(url).hostname
    if host in SITE_LANGUAGES and not is_site_language_url(url):
        raise ImportFailure(
            f"This source is limited to {SITE_LANGUAGES[host]}-language articles.",
            "unsupported_language",
        )
    if host == "www.marxists.org":
        source = archive.discover(soup, url, force_book=force_book)
        source.metadata["language"] = source_language(soup, url)
        return source
    if force_book:
        raise ImportFailure(
            "Linked-section book reimport is currently supported for Marxists Internet Archive.",
            "unsupported",
        )
    selector = ARTICLE_SELECTORS.get(host)
    body = soup.select_one(selector) if selector else None
    if body is None or len(body.get_text(" ", strip=True)) < 100:
        raise ImportFailure("Unrecognized article layout or empty article body.", "layout")
    title_node = soup.select_one(
        "#article-title, h1.article-title, h2.article-title, h1.entry-title, h1.tck-article-title"
    )
    title = title_node.get_text(" ", strip=True) if title_node else meta(soup, "og:title")
    if host == "communistusa.org":
        title = title.removesuffix(" - Revolutionary Communists of America")
    if host == "www.marxiste.qc.ca":
        title = title.removesuffix(" | Révolution communiste")
    if not title:
        raise ImportFailure("Article title was not found.", "layout")
    metadata = {
        "author": (
            italian_source_byline(soup) if host == "rivoluzione.red" else meta(soup, "author")
        ),
        "published": meta(soup, "article:published_time"),
        "language": source_language(soup, url),
    }
    from profiles.marxist.catalogue import MarxistCatalogue

    details = MarxistCatalogue.metadata(soup, url)
    if details:
        metadata.update(author=details.author, published=details.published, topic=details.topic)
        metadata.update(authors=list(details.authors), topics=list(details.topics))
    return Source(title, metadata, [Part(url, title)], False)


def extract(soup, url, *, book=False, group="", chapter_title="", index=False):
    host = urlsplit(url).hostname
    if host == "www.marxists.org":
        body = archive.extract(soup, url, book=book, group=group, chapter_title=chapter_title)
    else:
        body = soup.select_one(ARTICLE_SELECTORS[host])
        if not body:
            raise ImportFailure("Article body disappeared.", "layout")
        if host == "communisme.ch":
            for node in list(body.select(".icon-add-block")):
                node.decompose()
        if host == "communist.red":
            intro = soup.select_one(".meta_intro > .entry-content")
            if intro:
                for node in reversed(list(intro.contents)):
                    body.insert(0, node.extract())
        if host == "rivoluzione.red":
            author = body.select_one("p em")
            if author and re.match(r"^\s*di\s+", author.get_text(" ", strip=True), re.I):
                author.find_parent("p").decompose()
        if host in {"communisme.ch", "kommunismus.ch"}:
            # This layout appends separate newspaper articles after a divider.
            for heading in list(body.find_all("h1", recursive=False)):
                divider = heading.find_previous_sibling()
                if divider and divider.name == "hr":
                    for sibling in list(divider.next_siblings):
                        sibling.extract()
                    divider.decompose()
                    break
        hero = meta(soup, "og:image")
        if hero and not any(image_matches_hero(image, hero, url) for image in body.select("img")):
            figure = soup.new_tag("figure")
            figure.append(soup.new_tag("img", src=hero, alt=""))
            body.insert(0, figure)
    for node in list(body.select(REMOVE)):
        node.decompose()
    for node in body.select("div.wp-caption, div.img_caption"):
        node.name = "figure"
    for node in body.select("span.wf_caption"):
        node.name = "figure"
        for caption in node.find_all("span", recursive=False):
            caption.name = "figcaption"
    for node in body.select("p.wp-caption-text, span.caption, p.img_caption, p.img_caption_text"):
        node.name = "figcaption"
    if len(body.get_text(" ", strip=True)) < 50 and not (
        index and (body.get_text(strip=True) or body.find(["img", "table"]))
    ):
        raise ImportFailure("Extracted body is empty or unexpectedly short.", "layout")
    return body


def image_matches_hero(image, hero, page_url):
    def identity(value):
        parts = urlsplit(urljoin(page_url, value))
        path = unquote(parts.path)
        host = parts.hostname
        if urlsplit(page_url).hostname == "www.marxiste.qc.ca" and host in {
            "www.marxiste.qc.ca",
            "marxiste.qc.ca",
            "admin.marxiste.qc.ca",
        }:
            path = path.removeprefix("/wordpress")
            host = "admin.marxiste.qc.ca"
        return host, path

    candidates = [image_url(image, page_url)]
    for key in ("srcset", "data-srcset"):
        candidates.extend(
            item.strip().split()[0] for item in str(image.get(key, "")).split(",") if item.strip()
        )
    return identity(hero) in {identity(candidate) for candidate in candidates}


class MarxistAdapter:
    discover = staticmethod(discover)
    extract = staticmethod(extract)


def italian_source_byline(soup):
    body = soup.select_one(".post-wrapper-content")
    first = body.find("p") if body else None
    if not first or not re.match(r"^\s*di\s+", first.get_text(" ", strip=True), re.I):
        return ""
    return re.sub(r"^\s*di\s+", "", first.get_text(" ", strip=True), flags=re.I)


def clean_site_author(value, host):
    if host == "comunismo.ch":
        return re.sub(r"^\s*✏\s*", "", value).strip()
    return value
