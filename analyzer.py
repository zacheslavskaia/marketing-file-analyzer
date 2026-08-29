"""Core marketing-file analysis logic.

This module is intentionally free of any web-framework dependencies so it can be
unit tested in isolation and reused from a CLI, a notebook, or the Flask app.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# Canonical metric name -> list of accepted (case-insensitive) column aliases.
# Marketing exports from different platforms (Google Ads, Meta, LinkedIn, TikTok,
# generic spreadsheets) name the same concept differently, so we normalise them.
COLUMN_ALIASES: dict[str, list[str]] = {
    "impressions": ["impressions", "impr", "impr.", "views", "reach"],
    "clicks": ["clicks", "click", "link clicks", "taps"],
    "spend": ["spend", "cost", "amount spent", "amount_spent", "budget", "spent"],
    "conversions": [
        "conversions",
        "conversion",
        "conv",
        "conv.",
        "purchases",
        "results",
        "orders",
        "leads",
    ],
    "revenue": ["revenue", "conversion value", "conv. value", "sales", "total revenue"],
    "campaign": ["campaign", "campaign name", "campaign_name", "ad group", "adset name"],
    "channel": ["channel", "platform", "source", "medium", "network"],
    "date": ["date", "day", "reporting date", "report date"],
}

# Metrics that are summed across rows to produce totals.
ADDITIVE_METRICS = ["impressions", "clicks", "spend", "conversions", "revenue"]


class AnalysisError(ValueError):
    """Raised when an uploaded file cannot be analyzed."""


@dataclass
class AnalysisResult:
    row_count: int
    columns: list[str]
    detected_columns: dict[str, str]
    totals: dict[str, float]
    kpis: dict[str, float | None]
    breakdowns: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "columns": self.columns,
            "detected_columns": self.detected_columns,
            "totals": self.totals,
            "kpis": self.kpis,
            "breakdowns": self.breakdowns,
            "warnings": self.warnings,
        }


def _normalize(name: str) -> str:
    return str(name).strip().lower()


def detect_columns(columns: list[str]) -> dict[str, str]:
    """Map canonical metric names to the actual column present in the file."""
    normalized = {_normalize(c): c for c in columns}
    detected: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                detected[canonical] = normalized[alias]
                break
    return detected


def read_dataframe(data: bytes, filename: str) -> pd.DataFrame:
    """Read raw uploaded bytes into a DataFrame based on the file extension."""
    name = (filename or "").lower()
    buffer = io.BytesIO(data)
    try:
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(buffer)
        if name.endswith((".tsv",)):
            return pd.read_csv(buffer, sep="\t")
        # Default to CSV for .csv and unknown extensions.
        return pd.read_csv(buffer)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the user
        raise AnalysisError(f"Could not parse '{filename}': {exc}") from exc


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator in (0, None) or (isinstance(denominator, float) and math.isnan(denominator)):
        return None
    value = numerator / denominator
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _column_total(df: pd.DataFrame, column: str) -> float:
    series = pd.to_numeric(df[column], errors="coerce")
    total = series.sum(skipna=True)
    return float(0.0 if pd.isna(total) else total)


def _ratio(numerator: float | None, denominator: float | None, scale: float = 1.0) -> float | None:
    """Ratio helper that returns None if either input metric is absent."""
    if numerator is None or denominator is None:
        return None
    result = _safe_div(numerator, denominator)
    return None if result is None else result * scale


def compute_kpis(totals: dict[str, float]) -> dict[str, float | None]:
    """Derive standard marketing KPIs from summed totals.

    A KPI is reported only when every metric it depends on is present in
    ``totals``. A metric that is present but zero yields ``None`` for ratios
    that divide by it, rather than being confused with an absent metric.
    """
    impressions = totals.get("impressions")
    clicks = totals.get("clicks")
    spend = totals.get("spend")
    conversions = totals.get("conversions")
    revenue = totals.get("revenue")

    return {
        "ctr": _round(_ratio(clicks, impressions, 100)),
        "cpc": _round(_ratio(spend, clicks)),
        "cpm": _round(_ratio(spend, impressions, 1000)),
        "conversion_rate": _round(_ratio(conversions, clicks, 100)),
        "cpa": _round(_ratio(spend, conversions)),
        "roas": _round(_ratio(revenue, spend)),
    }


def _build_breakdown(df: pd.DataFrame, group_col: str, detected: dict[str, str]) -> list[dict[str, Any]]:
    present_metrics = [m for m in ADDITIVE_METRICS if m in detected]
    rows: list[dict[str, Any]] = []
    grouped = df.groupby(df[group_col].fillna("(unknown)").astype(str))
    for key, subset in grouped:
        totals = {m: _column_total(subset, detected[m]) for m in present_metrics}
        entry: dict[str, Any] = {"name": key, "rows": int(len(subset))}
        for metric, value in totals.items():
            entry[metric] = _round(value)
        kpis = compute_kpis(totals)
        entry["ctr"] = kpis["ctr"]
        entry["roas"] = kpis["roas"]
        entry["cpa"] = kpis["cpa"]
        rows.append(entry)

    # Sort by spend when available, otherwise by impressions, else by row count.
    sort_key = "spend" if "spend" in present_metrics else (
        "impressions" if "impressions" in present_metrics else "rows"
    )
    rows.sort(key=lambda r: (r.get(sort_key) or 0), reverse=True)
    return rows[:20]


def analyze(data: bytes, filename: str) -> AnalysisResult:
    """Analyze raw uploaded file bytes and return marketing insights."""
    df = read_dataframe(data, filename)

    if df.empty:
        raise AnalysisError("The uploaded file has no rows to analyze.")

    columns = [str(c) for c in df.columns]
    detected = detect_columns(columns)
    warnings: list[str] = []

    present_metrics = [m for m in ADDITIVE_METRICS if m in detected]
    if not present_metrics:
        raise AnalysisError(
            "No recognizable marketing metrics found. Expected at least one of: "
            "impressions, clicks, spend, conversions, revenue."
        )

    totals = {metric: _column_total(df, detected[metric]) for metric in present_metrics}
    kpis = compute_kpis(totals)

    breakdowns: dict[str, list[dict[str, Any]]] = {}
    for dimension in ("campaign", "channel"):
        if dimension in detected:
            breakdowns[dimension] = _build_breakdown(df, detected[dimension], detected)

    if "spend" not in detected:
        warnings.append("No spend/cost column detected; cost-based KPIs are unavailable.")
    if "revenue" not in detected:
        warnings.append("No revenue column detected; ROAS is unavailable.")

    return AnalysisResult(
        row_count=int(len(df)),
        columns=columns,
        detected_columns=detected,
        totals={k: _round(v) for k, v in totals.items()},
        kpis=kpis,
        breakdowns=breakdowns,
        warnings=warnings,
    )
