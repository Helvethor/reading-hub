"""Replace recognized third-party social players with stable, compact source links."""

from urllib.parse import parse_qs, urlsplit


def social_url(value):
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"https", "http"}:
        return ""
    if not any(
        host == domain or host.endswith("." + domain)
        for domain in ("instagram.com", "facebook.com")
    ):
        return ""
    if parsed.path.startswith("/plugins/"):
        return social_url(parse_qs(parsed.query).get("href", [""])[0])
    return value


def compact_social_embeds(soup):
    for node in list(soup.select("blockquote.instagram-media, .fb-post, .fb-video, iframe[src]")):
        if node.parent is None:
            continue
        raw = node.get("data-instgrm-permalink") or node.get("data-href") or node.get("src", "")
        url = social_url(str(raw))
        if not url:
            url = next(
                (url for link in node.select("a[href]") if (url := social_url(link["href"]))),
                "",
            )
        if not url:
            continue
        platform = "Instagram" if "instagram.com" in urlsplit(url).hostname else "Facebook"
        attribution = next(
            (
                link.get_text(" ", strip=True)
                for link in reversed(node.select("p a[href]"))
                if social_url(link["href"]) and link.get_text(" ", strip=True)
            ),
            "",
        )
        replacement = soup.new_tag("p")
        for target in [node, *node.select("[id], a[name]")]:
            for identifier in dict.fromkeys([target.get("id"), target.get("name")]):
                if identifier:
                    replacement.append(soup.new_tag("span", id=identifier))
        link = soup.new_tag("a", href=url)
        link.string = f"View on {platform}" + (f": {attribution}" if attribution else "")
        replacement.append(link)
        node.replace_with(replacement)
