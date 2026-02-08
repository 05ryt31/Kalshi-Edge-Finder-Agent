from collections import defaultdict

from src.models.recommendation import RecommendationModel
from src.schemas.report import ScanReportMetadata


class ReportGenerator:
    def generate_full_report(
        self,
        metadata: ScanReportMetadata,
        recommendations: list[RecommendationModel],
    ) -> str:
        sections = [
            self._header(),
            self._metadata_table(metadata),
            self._recommendations_section(recommendations),
            self._summary_section(recommendations),
        ]
        return "\n\n".join(sections)

    def generate_memory_summary(
        self,
        metadata: ScanReportMetadata,
        recommendations: list[RecommendationModel],
    ) -> str:
        sections = [
            self._memory_header(metadata),
            self._picks_table(recommendations),
            self._category_breakdown(recommendations),
            self._key_insights(recommendations),
        ]
        return "\n\n".join(sections)

    def _header(self) -> str:
        return "# Kalshi Edge Finder - Scan Report"

    def _metadata_table(self, metadata: ScanReportMetadata) -> str:
        timestamp = metadata.timestamp.strftime("%Y-%m-%d %H:%M UTC")
        categories = ", ".join(metadata.categories_scanned) if metadata.categories_scanned else "none"
        return (
            "## Scan Metadata\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            f"| Scan ID | `{metadata.scan_id}` |\n"
            f"| Timestamp | {timestamp} |\n"
            f"| Markets Scanned | {metadata.markets_scanned} |\n"
            f"| Markets Filtered | {metadata.markets_filtered} |\n"
            f"| Recommendations | {metadata.recommendations_count} |\n"
            f"| Categories | {categories} |"
        )

    def _recommendations_section(self, recommendations: list[RecommendationModel]) -> str:
        if not recommendations:
            return "## Recommendations\n\nNo recommendations generated."

        parts = ["## Recommendations"]
        for i, rec in enumerate(recommendations, 1):
            research_summary = self._extract_summary(rec.research_data)
            parts.append(
                f"### {i}. {rec.market_title}\n"
                f"- **Ticker:** `{rec.market_ticker}`\n"
                f"- **Category:** {rec.category}\n"
                f"- **Side:** {rec.side}\n"
                f"- **Market Price:** {rec.market_price}c\n"
                f"- **Estimated Probability:** {rec.estimated_probability:.0%}\n"
                f"- **Confidence:** {rec.confidence:.0%}\n"
                f"- **Edge:** {rec.edge:.1%}\n"
                f"- **Strength:** {rec.strength}\n"
                f"- **Suggested Amount:** ${rec.suggested_amount:.2f}\n\n"
                f"#### Reasoning\n{rec.reasoning or 'N/A'}\n\n"
                f"#### Research Summary\n{research_summary}\n\n"
                f"---"
            )
        return "\n\n".join(parts)

    def _summary_section(self, recommendations: list[RecommendationModel]) -> str:
        if not recommendations:
            return "## Summary\n\nNo data to summarize."

        by_strength = defaultdict(int)
        for rec in recommendations:
            by_strength[rec.strength] += 1

        avg_edge = sum(r.edge for r in recommendations) / len(recommendations)
        avg_conf = sum(r.confidence for r in recommendations) / len(recommendations)

        return (
            "## Summary\n"
            f"- Total recommendations: {len(recommendations)}\n"
            f"- Strong: {by_strength.get('strong', 0)} "
            f"| Medium: {by_strength.get('medium', 0)} "
            f"| Weak: {by_strength.get('weak', 0)}\n"
            f"- Average edge: {avg_edge:.1%}\n"
            f"- Average confidence: {avg_conf:.0%}"
        )

    def _memory_header(self, metadata: ScanReportMetadata) -> str:
        timestamp = metadata.timestamp.strftime("%Y-%m-%d %H:%M")
        return (
            f"# Scan Summary - {timestamp}\n\n"
            f"**{metadata.recommendations_count}** recommendations from "
            f"**{metadata.markets_filtered}** filtered markets "
            f"(of {metadata.markets_scanned} total)."
        )

    def _picks_table(self, recommendations: list[RecommendationModel]) -> str:
        if not recommendations:
            return "## Top Picks\n\nNone."

        rows = ["## Top Picks", "| Ticker | Side | Edge | Strength | Confidence |", "|--------|------|------|----------|------------|"]
        for rec in recommendations[:10]:
            rows.append(
                f"| `{rec.market_ticker}` | {rec.side} "
                f"| {rec.edge:.1%} | {rec.strength} | {rec.confidence:.0%} |"
            )
        return "\n".join(rows)

    def _category_breakdown(self, recommendations: list[RecommendationModel]) -> str:
        by_category: dict[str, list[RecommendationModel]] = defaultdict(list)
        for rec in recommendations:
            by_category[rec.category].append(rec)

        lines = ["## Category Breakdown"]
        for cat, recs in sorted(by_category.items()):
            avg_edge = sum(r.edge for r in recs) / len(recs)
            lines.append(f"- {cat.capitalize()}: {len(recs)} recs, avg edge {avg_edge:.1%}")

        return "\n".join(lines) if len(lines) > 1 else "## Category Breakdown\n\nNo data."

    def _key_insights(self, recommendations: list[RecommendationModel]) -> str:
        if not recommendations:
            return "## Key Insights\n\nNo data."

        strongest = max(recommendations, key=lambda r: r.edge)
        most_confident = max(recommendations, key=lambda r: r.confidence)

        return (
            "## Key Insights\n"
            f"- Strongest edge: `{strongest.market_ticker}` at {strongest.edge:.1%}\n"
            f"- Most confident: `{most_confident.market_ticker}` at {most_confident.confidence:.0%}"
        )

    def _extract_summary(self, research_data: dict | None) -> str:
        if not research_data:
            return "N/A"
        return research_data.get("summary", "N/A")
