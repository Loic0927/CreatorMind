import re
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None


NUMBER_PATTERNS = {
    "views": re.compile(r"views?\D+([\d,.]+[kKmM]?)"),
    "likes": re.compile(r"likes?\D+([\d,.]+[kKmM]?)"),
    "comments": re.compile(r"comments?\D+([\d,.]+[kKmM]?)"),
    "shares": re.compile(r"shares?\D+([\d,.]+[kKmM]?)"),
    "retention_rate": re.compile(r"retention\D+(\d+(?:\.\d+)?)%"),
}


def _normalize_number(raw: str) -> float:
    value = raw.replace(",", "").strip().lower()
    if value.endswith("k"):
        return float(value[:-1]) * 1_000
    if value.endswith("m"):
        return float(value[:-1]) * 1_000_000
    return float(value)


def extract_metrics_from_text(text: str) -> dict[str, float]:
    matches: dict[str, float] = {}
    lowered = text.lower()
    for key, pattern in NUMBER_PATTERNS.items():
        match = pattern.search(lowered)
        if match:
            matches[key] = _normalize_number(match.group(1))
    return matches


def extract_screenshot_metrics(file_bytes: bytes, filename: str) -> dict[str, Any]:
    messages: list[str] = []
    extracted_text = ""

    if pytesseract is None or Image is None:
        messages.append("OCR libraries are not installed, so screenshot parsing is unavailable in this environment.")
        return {
            "candidate_metrics": {},
            "confidence_level": "low",
            "messages": messages,
            "raw_text": extracted_text,
            "filename": filename,
        }

    try:
        from io import BytesIO

        image = Image.open(BytesIO(file_bytes))
        extracted_text = pytesseract.image_to_string(image)
        candidate_metrics = extract_metrics_from_text(extracted_text)

        if candidate_metrics:
            messages.append("Candidate metrics were extracted from the uploaded screenshot. Review and confirm them before audit.")
            confidence = "medium"
        else:
            messages.append("No recognizable metric labels were found in the screenshot text.")
            confidence = "low"
    except Exception as exc:  # pragma: no cover
        messages.append(f"Screenshot parsing failed: {exc}")
        candidate_metrics = {}
        confidence = "low"

    return {
        "candidate_metrics": candidate_metrics,
        "confidence_level": confidence,
        "messages": messages,
        "raw_text": extracted_text,
        "filename": filename,
    }
