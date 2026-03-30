from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectorStatus:
    platform: str
    supported_now: bool
    status: str
    capability_note: str


def get_connector_statuses() -> list[ConnectorStatus]:
    return [
        ConnectorStatus(
            platform="Instagram",
            supported_now=False,
            status="not_connected",
            capability_note="Prepared for official Instagram Insights integration.",
        ),
        ConnectorStatus(
            platform="YouTube",
            supported_now=True,
            status="not_connected",
            capability_note="Supports public Data API audits now and OAuth connection setup for advanced YouTube Analytics access.",
        ),
        ConnectorStatus(
            platform="TikTok",
            supported_now=False,
            status="not_connected",
            capability_note="Prepared only for official profile and video metadata workflows.",
        ),
    ]
