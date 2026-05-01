from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.schemas.report import ScanReportMetadata
from src.services.report_generator import ReportGenerator


def _make_recommendation(**overrides):
    defaults = {
        "id": "rec-1",
        "scan_id": "scan-1",
        "market_ticker": "TEMP-NYC-HIGH",
        "market_title": "NYC Max Temperature Above 80F",
        "category": "climate",
        "side": "yes",
        "market_price": 30,
        "estimated_probability": 0.65,
        "confidence": 0.80,
        "edge": 0.35,
        "strength": "strong",
        "suggested_amount": 85.0,
        "reasoning": "Weather forecast shows sustained high temps",
        "research_data": {"summary": "Current: 78F. Next 24h: High 85F, Low 70F."},
        "status": "pending",
        "expires_at": datetime(2026, 2, 10, tzinfo=timezone.utc),
        "created_at": datetime(2026, 2, 8, 14, 30, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 2, 8, 14, 30, tzinfo=timezone.utc),
    }
    defaults.update(overrides)

    rec = MagicMock()
    for k, v in defaults.items():
        setattr(rec, k, v)
    return rec


def _make_metadata(**overrides):
    defaults = {
        "scan_id": "abc-123",
        "timestamp": datetime(2026, 2, 8, 14, 30, tzinfo=timezone.utc),
        "markets_scanned": 500,
        "markets_filtered": 15,
        "recommendations_count": 3,
        "categories_scanned": ["climate", "economics"],
    }
    defaults.update(overrides)
    return ScanReportMetadata(**defaults)


class TestReportGenerator:
    def setup_method(self):
        self.gen = ReportGenerator()

    def test_full_report_contains_header(self):
        report = self.gen.generate_full_report(_make_metadata(), [])
        assert "# Kalshi Edge Finder - Scan Report" in report

    def test_full_report_contains_metadata(self):
        report = self.gen.generate_full_report(_make_metadata(), [])
        assert "abc-123" in report
        assert "500" in report
        assert "15" in report

    def test_full_report_contains_recommendations(self):
        rec = _make_recommendation()
        report = self.gen.generate_full_report(_make_metadata(), [rec])
        assert "TEMP-NYC-HIGH" in report
        assert "strong" in report
        assert "Weather forecast" in report

    def test_full_report_no_recommendations(self):
        report = self.gen.generate_full_report(
            _make_metadata(recommendations_count=0), []
        )
        assert "No recommendations generated" in report

    def test_full_report_summary_counts(self):
        recs = [
            _make_recommendation(strength="strong"),
            _make_recommendation(id="rec-2", strength="medium", edge=0.22),
            _make_recommendation(id="rec-3", strength="weak", edge=0.16),
        ]
        report = self.gen.generate_full_report(_make_metadata(), recs)
        assert "Strong: 1" in report
        assert "Medium: 1" in report
        assert "Weak: 1" in report

    def test_memory_summary_contains_table(self):
        rec = _make_recommendation()
        summary = self.gen.generate_memory_summary(_make_metadata(), [rec])
        assert "| Ticker" in summary
        assert "TEMP-NYC-HIGH" in summary

    def test_memory_summary_has_category_breakdown(self):
        recs = [
            _make_recommendation(category="climate"),
            _make_recommendation(id="rec-2", category="economics", market_ticker="CPI-FEB"),
        ]
        summary = self.gen.generate_memory_summary(_make_metadata(), recs)
        assert "Climate" in summary
        assert "Economics" in summary

    def test_memory_summary_key_insights(self):
        recs = [
            _make_recommendation(edge=0.40, confidence=0.70),
            _make_recommendation(
                id="rec-2",
                market_ticker="CPI-FEB",
                edge=0.20,
                confidence=0.90,
            ),
        ]
        summary = self.gen.generate_memory_summary(_make_metadata(), recs)
        assert "Strongest edge" in summary
        assert "Most confident" in summary
