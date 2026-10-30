from typing import Dict, List


def generate_content_insights(input_data: Dict, prediction: Dict) -> Dict:
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendations: List[str] = []

    platform = input_data.get("platform", "")
    content_type = input_data.get("contentType", "")
    caption_length = input_data.get("captionLength", 0)
    views = prediction.get("views", 0)
    viral_score = prediction.get("viral_score", 0)
    engagement = prediction.get("engagement", 0)

    if viral_score >= 75:
        strengths.append("The concept has strong viral potential and should be easy for viewers to share quickly.")
    elif viral_score < 45:
        weaknesses.append("The idea does not yet look strong enough to trigger wide sharing.")
        recommendations.append("Make the opening hook clearer in the first one to two seconds.")

    if engagement >= 6:
        strengths.append("The predicted engagement is healthy, which suggests the format can hold audience interest.")
    elif engagement < 3:
        weaknesses.append("The content may not prompt enough reactions, comments, or saves.")

    if content_type in ["Reel", "Short"]:
        strengths.append("Short-form video usually has better discovery potential on modern social platforms.")
    elif content_type in ["Post", "Story"]:
        weaknesses.append("This format may be less discoverable than short-form video.")
        recommendations.append("Repurpose this idea into a short-form video variation to increase reach.")

    if 80 <= caption_length <= 180:
        strengths.append("The caption length is balanced and likely easy to consume.")
    elif caption_length < 40:
        weaknesses.append("The caption may be too short to provide enough context.")
        recommendations.append("Expand the caption so the main idea has enough context.")
    elif caption_length > 250:
        weaknesses.append("The caption may be longer than needed for quick social consumption.")
        recommendations.append("Tighten the caption so the main value is obvious at a glance.")

    if views >= 10000:
        analysis = (
            f"This {content_type.lower()} looks promising for {platform}. The expected reach is strong, "
            "and the current setup suggests a solid match between format, timing, and audience behavior."
        )
    elif views >= 3000:
        analysis = (
            f"This {content_type.lower()} has moderate potential on {platform}. The foundation is workable, "
            "but improving the hook, timing, or engagement strategy could lift performance."
        )
    else:
        analysis = (
            f"This {content_type.lower()} may struggle to break through on {platform} in its current form. "
            "It likely needs a sharper hook and a more compelling audience payoff."
        )

    if not weaknesses:
        weaknesses.append("There are no major warning signs, but testing multiple variants could still improve results.")

    if not recommendations:
        recommendations.append("Test two variations of the hook or caption to identify the strongest performer.")

    return {
        "analysis": analysis,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
    }
