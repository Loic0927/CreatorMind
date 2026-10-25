from urllib.parse import parse_qs, unquote, urlparse

from pydantic import BaseModel


class ParsedUrlAnalysis(BaseModel):
    prediction_input: dict
    caption_text: str = ""
    source_url: str


def detect_platform(parsed_url) -> str:
    hostname = parsed_url.netloc.lower()

    if "tiktok.com" in hostname:
        return "TikTok"
    if "instagram.com" in hostname:
        return "Instagram"
    if "youtube.com" in hostname or "youtu.be" in hostname:
        return "YouTube"

    raise ValueError("Unsupported URL. Use a TikTok, Instagram, or YouTube URL.")


def detect_content_type(platform: str, parsed_url) -> str:
    path = parsed_url.path.lower()

    if platform == "Instagram":
        if "/reel/" in path or "/reels/" in path:
            return "Reel"
        if "/stories/" in path:
            return "Story"
        return "Post"

    if platform == "YouTube":
        if "/shorts/" in path or "youtu.be" in parsed_url.netloc.lower():
            return "Short"
        return "Post"

    if platform == "TikTok":
        return "Short"

    return "Post"


def extract_caption_text(parsed_url) -> str:
    query = parse_qs(parsed_url.query)

    for key in ["caption", "text", "description", "title"]:
        if key in query and query[key]:
            return unquote(query[key][0]).strip()

    path_parts = [part for part in parsed_url.path.split("/") if part]
    if not path_parts:
        return ""

    slug = path_parts[-1].replace("-", " ").replace("_", " ")
    return unquote(slug).strip()


def approximate_posting_hour(platform: str) -> int:
    if platform in {"Instagram", "TikTok"}:
        return 18
    return 16


def parse_content_url(url: str) -> ParsedUrlAnalysis:
    parsed_url = urlparse(url.strip())

    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("Invalid URL. Include the full http:// or https:// content link.")

    platform = detect_platform(parsed_url)
    content_type = detect_content_type(platform, parsed_url)
    caption_text = extract_caption_text(parsed_url)
    caption_length = len(caption_text)
    posting_hour = approximate_posting_hour(platform)

    return ParsedUrlAnalysis(
        source_url=url,
        caption_text=caption_text,
        prediction_input={
            "platform": platform,
            "contentType": content_type,
            "captionLength": caption_length,
            "hashtagsCount": 0,
            "postingHour": posting_hour,
        },
    )
