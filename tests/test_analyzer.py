"""Unit tests for the marketing-file analyzer."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from analyzer import AnalysisError, analyze, compute_kpis, detect_columns

SAMPLE_CSV = (
    "Date,Campaign,Channel,Impressions,Clicks,Spend,Conversions,Revenue\n"
    "2026-01-01,Summer Sale,Google Ads,100000,4000,2000.00,200,12000.00\n"
    "2026-01-01,Retargeting,Meta,50000,2000,1000.00,100,8000.00\n"
)


def _csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def test_detect_columns_handles_aliases():
    detected = detect_columns(["Impr.", "Cost", "Purchases", "Platform"])
    assert detected["impressions"] == "Impr."
    assert detected["spend"] == "Cost"
    assert detected["conversions"] == "Purchases"
    assert detected["channel"] == "Platform"


def test_compute_kpis_basic():
    kpis = compute_kpis(
        {"impressions": 100000, "clicks": 5000, "spend": 1000, "conversions": 250, "revenue": 5000}
    )
    assert kpis["ctr"] == 5.0
    assert kpis["cpc"] == 0.2
    assert kpis["cpm"] == 10.0
    assert kpis["conversion_rate"] == 5.0
    assert kpis["cpa"] == 4.0
    assert kpis["roas"] == 5.0


def test_compute_kpis_handles_zero_denominators():
    kpis = compute_kpis({"impressions": 0, "clicks": 0, "spend": 0, "conversions": 0, "revenue": 0})
    assert kpis["ctr"] is None
    assert kpis["cpc"] is None
    assert kpis["roas"] is None


def test_analyze_totals_and_breakdowns():
    result = analyze(_csv_bytes(SAMPLE_CSV), "report.csv")
    assert result.row_count == 2
    assert result.totals["impressions"] == 150000
    assert result.totals["spend"] == 3000
    assert result.totals["revenue"] == 20000
    # ROAS = 20000 / 3000
    assert result.kpis["roas"] == pytest.approx(6.67, abs=0.01)
    assert "campaign" in result.breakdowns
    assert "channel" in result.breakdowns
    names = {row["name"] for row in result.breakdowns["campaign"]}
    assert {"Summer Sale", "Retargeting"} <= names


def test_analyze_rejects_empty_file():
    with pytest.raises(AnalysisError):
        analyze(_csv_bytes("col_a,col_b\n"), "empty.csv")


def test_analyze_rejects_no_metrics():
    with pytest.raises(AnalysisError):
        analyze(_csv_bytes("first,last\nJane,Doe\n"), "contacts.csv")


def test_analyze_excel(tmp_path):
    df = pd.DataFrame(
        {
            "Campaign": ["A", "B"],
            "Impressions": [1000, 2000],
            "Clicks": [100, 200],
            "Cost": [50.0, 75.0],
        }
    )
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    result = analyze(buffer.getvalue(), "report.xlsx")
    assert result.row_count == 2
    assert result.totals["impressions"] == 3000
    assert result.detected_columns["spend"] == "Cost"


def test_analyze_missing_revenue_warns():
    csv = "Campaign,Impressions,Clicks,Spend\nA,1000,100,50\n"
    result = analyze(_csv_bytes(csv), "no_rev.csv")
    assert result.kpis["roas"] is None
    assert any("revenue" in w.lower() for w in result.warnings)
