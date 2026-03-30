import re
from typing import Any


BENEFIT_KEYWORDS = {
    "how",
    "why",
    "tips",
    "guide",
    "learn",
    "save",
    "avoid",
    "mistake",
    "secret",
    "template",
}


def normalize_hashtags(raw_hashtags: list[str] | None) -> list[str]:
    if not raw_hashtags:
        return []

    normalized: list[str] = []
    for tag in raw_hashtags:
        cleaned = tag.strip()
        if not cleaned:
            continue
        normalized.append(cleaned if cleaned.startswith("#") else f"#{cleaned}")
    return normalized


def token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z]{3,}", text.lower()))


def build_content_audit(
    *,
    platform: str,
    content_type: str,
    caption: str,
    hashtags: list[str],
    metrics: dict[str, Any],
    prediction_signal: dict[str, Any] | None,
) -> dict[str, Any]:
    what_is_working: list[str] = []
    underperforming: list[str] = []
    likely_cause: list[str] = []
    recommended_changes: list[str] = []
    confidence_notes: list[str] = []

    views = metrics.get("views")
    likes = metrics.get("likes")
    comments = metrics.get("comments")
    shares = metrics.get("shares")
    retention_rate = metrics.get("retention_rate")
    average_watch_time = metrics.get("average_watch_time")

    caption_length = len(caption.strip())
    hashtag_count = len(hashtags)

    if caption_length == 0:
        underperforming.append("No caption text was provided, so value communication is limited.")
        likely_cause.append("Without caption context, the post may lack a clear benefit statement or framing.")
        recommended_changes.append("Add a caption that explains the payoff, angle, or audience value in the opening line.")
    elif caption_length < 40:
        underperforming.append("Caption is too short to clearly communicate the value proposition.")
        likely_cause.append("The post likely asks the audience to infer too much from minimal text.")
        recommended_changes.append("Expand the caption with a direct benefit statement or concrete takeaway.")
    elif 80 <= caption_length <= 180:
        what_is_working.append("Caption length is strong enough to communicate context without feeling overloaded.")

    caption_tokens = token_set(caption)
    hashtag_tokens = {tag.lower().lstrip("#") for tag in hashtags}

    if hashtag_count == 0:
        underperforming.append("No hashtags were provided, so discovery support is limited.")
        likely_cause.append("The post has no additional topical labels to help discovery outside existing audience reach.")
        recommended_changes.append("Add a small set of relevant topic hashtags tied to the actual content theme.")
    elif caption_tokens and hashtag_tokens and not any(token in caption_tokens for token in hashtag_tokens):
        underperforming.append("Hashtags do not appear to align with the visible caption theme.")
        likely_cause.append("The tag set may be generic or disconnected from the actual subject matter of the post.")
        recommended_changes.append("Replace broad hashtags with tags that repeat the real topic, audience, or promised outcome.")
    else:
        what_is_working.append("Hashtags appear aligned enough to support the post theme.")

    if content_type in {"Post", "Story"}:
        underperforming.append("This content type is less discoverable than short-form video on most current platforms.")
        likely_cause.append("The format may rely more on existing audience attention than algorithmic discovery.")
        recommended_changes.append("Consider repackaging the idea into a short-form video version for broader discovery.")

    if views and comments is not None and views > 0:
        comment_rate = comments / views
        if comment_rate < 0.005:
            underperforming.append("Comments are low relative to views, suggesting weak discussion trigger.")
            likely_cause.append("The post may inform viewers, but it does not give them a reason to respond.")
            recommended_changes.append("Add a stronger opinion prompt, question, or explicit request for audience response.")
        else:
            what_is_working.append("Comments are healthy enough to suggest the post invites conversation.")

    if views and likes is not None and views > 0:
        like_rate = likes / views
        if like_rate < 0.02:
            underperforming.append("Likes are low relative to views, suggesting weak immediate resonance.")
            likely_cause.append("The post may not communicate its payoff quickly enough to trigger lightweight positive feedback.")
            recommended_changes.append("Clarify the post value earlier and make the first screen or frame more legible.")
        else:
            what_is_working.append("Like rate suggests the post is resonating with at least part of the audience.")

    if views and shares is not None and views > 0:
        share_rate = shares / views
        if share_rate < 0.001:
            underperforming.append("Shares are low relative to views, so the post may not feel share-worthy yet.")
            likely_cause.append("The content may be useful or interesting, but not framed as something others need to pass on.")
            recommended_changes.append("Strengthen the utility, novelty, or emotional payoff so viewers feel a reason to share.")

    if retention_rate is None and average_watch_time is None:
        confidence_notes.append("Hook diagnosis is low-confidence because no retention or watch-time data was provided.")
    else:
        if retention_rate is not None and retention_rate < 0.35:
            underperforming.append("Retention appears low, which suggests viewers are dropping before the core payoff arrives.")
            likely_cause.append("The opening may not establish relevance quickly enough for the audience.")
            recommended_changes.append("Move the promised result or strongest claim earlier in the post.")
        elif retention_rate is not None:
            what_is_working.append("Retention data suggests the opening is holding attention reasonably well.")

    if caption and not any(keyword in caption.lower() for keyword in BENEFIT_KEYWORDS):
        underperforming.append("The caption likely lacks a clear payoff statement in the opening line.")
        likely_cause.append("The audience may not immediately understand what they gain from reading or watching.")
        recommended_changes.append("Lead with the benefit, outcome, or problem solved before supporting details.")

    if prediction_signal:
        confidence_notes.append(
            "A predictive model signal is included as a secondary input, but the audit prioritizes real provided metrics."
        )

    if not what_is_working:
        what_is_working.append("Platform and content context were identified, but more live metrics would improve confidence.")

    if not underperforming:
        underperforming.append("No major underperformance signals were detected from the inputs provided.")

    if not likely_cause:
        likely_cause.append("The available inputs do not expose a single dominant failure point.")

    if not recommended_changes:
        recommended_changes.append("Collect more real metrics such as comments, shares, or retention for a higher-confidence audit.")

    return {
        "what_is_working": what_is_working,
        "underperforming": underperforming,
        "likely_cause": likely_cause,
        "recommended_changes": recommended_changes,
        "confidence_notes": confidence_notes,
    }
