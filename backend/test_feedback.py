from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import backend.services.feedback as feedback

NOW = datetime(2026, 11, 25, tzinfo=UTC)


def _snapshot(identifier: str, *, views: int, comments: int, saves: int = 10, shares: int = 10):
    return SimpleNamespace(
        id=identifier,
        captured_at=NOW,
        views=views,
        reach=1000,
        saves=saves,
        shares=shares,
        comments=comments,
        engagement_rate=1,
        average_watch_time_ms=None,
    )


def _item(identifier: str, snapshot):
    return {
        "tracking": SimpleNamespace(id=identifier),
        "media": SimpleNamespace(media_type="IMAGE", published_at=NOW - timedelta(days=10)),
        "snapshots": [snapshot],
        "latest": snapshot,
    }


def test_high_views_low_comments_produces_named_outlier_diagnosis():
    selected = _item("selected", _snapshot("selected-snapshot", views=1000, comments=1))
    peers = [_item(f"peer-{index}", _snapshot(f"peer-snapshot-{index}", views=100, comments=10)) for index in range(6)]

    facts = feedback.build_feedback_facts(selected, [selected, *peers], {"usual_ranges": []}, now=NOW)
    outlier = next(fact for fact in facts if fact["id"] == "interaction_outlier")
    output = feedback.template_output(facts)

    assert outlier["value"] == "views_high_comments_low"
    assert output["diagnosis"] == "Views are high relative to same-format peers while Comments are low."
    assert {item["fact_id"] for item in output["evidence"]} == {
        "interaction_views",
        "interaction_comments",
    }


def test_structured_output_contains_concrete_experiment_and_measure():
    facts = [
        {
            "id": "growth_stage",
            "type": "growth_stage",
            "value": "still_growing",
            "evidence": {"peer_count": 6},
            "qualifies": True,
        }
    ]

    output = feedback.template_output(facts)

    assert "Experiment:" in output["experiment"]
    assert "Measure:" in output["measure"]
    assert feedback.validate_output(output, facts)


def test_validator_rejects_numbers_not_present_in_fact_payload():
    facts = [
        {
            "id": "interaction_views",
            "type": "interaction_signal",
            "value": "higher",
            "evidence": {"signal": "views", "percentile": 95.0, "peer_count": 6},
            "qualifies": True,
        }
    ]
    payload = {
        "diagnosis": "Views were high at percentile 95.",
        "evidence": [{"fact_id": "interaction_views", "statement": "Views were high at percentile 95."}],
        "hypothesis": "Hypothesis: the post may have attracted more viewing, but the facts do not establish a cause.",
        "experiment": "Experiment: change one presentation element in the next comparable post.",
        "measure": "Measure: compare the views percentile on the next comparable post.",
        "do_not_change": "Do not change multiple elements at once.",
    }
    assert feedback.validate_output(payload, facts)

    payload["diagnosis"] = "Views were high at percentile 97."
    payload["evidence"][0]["statement"] = payload["diagnosis"]
    assert not feedback.validate_output(payload, facts)
