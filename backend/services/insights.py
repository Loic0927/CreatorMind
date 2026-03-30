from typing import Dict, List


def generate_content_insights(input_data: Dict, prediction: Dict) -> Dict:
    strengths: List[str] = []
    weaknesses: List[str] = []
    recommendations: List[str] = []

    platform = input_data.get("platform", "")
    content_type = input_data.get("contentType", "")
    caption_length = input_data.get("captionLength", 0)
    hashtags_count = input_data.get("hashtagsCount", 0)
    posting_hour = input_data.get("postingHour", 0)

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
        recommendations.append("Add a clearer call to action such as a question, opinion prompt, or save-worthy takeaway.")

    if 17 <= posting_hour <= 21:
        strengths.append("The posting time is within a strong evening window when audience activity is often higher.")
    elif posting_hour < 8 or posting_hour > 22:
        weaknesses.append("The posting time may limit early reach because fewer users may be active.")
        recommendations.append("Test publishing between 5 PM and 9 PM for stronger initial distribution.")

    if content_type in ["Reel", "Short"]:
        strengths.append("Short-form video usually has better discovery potential on modern social platforms.")
    elif content_type in ["Post", "Story"]:
        weaknesses.append("This format may be less discoverable than short-form video.")
        recommendations.append("Repurpose this idea into a short-form video variation to increase reach.")

    if 80 <= caption_length <= 180:
        strengths.append("The caption length is balanced and likely easy to consume.")
    elif caption_length < 40:
        weaknesses.append("The caption may be too short to provide enough context or encourage action.")
        recommendations.append("Expand the caption with a clearer benefit, hook, or next step for the audience.")
    elif caption_length > 250:
        weaknesses.append("The caption may be longer than needed for quick social consumption.")
        recommendations.append("Tighten the caption so the main value is obvious at a glance.")

    if 3 <= hashtags_count <= 8:
        strengths.append("The hashtag count is focused enough to support discoverability without looking spammy.")
    elif hashtags_count == 0:
        weaknesses.append("No hashtags are included, which may reduce discoverability.")
        recommendations.append("Add a few niche-relevant hashtags that match the topic and audience.")
    elif hashtags_count > 12:
        weaknesses.append("Too many hashtags can make the post feel unfocused.")
        recommendations.append("Reduce the hashtag list to a smaller, more targeted set.")

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
