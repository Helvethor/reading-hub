import io
import warnings
from urllib.parse import urlsplit, urlunsplit

from PIL import Image, UnidentifiedImageError

from library.services.errors import ImportFailure
from library.services.fetch import validate_url

IMAGE_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif", "WEBP": "image/webp"}


def image_request_url(url):
    # Encode source path spaces without changing manifest keys or trusting other URL components.
    if url != url.lstrip() or any(ord(char) < 32 for char in url) or "\\" in url:
        return validate_url(url, asset=True)
    parts = urlsplit(url)
    requested = urlunsplit(parts._replace(path=parts.path.replace(" ", "%20")))
    return validate_url(requested, asset=True)


def fetch_image(fetcher, url):
    response = fetcher.fetch(image_request_url(url), asset=True)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(response.body)) as image:
                media_type = IMAGE_TYPES.get(image.format)
                if not media_type or response.media_type != media_type:
                    raise ImportFailure("Unsupported or mismatched raster image type.", "image")
                image.verify()
    except (
        OSError, UnidentifiedImageError, Image.DecompressionBombWarning,
        Image.DecompressionBombError, SyntaxError, ValueError,
    ) as exc:
        raise ImportFailure(f"Invalid raster image: {exc}", "image") from exc
    return response
