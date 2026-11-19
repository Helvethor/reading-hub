from bs4 import BeautifulSoup

from library.models import Blob
from library.services.book_views import publication_toc, publication_view
from library.services.document_edits import validate_editor_metadata
from library.services.editor_structure import section_structure
from library.services.semantic_documents import canonical_document, document_issue_details
from library.services.storage import read_blob


def prepare_workspace_document(value, original_metadata, original_structure, assets):
    document = canonical_document(value)
    document["metadata"] = validate_editor_metadata(
        original_metadata, document["metadata"],
    )
    document = canonical_document(document)
    issues = document_issue_details(document, assets)
    blocking = [issue["message"] for issue in issues if issue["blocking"]]
    if blocking:
        raise ValueError("Resolve document issues before previewing: " + "; ".join(blocking))
    content_issues = [issue for issue in issues if not issue["blocking"]]

    soup = BeautifulSoup(document["html"], "html.parser")
    structure = section_structure(
        soup, original_structure, document["metadata"].get("content_organization"),
        document_title=document["title"], metadata=document["metadata"],
    )
    structure["toc"] = publication_toc(
        soup, document["title"], book=structure["book"],
    )
    output_document = canonical_document({
        **document, "html": str(soup),
    })
    projection = publication_view(
        output_document["html"], structure["toc"], document["title"],
        book=structure["book"],
        metadata=document["metadata"],
    )

    image_digests = {
        image["src"].split("/")[2] for image in soup.select("img")
    }
    bindings = Blob.objects.in_bulk(image_digests)
    if set(bindings) != image_digests:
        raise ValueError("A retained image asset is no longer available.")
    for digest, blob in bindings.items():
        try:
            data = read_blob(digest)
        except OSError as exc:
            raise ValueError(f"A retained image asset is unavailable: {digest}") from exc
        if len(data) != blob.size:
            raise ValueError(f"A retained image asset failed its integrity check: {digest}")

    return {
        "document": document,
        "output_document": output_document,
        "structure": structure,
        "projection": projection,
        "assets": bindings,
        "issues": content_issues,
    }
