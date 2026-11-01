"""Source snapshots for the only two approved Summary UI changes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_web_summary_source_snapshot_has_only_text_and_muted_note_contract():
    source = (ROOT / "frontend/src/components/dashboard/WireframeAnalyze.tsx").read_text(encoding="utf-8")
    expected = '{analysis?.summary ? <Card><h2 className="text-xl font-black">Summary</h2><p className="mt-3 text-[15px] leading-5 text-[#1E1633]">{analysis.summary}</p>{analysis.summary_note ? <p className="mt-3 text-sm leading-5 text-[#5F587A]">{analysis.summary_note}</p> : null}</Card> : null}'
    assert expected in source
    assert "first_24h_status" not in source and "milestone_hours" not in source


def test_mobile_summary_source_snapshot_keeps_existing_card_and_muted_style():
    source = (ROOT / "mobile/src/screens/TrackingReportScreen.tsx").read_text(encoding="utf-8")
    expected = '{analysis?.summary ? <Card title="Summary"><Text style={styles.body}>{analysis.summary}</Text>{analysis.summary_note ? <Text style={styles.muted}>{analysis.summary_note}</Text> : null}</Card> : null}'
    assert expected in source
    assert "first_24h_status" not in source and "milestone_hours" not in source
