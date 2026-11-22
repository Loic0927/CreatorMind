"""Source snapshots for the Summary UI contract (whitespace-insensitive, so formatting changes don't matter)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _compact(relative_path: str) -> str:
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    return re.sub(r"\s+", "", source)


def test_web_summary_source_snapshot_has_only_text_and_muted_note_contract():
    source = _compact("frontend/src/components/dashboard/AnalyzeTab.tsx")
    assert "{analysis?.summary?(" in source
    assert '<h2className="text-xlfont-black">Summary</h2>' in source
    assert '<pclassName="mt-3text-[15px]leading-5text-ink">{analysis.summary}</p>' in source
    assert 'analysis?.summary_status==="pending"' in source
    assert "Yoursummaryisbeingprepared." in source
    assert "first_24h_status" not in source and "milestone_hours" not in source


def test_mobile_summary_source_snapshot_keeps_existing_card_and_muted_style():
    source = _compact("mobile/src/screens/TrackingReportScreen.tsx")
    assert "{analysis?.summary?(" in source
    assert '<Cardtitle="Summary"><Textstyle={styles.body}>{analysis.summary}</Text></Card>' in source
    assert 'analysis?.summary_status==="pending"' in source
    assert "Yoursummaryisbeingprepared." in source
    assert "first_24h_status" not in source and "milestone_hours" not in source
