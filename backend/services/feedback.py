"""Evidence-first Summary feedback with validated provider fallbacks."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol
from uuid import uuid4

from sqlalchemy import delete

from backend.services.gemini import GeminiConfigurationError, GeminiUpstreamError, generate_gemini_content
from backend.storage.content_repository import get_content_repository
from backend.storage.database import session_factory
from backend.storage.models import InsightTextCache
from backend.storage.sql_models import AIGenerationLogRecord

LOGGER = logging.getLogger("postbridge.feedback")
PROMPT_VERSION = "summary-facts-v1"
MIN_PEERS = 6
PERCENTILE_RANGE_AT = 15
PACE_MOST_FRACTION = .75
PACE_HALF_FRACTION = .40
CAUSAL = re.compile(r"\b(because|due to|caused|thanks to|led to)\b", re.I)
PREDICTIVE = re.compile(r"\b(will|going to|likely to|guarantee|boost)\b", re.I)
ADVICE = re.compile(r"\b(try|consider|could|might|option|recommend|suggest|reuse|focus|keep|make)\b", re.I)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _format(media_type: str) -> str:
    return "video" if str(media_type).upper() in {"VIDEO", "REELS"} else str(media_type or "IMAGE").lower()


def _mature(media: Any, now: datetime) -> bool:
    days = 14 if _format(media.media_type) == "video" else 7
    return now - _aware(media.published_at) >= timedelta(days=days)


def _value(snapshot: Any, name: str) -> float | None:
    value = getattr(snapshot, name, None)
    return float(value) if value is not None else None


def _rate(snapshot: Any, names: tuple[str, ...]) -> float | None:
    reach = _value(snapshot, "reach")
    values = [_value(snapshot, name) for name in names]
    present = [value for value in values if value is not None]
    return sum(present) / reach if reach and present else None


def _percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * proportion
    lower = int(position); upper = min(len(ordered) - 1, lower + 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _range(values: list[float]) -> tuple[float, float]:
    return (_percentile(values, .10), _percentile(values, .90)) if len(values) >= PERCENTILE_RANGE_AT else (min(values), max(values))


def _fact(fact_id: str, fact_type: str, evidence: dict[str, Any], value: str, qualifies: bool) -> dict[str, Any]:
    return {"id": fact_id, "type": fact_type, "evidence": evidence, "value": value, "qualifies": qualifies}


def build_feedback_facts(selected: dict[str, Any], items: list[dict[str, Any]], analysis: dict[str, Any], now: datetime | None = None) -> list[dict[str, Any]]:
    """Pure fact extraction; missing evidence always produces a non-qualifying fact."""
    current = _aware(now or datetime.now(timezone.utc))
    media = selected["media"]
    snapshots = sorted(selected.get("snapshots") or [], key=lambda row: _aware(row.captured_at))
    if selected.get("latest") is not None and all(row.id != selected["latest"].id for row in snapshots):
        snapshots.append(selected["latest"]); snapshots.sort(key=lambda row: _aware(row.captured_at))

    facts: list[dict[str, Any]] = []
    spaced = next(((a, b) for a in snapshots for b in reversed(snapshots)
                   if _aware(b.captured_at) - _aware(a.captured_at) >= timedelta(hours=6)), None)
    growth_value = ""
    if spaced:
        first, last = spaced
        first_value = _value(first, "views") or _value(first, "reach")
        last_value = _value(last, "views") or _value(last, "reach")
        if first_value is not None and last_value is not None:
            growth_value = "levelled_off" if _mature(media, current) else "still_growing"
    facts.append(_fact("growth_stage", "growth_stage", {
        "snapshot_ids": [spaced[0].id, spaced[1].id] if spaced else [], "minimum_spacing_hours": 6,
    }, growth_value, bool(growth_value)))

    early = [row for row in snapshots if _aware(row.captured_at) <= _aware(media.published_at) + timedelta(hours=36)]
    pace_value = ""
    if early:
        first = early[0]
        later = [row for row in snapshots if _aware(row.captured_at) > _aware(first.captured_at)]
        first_views = _value(first, "views"); latest_views = _value(snapshots[-1], "views") if snapshots else None
        if len(later) >= 2 and first_views is not None and latest_views and latest_views > 0:
            share = first_views / latest_views
            pace_value = "most" if share >= PACE_MOST_FRACTION else "about_half" if share >= PACE_HALF_FRACTION else "less_than_half"
    facts.append(_fact("accumulation_pace", "accumulation_pace", {
        "first_snapshot_id": early[0].id if early else None,
        "later_snapshot_ids": [row.id for row in snapshots[1:]] if early else [],
    }, pace_value, bool(pace_value)))

    peers = []
    for item in items:
        if item.get("tracking") is None or item["tracking"].id == selected["tracking"].id or item.get("media") is None:
            continue
        peer_snaps = list(item.get("snapshots") or [])
        if _format(item["media"].media_type) == _format(media.media_type) and _mature(item["media"], current) and peer_snaps:
            peers.append((item, max(peer_snaps, key=lambda row: _aware(row.captured_at))))
    latest = snapshots[-1] if snapshots else None

    mix = _rate(latest, ("saves", "shares", "comments")) if latest else None
    peer_mix = [value for _, snap in peers if (value := _rate(snap, ("saves", "shares", "comments"))) is not None]
    mix_value = ""
    if mix is not None and len(peer_mix) >= MIN_PEERS:
        low, high = _range(peer_mix); mix_value = "higher" if mix > high else "lower" if mix < low else "usual"
    facts.append(_fact("interaction_mix", "interaction_mix", {"peer_count": len(peer_mix), "post_snapshot_id": getattr(latest, "id", None)}, mix_value,
                       mix_value in {"higher", "lower"}))

    reach = _value(latest, "reach") if latest else None
    engagement = _value(latest, "engagement_rate") if latest else None
    peer_reach = [_value(snap, "reach") for _, snap in peers if _value(snap, "reach") is not None]
    peer_engagement = [_value(snap, "engagement_rate") for _, snap in peers if _value(snap, "engagement_rate") is not None]
    relation_value = ""
    if reach is not None and engagement is not None and len(peer_reach) >= MIN_PEERS and len(peer_engagement) >= MIN_PEERS:
        rlow, rhigh = _range(peer_reach); elow, ehigh = _range(peer_engagement)
        reach_direction = "higher" if reach > rhigh else "lower" if reach < rlow else "usual"
        if reach_direction != "usual" and elow <= engagement <= ehigh:
            relation_value = f"{reach_direction}_reach_usual_engagement"
    facts.append(_fact("reach_interaction_relation", "reach_interaction_relation", {
        "reach_peer_count": len(peer_reach), "engagement_peer_count": len(peer_engagement),
        "post_snapshot_id": getattr(latest, "id", None),
    }, relation_value, bool(relation_value)))

    watch = _value(latest, "average_watch_time_ms") if latest else None
    peer_watch = [_value(snap, "average_watch_time_ms") for _, snap in peers if _value(snap, "average_watch_time_ms") is not None]
    watch_value = ""
    if watch is not None and len(peer_watch) >= MIN_PEERS:
        low, high = _range(peer_watch); watch_value = "longer" if watch > high else "shorter" if watch < low else "usual"
    facts.append(_fact("watch_time", "watch_time", {"peer_count": len(peer_watch), "post_snapshot_id": getattr(latest, "id", None)}, watch_value,
                       watch_value in {"longer", "shorter"}))

    # Interaction mix is redundant when the page already exposes all of its
    # component comparisons. Other facts describe relationships or time paths.
    visible = {row.get("metric") for row in analysis.get("usual_ranges", [])}
    if {"saves", "shares", "comments"} <= visible:
        for fact in facts:
            if fact["type"] == "interaction_mix":
                fact["qualifies"] = False; fact["evidence"]["novelty_dropped"] = True
    return facts


TEMPLATES: dict[tuple[str, str], tuple[str, str]] = {
    ("growth_stage", "still_growing"): ("This post was still accumulating attention across the observed checkpoints.", "observation"),
    ("growth_stage", "levelled_off"): ("This post had levelled off across the observed checkpoints.", "observation"),
    ("accumulation_pace", "most"): ("Most of the observed attention had accumulated early.", "observation"),
    ("accumulation_pace", "about_half"): ("Attention accumulated across both the early and later checkpoints.", "observation"),
    ("accumulation_pace", "less_than_half"): ("More of the observed attention arrived after the earliest checkpoint.", "observation"),
    ("interaction_mix", "higher"): ("Interaction actions were unusually prominent for the reach this post received.", "observation"),
    ("interaction_mix", "lower"): ("Interaction actions were unusually limited for the reach this post received.", "observation"),
    ("reach_interaction_relation", "higher_reach_usual_engagement"): ("Reach stood apart while the interaction rate remained typical for this format.", "observation"),
    ("reach_interaction_relation", "lower_reach_usual_engagement"): ("Reach was unusually limited while the interaction rate remained typical for this format.", "observation"),
    ("watch_time", "longer"): ("Average viewing time was unusually strong for this format.", "observation"),
    ("watch_time", "shorter"): ("Average viewing time was unusually limited for this format.", "observation"),
}


def template_output(facts: list[dict[str, Any]]) -> dict[str, Any]:
    sentences = []
    for fact in facts:
        template = TEMPLATES.get((fact["type"], fact.get("value", ""))) if fact.get("qualifies") else None
        if template:
            sentences.append({"text": template[0], "kind": template[1], "fact_ids": [fact["id"]]})
        if len(sentences) == 3:
            break
    return {"sentences": sentences}


def validate_output(payload: Any, facts: list[dict[str, Any]]) -> bool:
    if not isinstance(payload, dict) or not isinstance(payload.get("sentences"), list) or len(payload["sentences"]) > 3:
        return False
    valid_ids = {fact["id"] for fact in facts if fact.get("qualifies")}
    suggestions = 0
    for sentence in payload["sentences"]:
        if not isinstance(sentence, dict) or sentence.get("kind") not in {"observation", "suggestion"}:
            return False
        text = sentence.get("text"); ids = sentence.get("fact_ids")
        if not isinstance(text, str) or not text.strip() or re.search(r"\d", text) or CAUSAL.search(text) or PREDICTIVE.search(text):
            return False
        if not isinstance(ids, list) or not ids or any(value not in valid_ids for value in ids):
            return False
        if sentence["kind"] == "suggestion":
            suggestions += 1
            if not ADVICE.search(text): return False
        elif ADVICE.search(text):
            return False
    return suggestions <= 1


class FeedbackProvider(Protocol):
    name: str
    model: str
    def generate(self, facts: list[dict[str, Any]]) -> dict[str, Any]: ...


@dataclass
class GeminiFeedbackProvider:
    generator: Callable[..., str] = generate_gemini_content
    name: str = "gemini"

    @property
    def model(self) -> str:
        return os.getenv("GEMINI_MODEL", "unconfigured")

    def generate(self, facts: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = (
            "Return JSON only: {\"sentences\":[{\"text\":string,\"kind\":\"observation|suggestion\",\"fact_ids\":[string]}]}. "
            "Use at most three sentences and at most one suggestion. Cite only supplied fact ids. Use plain language. "
            "Do not restate values, ranks, ranges, dates, or titles. Make no causal, predictive, promise, visual, or creative claim. "
            "Give no hashtag, call-to-action, or engagement-bait advice. A suggestion must follow directly from a fact, be optional, and promise nothing.\n"
            f"FACTS_JSON={json.dumps(facts, separators=(',', ':'))}"
        )
        timeout = max(1, int(os.getenv("FEEDBACK_REQUEST_TIMEOUT_SECONDS", "12")))
        last_error: Exception | None = None
        for attempt in range(2):
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(self.generator, prompt)
            try:
                raw = future.result(timeout=timeout)
                executor.shutdown(wait=False, cancel_futures=True)
                return json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
            except (FutureTimeout, json.JSONDecodeError, GeminiConfigurationError, GeminiUpstreamError) as exc:
                last_error = exc; future.cancel(); executor.shutdown(wait=False, cancel_futures=True)
                if attempt == 0 and not isinstance(exc, GeminiConfigurationError):
                    continue
                raise GeminiUpstreamError("Feedback generation failed.") from None
        raise GeminiUpstreamError("Feedback generation failed.") from last_error


@dataclass
class TrainedFeedbackProvider:
    name: str = "trained"
    model: str = "creator-linear-regression-views"

    @property
    def healthy(self) -> bool:
        # The only repository artifact is a numeric views predictor trained on
        # synthetic rows. It fails the product acceptance check by design.
        return False

    def generate(self, facts: list[dict[str, Any]]) -> dict[str, Any]:
        del facts
        raise RuntimeError("The trained numeric predictor is not a feedback provider.")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _selection() -> tuple[list[FeedbackProvider], str]:
    configured = os.getenv("FEEDBACK_PROVIDER", "auto").strip().lower()
    trained = TrainedFeedbackProvider(); gemini = GeminiFeedbackProvider()
    trained_enabled = trained.healthy and os.getenv("FEEDBACK_TRAINED_ENABLED", "false").lower() == "true"
    if configured == "trained" and trained_enabled: providers: list[FeedbackProvider] = [trained, gemini]
    elif configured == "trained":
        LOGGER.warning("feedback_provider_disabled provider=trained reason=numeric_predictor_ineligible")
        providers = [gemini]
    elif configured == "gemini": providers = [gemini]
    else: providers = ([trained] if trained_enabled else []) + [gemini]
    signature = f"{configured}:{','.join(f'{p.name}/{p.model}' for p in providers)}"
    LOGGER.info("feedback_provider_selection configured=%s chain=%s", configured, ",".join(provider.name for provider in providers))
    return providers, signature


def _log(tracked_post_id: str, provider: str, model: str, input_hash: str, status: str,
         latency_ms: int | None, raw: str | None) -> None:
    if not get_content_repository().persistent:
        return
    now = datetime.now(timezone.utc)
    with session_factory().begin() as session:
        session.add(AIGenerationLogRecord(
            id=str(uuid4()), generator="summary", tracked_post_id=tracked_post_id,
            provider=provider, model=model, prompt_version=PROMPT_VERSION,
            input_hash=input_hash, status=status, latency_ms=latency_ms,
            token_usage=None, raw_response=(raw or "")[:4000] or None, created_at=now,
        ))
        session.execute(delete(AIGenerationLogRecord).where(AIGenerationLogRecord.created_at < now - timedelta(days=30)))


def generate_summary(user_id: str, tracked_post_id: str, facts: list[dict[str, Any]]) -> str | None:
    qualifying = [fact for fact in facts if fact.get("qualifies")]
    providers, signature = _selection()
    input_hash = _hash({"facts": facts, "selection": signature, "prompt_version": PROMPT_VERSION})
    repository = get_content_repository(); key = f"summary:{tracked_post_id}"
    existing = repository.get_text_cache(user_id, key)
    if existing and existing.input_hash == input_hash:
        return existing.text or None
    if not qualifying:
        _log(tracked_post_id, "none", "none", input_hash, "empty", 0, None)
        now = datetime.now(timezone.utc)
        repository.upsert_text_cache(InsightTextCache(
            id=existing.id if existing else str(uuid4()), user_id=user_id, tracked_post_id=tracked_post_id,
            cache_key=key, input_hash=input_hash, text="", model_name="none", provider="none",
            prompt_version=PROMPT_VERSION, facts_json=facts,
            created_at=existing.created_at if existing else now, updated_at=now,
        ))
        return None

    payload = None; chosen = "template"; model = "deterministic-v1"
    for provider in providers:
        started = time.monotonic(); raw = None
        try:
            candidate = provider.generate(qualifying); raw = json.dumps(candidate, separators=(",", ":"))
            valid = validate_output(candidate, qualifying)
            _log(tracked_post_id, provider.name, provider.model, input_hash, "ok" if valid else "invalid",
                 int((time.monotonic() - started) * 1000), raw)
            if valid:
                payload = candidate; chosen = provider.name; model = provider.model; break
            LOGGER.warning("feedback_provider_fallback provider=%s reason=invalid", provider.name)
        except Exception as exc:
            _log(tracked_post_id, provider.name, provider.model, input_hash, "error",
                 int((time.monotonic() - started) * 1000), type(exc).__name__)
            LOGGER.warning("feedback_provider_fallback provider=%s reason=%s", provider.name, type(exc).__name__)
    if payload is None:
        payload = template_output(qualifying)
    if not validate_output(payload, qualifying):
        return None
    text = " ".join(sentence["text"].strip() for sentence in payload["sentences"])
    now = datetime.now(timezone.utc)
    repository.upsert_text_cache(InsightTextCache(
        id=existing.id if existing else str(uuid4()), user_id=user_id, tracked_post_id=tracked_post_id,
        cache_key=key, input_hash=input_hash, text=text, model_name=model, provider=chosen,
        prompt_version=PROMPT_VERSION, facts_json=facts,
        created_at=existing.created_at if existing else now, updated_at=now,
    ))
    LOGGER.info("feedback_provider_selected tracked_post_id=%s provider=%s model=%s", tracked_post_id, chosen, model)
    return text or None


def cached_summary(user_id: str, tracked_post_id: str) -> str | None:
    item = get_content_repository().get_text_cache(user_id, f"summary:{tracked_post_id}")
    return item.text or None if item else None


def refresh_summary_for_user(user_id: str, tracked_post_id: str | None = None) -> None:
    """Generate caches only from explicit login-sync/manual-refresh call sites."""
    from backend.services.account_insights import build_post_analysis
    from backend.storage.instagram_repository import get_instagram_repository
    content = get_content_repository(); account = get_instagram_repository().get_connection(user_id)
    if not account: return
    media = {row.id: row for row in content.media_for_account(account.id)}
    items = []
    for tracked in content.tracked(user_id, active_only=False):
        snapshots = content.snapshots([tracked.media_id])
        items.append({"tracking": tracked, "media": media.get(tracked.media_id),
                      "latest": max(snapshots, key=lambda row: _aware(row.captured_at)) if snapshots else None,
                      "snapshots": snapshots})
    for selected in items:
        if selected.get("media") is None or (tracked_post_id and selected["tracking"].id != tracked_post_id): continue
        analysis = build_post_analysis(selected, items, summary=None,
            audience_comments={"state": "feature_off", "message": ""})
        facts = build_feedback_facts(selected, items, analysis)
        generate_summary(user_id, selected["tracking"].id, facts)


def summary_note(status: str) -> str | None:
    if status == "unavailable":
        return "Early-growth data isn't available for this post because it was added after its first 24 hours."
    if status == "partial":
        return "Some early-growth checkpoints are missing because tracking started late."
    return None
