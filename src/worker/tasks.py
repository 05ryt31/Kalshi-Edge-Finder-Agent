from datetime import datetime, timezone

from src.clients.kalshi import KalshiClient
from src.clients.nws import NWSClient
from src.clients.openweather import OpenWeatherClient
from src.config import settings  # noqa: F401  (kept for downstream env access)
from src.db.repositories.recommendation import RecommendationRepository
from src.db.repositories.scan import ScanRepository
from src.db.repositories.settings import SettingsRepository
from src.db.session import async_session_factory
from src.schemas.report import ScanReportMetadata
from src.schemas.settings import Settings
from src.services.decision import DecisionEngine
from src.services.estimator import ProbabilityEstimator
from src.services.filter import FilterService
from src.services.historical_context import HistoricalContextService
from src.services.report_generator import ReportGenerator
from src.services.report_writer import ReportWriter
from src.services.research.agent import ResearchAgent
from src.services.scanner import ScannerService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_scan_task(*, scan_id: str | None = None) -> str:
    logger.info("scan_task_started", scan_id=scan_id)

    kalshi = KalshiClient()
    openweather = OpenWeatherClient()
    nws = NWSClient()

    try:
        async with async_session_factory() as session:
            settings_repo = SettingsRepository(session)
            settings_model = await settings_repo.get()
            app_settings = Settings.model_validate(settings_model)

            scanner = ScannerService(kalshi)
            filter_service = FilterService(app_settings)
            research_agent = ResearchAgent(openweather, nws)
            estimator = ProbabilityEstimator()
            decision_engine = DecisionEngine(app_settings)

            logger.info(
                "scan_mode",
                paper_trading=app_settings.paper_trading,
                categories=app_settings.categories,
                max_bet_amount=app_settings.max_bet_amount,
            )

            scan_repo = ScanRepository(session)
            if scan_id:
                scan = await scan_repo.get(scan_id)
                if scan is None:
                    raise ValueError(f"Scan {scan_id} not found")
            else:
                scan = await scan_repo.create()
                scan_id = scan.id
            logger.info("scan_created", scan_id=scan_id)

            try:
                markets = []
                async for market in scanner.scan_all_markets():
                    markets.append(market)

                await scan_repo.update(scan, markets_scanned=len(markets))
                logger.info("markets_scanned", count=len(markets))

                filtered = filter_service.filter_markets(markets)
                await scan_repo.update(scan, markets_filtered=len(filtered))
                logger.info("markets_filtered", count=len(filtered))

                recommendation_repo = RecommendationRepository(session)
                historical_service = HistoricalContextService(recommendation_repo)
                rec_count = 0

                for market in filtered:
                    try:
                        # Skip past events with extreme prices before any research/LLM
                        if market.is_past_event and market.is_extreme_price:
                            logger.info(
                                "skipped_past_extreme",
                                ticker=market.ticker,
                                yes_ask=market.yes_ask,
                            )
                            continue

                        research_data = await research_agent.research(market)

                        # Suppress historical context for concluded events to prevent echo chamber
                        if market.is_past_event:
                            historical_context = ""
                        else:
                            historical_context = await historical_service.get_context_for_category(
                                market.category, exclude_scan_id=scan_id
                            )

                        estimate = await estimator.estimate(
                            market, research_data, historical_context=historical_context
                        )

                        recommendation = decision_engine.evaluate(
                            market=market,
                            estimate=estimate,
                            research_data=research_data,
                            scan_id=scan_id,
                        )

                        if recommendation:
                            await recommendation_repo.create(
                                {
                                    **recommendation.model_dump(),
                                    "research_data": research_data,
                                    "reasoning": estimate["reasoning"],
                                }
                            )
                            rec_count += 1
                            logger.info(
                                "recommendation_saved",
                                ticker=market.ticker,
                                side=recommendation.side,
                                strength=recommendation.strength,
                                edge=f"{recommendation.edge:.1%}",
                            )
                    except Exception as e:
                        logger.error(
                            "market_processing_error", ticker=market.ticker, error=str(e)
                        )

                # Generate reports
                await _generate_reports(
                    recommendation_repo=recommendation_repo,
                    scan_id=scan_id,
                    markets_scanned=len(markets),
                    markets_filtered=len(filtered),
                    rec_count=rec_count,
                    filtered_markets=filtered,
                )

                await scan_repo.update(
                    scan, status="completed", recommendations_generated=rec_count
                )
                await session.commit()

                logger.info("scan_task_completed", scan_id=scan_id, recommendations=rec_count)
                return scan_id

            except Exception as e:
                logger.error("scan_task_failed", scan_id=scan_id, error=str(e))
                await session.rollback()
                async with async_session_factory() as err_session:
                    err_scan_repo = ScanRepository(err_session)
                    err_scan = await err_scan_repo.get(scan_id)
                    if err_scan:
                        await err_scan_repo.update(
                            err_scan, status="failed", error_message=str(e)
                        )
                        await err_session.commit()
                raise

    except Exception as e:
        logger.error("scan_task_failed", error=str(e))
        raise
    finally:
        await kalshi.close()
        await openweather.close()
        await nws.close()


async def _generate_reports(
    *,
    recommendation_repo: RecommendationRepository,
    scan_id: str,
    markets_scanned: int,
    markets_filtered: int,
    rec_count: int,
    filtered_markets: list,
) -> None:
    try:
        scan_recs = await recommendation_repo.list_by_scan(scan_id)
        now = datetime.now(timezone.utc)

        categories = list({m.category for m in filtered_markets})
        metadata = ScanReportMetadata(
            scan_id=scan_id,
            timestamp=now,
            markets_scanned=markets_scanned,
            markets_filtered=markets_filtered,
            recommendations_count=rec_count,
            categories_scanned=categories,
        )

        generator = ReportGenerator()
        writer = ReportWriter()

        full_report = generator.generate_full_report(metadata, scan_recs)
        memory_summary = generator.generate_memory_summary(metadata, scan_recs)

        await writer.write_full_report(full_report, scan_id, now)
        await writer.write_memory_summary(memory_summary, scan_id, now)

        logger.info("reports_generated", scan_id=scan_id)
    except Exception as e:
        logger.error("report_generation_failed", scan_id=scan_id, error=str(e))
