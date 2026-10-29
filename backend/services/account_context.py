"""Structured, account-scoped creator context with conservative relevance checks."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Literal
from collections import Counter


CONTEXT_STORAGE_VERSION = 2
MAX_SERIALIZED_CONTEXT_LENGTH = 12000
_WORDS = re.compile(r"[^\W_][\w'-]{1,}", re.UNICODE)
_STOP_WORDS = {
    "about", "account", "audience", "brand", "content", "creator", "family",
    "focused", "friendly", "guidance", "people", "social", "this", "with",
    "when", "from", "that", "their", "through", "into", "your", "the", "and",
    "for", "are", "who", "enjoy", "based", "using", "make", "more",
}

TONE_KEYS = {"warm", "direct", "playful", "educational", "professional", "conversational", "calm", "bold", "other"}
CONTENT_FORMAT_KEYS = {"image", "carousel", "reel_video", "story", "text"}
CAPTION_LANGUAGE_KEYS = {"auto", "english", "traditional_chinese", "simplified_chinese", "japanese", "korean", "spanish", "other"}
PRIMARY_CATEGORY_KEYS = {"education", "entertainment", "inspiration", "personal", "product_service", "news_commentary", "community", "other"}
AUDIENCE_AGE_KEYS = {"under_18", "18_24", "25_34", "35_44", "45_54", "55_64", "65_plus"}


@dataclass(frozen=True)
class AccountContextFields:
    account_theme: str = ""
    about_this_account: str = ""
    target_audience: str = ""
    tone_keys: tuple[str, ...] = ()
    tone_other: str = ""
    content_formats: tuple[str, ...] = ()
    caption_language: str = "auto"
    primary_category: str = ""
    primary_category_other: str = ""
    audience_age_ranges: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not any((value.strip() if isinstance(value, str) else bool(value)) for value in asdict(self).values())


@dataclass(frozen=True)
class ContextReference:
    text: str
    relevance: Literal["none", "low", "related"]
    used: bool


def _clean(value: object, limit: int) -> str:
    return re.sub(r"\r\n?", "\n", str(value or "")).strip()[:limit]


def normalize_context_fields(value: AccountContextFields) -> AccountContextFields:
    tones = tuple(dict.fromkeys(key for key in value.tone_keys if key in TONE_KEYS))[:3]
    formats = tuple(dict.fromkeys(key for key in value.content_formats if key in CONTENT_FORMAT_KEYS))
    ages = tuple(dict.fromkeys(key for key in value.audience_age_ranges if key in AUDIENCE_AGE_KEYS))
    return AccountContextFields(
        account_theme=_clean(value.account_theme, 300),
        about_this_account=_clean(value.about_this_account, 3000),
        target_audience=_clean(value.target_audience, 2000),
        tone_keys=tones,
        tone_other=_clean(value.tone_other, 120) if "other" in tones else "",
        content_formats=formats,
        caption_language=value.caption_language if value.caption_language in CAPTION_LANGUAGE_KEYS else "auto",
        primary_category=value.primary_category if value.primary_category in PRIMARY_CATEGORY_KEYS else "",
        primary_category_other=_clean(value.primary_category_other, 120) if value.primary_category == "other" else "",
        audience_age_ranges=ages,
    )


def serialize_account_context(value: AccountContextFields) -> str:
    normalized = normalize_context_fields(value)
    if normalized.is_empty():
        return ""
    payload = {"version": CONTEXT_STORAGE_VERSION, **asdict(normalized)}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > MAX_SERIALIZED_CONTEXT_LENGTH:
        raise ValueError("Account context is too long.")
    return encoded


def deserialize_account_context(raw: str | None) -> AccountContextFields:
    value = (raw or "").strip()
    if not value:
        return AccountContextFields()
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return AccountContextFields(about_this_account=_clean(value, 3000))
    if not isinstance(payload, dict):
        return AccountContextFields(about_this_account=_clean(value, 3000))
    return normalize_context_fields(AccountContextFields(
        account_theme=payload.get("account_theme", ""),
        about_this_account=payload.get("about_this_account", payload.get("account_context", "")),
        target_audience=payload.get("target_audience", ""),
        tone_keys=tuple(payload.get("tone_keys") or ()),
        tone_other=payload.get("tone_other", ""),
        content_formats=tuple(payload.get("content_formats") or ()),
        caption_language=payload.get("caption_language", "auto"),
        primary_category=payload.get("primary_category", ""),
        primary_category_other=payload.get("primary_category_other", ""),
        audience_age_ranges=tuple(payload.get("audience_age_ranges") or ()),
    ))


def context_as_dict(raw: str | None) -> dict[str, object]:
    return asdict(deserialize_account_context(raw))


def _keywords(value: str) -> set[str]:
    return {
        word.lower()
        for word in _WORDS.findall(value)
        if word.lower() not in _STOP_WORDS and not word.isdigit()
    }


def _format_sections(fields: AccountContextFields, mode: Literal["creation", "analysis"]) -> str:
    sections: list[tuple[str, str]] = [
        ("Account Theme", fields.account_theme),
        ("About This Account", fields.about_this_account),
        ("Target Audience", fields.target_audience),
    ]
    if mode == "creation":
        sections.extend([
            ("Tone", ", ".join(fields.tone_keys) + (f": {fields.tone_other}" if fields.tone_other else "")),
            ("Content Formats", ", ".join(fields.content_formats)),
            ("Caption Language", fields.caption_language),
            ("Primary Category", fields.primary_category_other or fields.primary_category),
            ("Audience Age (user supplied)", ", ".join(fields.audience_age_ranges)),
        ])
    return "\n".join(f"{label}: {value}" for label, value in sections if value.strip())


def context_reference_for_content(
    raw: str | None,
    content: str,
    *,
    mode: Literal["creation", "analysis"],
) -> ContextReference:
    """Use context only as interpretation guidance, never as performance evidence."""
    fields = deserialize_account_context(raw)
    if fields.is_empty():
        return ContextReference(text="", relevance="none", used=False)

    theme_text = "\n".join((fields.account_theme, fields.about_this_account, fields.target_audience))
    theme_keywords = _keywords(theme_text)
    content_keywords = _keywords(content)
    related = not theme_keywords or bool(theme_keywords & content_keywords)
    if related:
        text = _format_sections(fields, mode)
        return ContextReference(text=text, relevance="related", used=bool(text))
    return ContextReference(text="", relevance="none", used=False)


def suggest_context_from_posts(posts: list[dict[str, object]]) -> dict[str, object]:
    """Return an editable draft derived only from recent captions and formats."""
    recent = posts[:10]
    captions = [str(item.get("caption") or "") for item in recent]
    cleaned_captions = [re.sub(r"(?<!\w)[#@][\w'-]+", " ", caption) for caption in captions]
    formats = []
    for item in recent:
        media_type = str(item.get("media_type") or "").upper()
        key = "reel_video" if media_type in {"VIDEO", "REELS"} else "carousel" if media_type == "CAROUSEL_ALBUM" else "image" if media_type == "IMAGE" else ""
        if key and key not in formats:
            formats.append(key)
    combined = " ".join(cleaned_captions)
    if re.search(r"[\u3040-\u30ff]", combined):
        language = "japanese"
    elif re.search(r"[\uac00-\ud7af]", combined):
        language = "korean"
    elif re.search(r"[\u4e00-\u9fff]", combined):
        language = "traditional_chinese" if re.search(r"[體臺灣這個與為會後]", combined) else "simplified_chinese"
    else:
        language = "english" if re.search(r"[A-Za-z]", combined) else "auto"
    keywords = Counter(word.lower() for caption in cleaned_captions for word in _WORDS.findall(caption)
                       if word.lower() not in _STOP_WORDS and len(word) > 2)
    repeated = [word for word, count in keywords.most_common(5) if count >= 2]
    tones = []
    if any("?" in caption for caption in captions):
        tones.append("conversational")
    if any(re.search(r"[!！]|[\U0001F300-\U0001FAFF]", caption) for caption in captions):
        tones.append("playful")
    purpose_cues = {
        "education": ("how", "tutorial", "tips", "guide", "lesson", "steps"),
        "entertainment": ("fun", "comedy", "joke", "skit"),
        "inspiration": ("inspire", "inspiration", "motivation", "motivational"),
        "personal": ("my day", "my story", "personal update"),
        "product_service": ("buy", "shop", "order", "product", "service", "book now"),
        "news_commentary": ("news", "commentary", "opinion", "latest update"),
        "community": ("community", "members", "together"),
    }
    lowered = combined.lower()
    category_scores = {category: sum(lowered.count(cue) for cue in cues) for category, cues in purpose_cues.items()}
    primary_category = max(category_scores, key=category_scores.get) if category_scores and max(category_scores.values()) > 0 else ""
    return {
        "draft": {
            "account_theme": f"Recent captions often mention: {', '.join(repeated)}." if repeated else "",
            "about_this_account": f"Recent posts use {', '.join(formats)} formats." if formats else "",
            "target_audience": "", "tone_keys": tones[:3], "tone_other": "",
            "content_formats": formats, "caption_language": language,
            "primary_category": primary_category, "primary_category_other": "", "audience_age_ranges": [],
        },
        "source": {"posts_considered": len(recent), "captions_considered": len(captions),
                   "covers_available": sum(bool(item.get("thumbnail_url")) for item in recent)},
        "not_inferred": ["audience demographics", "sensitive traits"],
    }


def preview_context(value: AccountContextFields) -> dict[str, object]:
    fields = normalize_context_fields(value)
    language = fields.caption_language.replace("_", " ")
    tone = ", ".join(fields.tone_keys) or "neutral"
    templates = {
        "traditional_chinese": "這是一則簡單、清楚的近況分享。",
        "simplified_chinese": "这是一则简单、清楚的近况分享。",
        "japanese": "シンプルで分かりやすい近況のお知らせです。",
        "korean": "간단하고 명확한 소식을 전합니다.",
        "spanish": "Una actualización sencilla y clara.",
    }
    sample = templates.get(fields.caption_language, f"A simple update written in a {tone} tone.")
    return {"label": "Sample only", "caption": sample, "language": language,
            "stored": False, "used_for": ["caption generation", "Create prefill"],
            "not_used_for": ["performance facts", "metric comparisons"]}
