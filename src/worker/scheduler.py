from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.utils.logger import get_logger
from src.worker.tasks import run_scan_task

logger = get_logger(__name__)


class ScanScheduler:
    def __init__(self, interval_hours: int = 1) -> None:
        self.scheduler = AsyncIOScheduler()
        self.interval_hours = interval_hours

    async def start(self) -> None:
        logger.info("starting_scheduler", interval_hours=self.interval_hours)
        self.scheduler.add_job(
            run_scan_task,
            "interval",
            hours=self.interval_hours,
            id="scan_job",
            replace_existing=True,
        )
        self.scheduler.start()

    def stop(self) -> None:
        logger.info("stopping_scheduler")
        self.scheduler.shutdown()
