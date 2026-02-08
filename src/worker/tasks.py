from src.clients.fred import FREDClient
from src.clients.kalshi import KalshiClient
from src.clients.openweather import OpenWeatherClient
from src.db.repositories.recommendation import RecommendationRepository
from src.db.repositories.scan import ScanRepository
from src.db.repositories.settings import SettingsRepository
from src.db.session import async_session_factory
from src.schemas.settings import Settings
from src.services.decision import DecisionEngine
from src.services.estimator import ProbabilityEstimator
from src.services.filter import FilterService
from src.services.research.agent import ResearchAgent
from src.services.scanner import ScannerService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_scan_task() -> str:
    logger.info("scan_task_started")

    kalshi = KalshiClient()
    openweather = OpenWeatherClient()
    fred = FREDClient()

    try:
        async with async_session_factory() as session:
            settings_repo = SettingsRepository(session)
            settings_model = await settings_repo.get()
            app_settings = Settings.model_validate(settings_model)

            scanner = ScannerService(kalshi)
            filter_service = FilterService(app_settings)
            research_agent = ResearchAgent(openweather, fred)
            estimator = ProbabilityEstimator()
            decision_engine = DecisionEngine(app_settings)

            scan_repo = ScanRepository(session)
            scan = await scan_repo.create()
            scan_id = scan.id
            logger.info("scan_created", scan_id=scan_id)

            markets = []
            async for market in scanner.scan_all_markets():
                markets.append(market)

            await scan_repo.update(scan, markets_scanned=len(markets))
            logger.info("markets_scanned", count=len(markets))

            filtered = filter_service.filter_markets(markets)
            await scan_repo.update(scan, markets_filtered=len(filtered))
            logger.info("markets_filtered", count=len(filtered))

            recommendation_repo = RecommendationRepository(session)
            rec_count = 0

            for market in filtered:
                try:
                    research_data = await research_agent.research(market)
                    estimate = await estimator.estimate(market, research_data)
                    recommendation = decision_engine.evaluate(
                        market=market,
                        estimate=estimate,
                        research_data=research_data,
                        scan_id=scan_id,
                    )

                    if recommendation:
                        await recommendation_repo.create(
                            {
                                **recommendation.model_dump(exclude={"yes_multiplier", "no_multiplier"}),
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
                    logger.error("market_processing_error", ticker=market.ticker, error=str(e))

            await scan_repo.update(
                scan, status="completed", recommendations_generated=rec_count
            )
            await session.commit()

            logger.info("scan_task_completed", scan_id=scan_id, recommendations=rec_count)
            return scan_id

    except Exception as e:
        logger.error("scan_task_failed", error=str(e))
        raise
    finally:
        await kalshi.close()
        await openweather.close()
        await fred.close()
