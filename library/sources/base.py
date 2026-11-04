import logging
import re
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup
from bs4.dammit import EncodingDetector

from library.services.errors import ImportFailure

logger = logging.getLogger("library")


@dataclass
class Part:
    url: str
    title: str
    group: str = ""
    use_source_headings: bool = False
    role: str = "chapter"
    section: str = ""
    excerpt: dict | None = None


@dataclass
class Source:
    title: str
    metadata: dict
    parts: list[Part]
    book: bool


def parse_html(data, headers=None):
    declared = EncodingDetector.find_declared_encoding(data, is_html=True)
    header = (headers or {}).get("content-type", "")
    match = re.search(r"charset=[\"']?([\w-]+)", header, re.I)
    encoding = declared or (match.group(1) if match else None)
    if encoding:
        encoding = {
            "ascii": "windows-1252",
            "us-ascii": "windows-1252",
            "iso-8859-1": "windows-1252",
            "iso8859-1": "windows-1252",
            "latin1": "windows-1252",
            "latin-1": "windows-1252",
            "gb2312": "gb18030",
            "gbk": "gb18030",
            "x-sjis": "cp932",
            "shift-jis": "cp932",
            "ks-c-5601-1987": "cp949",
            "euc-kr": "cp949",
        }.get(encoding.lower().replace("_", "-"), encoding)
    if data.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    if encoding:
        try:
            text = data.decode(encoding)
        except (UnicodeError, LookupError) as exc:
            if not isinstance(exc, UnicodeDecodeError):
                raise ImportFailure(f"Unable to decode source as {encoding}.", "encoding") from exc
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise ImportFailure(f"Unable to decode source as {encoding}.", "encoding") from exc
            logger.warning(
                "Source claims %s but contains valid UTF-8; using strict UTF-8.", encoding
            )
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = data.decode("windows-1252")
            except UnicodeDecodeError as exc:
                raise ImportFailure("Unable to decode source text.", "encoding") from exc
    if "\ufffd" in text:
        raise ImportFailure("Source text contains decoding replacement characters.", "encoding")
    return BeautifulSoup(text, "html.parser")


def meta(soup, key):
    key = re.compile(r"^" + re.escape(key) + "$", re.I)
    node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    return str(node.get("content", "")).strip() if node else ""


def image_url(image, page_url):
    raw = image.get("data-src") or image.get("data-lazy-src") or image.get("src", "")
    return urldefrag(urljoin(page_url, raw))[0]
