from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogueLink:
    url: str
    title: str = ""
    is_article: bool = False
    author: str = ""
    published: str = ""
    topic: str = ""
    era: str = ""
    authors: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    language: str = ""
