"""Structured, account-scoped creator context with conservative relevance checks."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Literal


CONTEXT_STORAGE_VERSION = 1
MAX_SERIALIZED_CONTEXT_LENGTH = 12000
_WORDS = re.compile(r"[^\W_][\w'-]{1,}", re.UNICODE)
_STOP_WORDS = {
    "about", "account", "audience", "brand", "content", "creator", "family",
    "focused", "friendly", "guidance", "people", "social", "this", "with",
    "when", "from", "that", "their", "through", "into", "your", "the", "and",
    "for", "are", "who", "enjoy", "based", "using", "make", "more",
}


@dataclass(frozen=True)
class AccountContextFields:
    account_theme: str = ""
    about_this_account: str = ""
    target_audience: str = ""
    brand_voice: str = ""
    analysis_guidance: str = ""
    creation_guidance: str = ""

    def is_empty(self) -> bool:
        return not any(value.strip() for value in asdict(self).values())


@dataclass(frozen=True)
class ContextReference:
    text: str
    relevance: Literal["none", "low", "related"]
    used: bool


def _clean(value: object, limit: int) -> str:
    return re.sub(r"\r\n?", "\n", str(value or "")).strip()[:limit]


def normalize_context_fields(value: AccountContextFields) -> AccountContextFields:
    return AccountContextFields(
        account_theme=_clean(value.account_theme, 300),
        about_this_account=_clean(value.about_this_account, 3000),
        target_audience=_clean(value.target_audience, 2000),
        brand_voice=_clean(value.brand_voice, 1000),
        analysis_guidance=_clean(value.analysis_guidance, 2500),
        creation_guidance=_clean(value.creation_guidance, 2500),
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
        brand_voice=payload.get("brand_voice", ""),
        analysis_guidance=payload.get("analysis_guidance", ""),
        creation_guidance=payload.get("creation_guidance", ""),
    ))


def context_as_dict(raw: str | None) -> dict[str, str]:
    return asdict(deserialize_account_context(raw))


def _keywords(value: str) -> set[str]:
    return {
        word.lower()
        for word in _WORDS.findall(value)
        if word.lower() not in _STOP_WORDS and not word.isdigit()
    }


def _format_sections(fields: AccountContextFields, *, mode: Literal["creation", "analysis"], reduced: bool) -> str:
    sections: list[tuple[str, str]] = []
    if not reduced:
        sections.extend((
            ("Account Theme", fields.account_theme),
            ("About This Account", fields.about_this_account),
            ("Target Audience", fields.target_audience),
        ))
    sections.append(("Brand Voice", fields.brand_voice))
    if not reduced:
        sections.append(("Creation Guidance" if mode == "creation" else "Analysis Guidance",
                         fields.creation_guidance if mode == "creation" else fields.analysis_guidance))
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
        text = _format_sections(fields, mode=mode, reduced=False)
        return ContextReference(text=text, relevance="related", used=bool(text))

    if mode == "creation":
        text = _format_sections(fields, mode=mode, reduced=True)
        return ContextReference(text=text, relevance="low", used=bool(text))
    return ContextReference(text="", relevance="none", used=False)

