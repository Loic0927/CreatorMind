"""Source snapshots for the Summary UI contract (whitespace-insensitive, so formatting changes don't matter)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _compact(relative_path: str) -> str:
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    return re.sub(r"\s+", "", source)


def test_web_summary_source_snapshot_has_only_text_and_muted_note_contract():
    source = _compact("frontend/src/components/dashboard/AnalyzeTab.tsx")
    expected = re.sub(
        r"\s+",
        "",
        '{analysis?.summary ? ( <Card> <h2 className="text-xl font-black">Summary</h2>'
        ' <p className="mt-3 text-[15px] leading-5 text-slate-900">{analysis.summary}</p> </Card> ) : null}',
    )
    assert expected in source
    assert "first_24h_status" not in source and "milestone_hours" not in source


def test_mobile_summary_source_snapshot_keeps_existing_card_and_muted_style():
    source = _compact("mobile/src/screens/TrackingReportScreen.tsx")
    expected = re.sub(
        r"\s+",
        "",
        '{analysis?.summary ? ( <Card title="Summary"> <Text style={styles.body}>{analysis.summary}</Text> </Card> ) : null}',
    )
    assert expected in source
    assert "first_24h_status" not in source and "milestone_hours" not in source
