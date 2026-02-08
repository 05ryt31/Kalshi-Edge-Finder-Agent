import asyncio
from datetime import datetime
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"


def _get_claude_memory_dir() -> Path:
    project_path = str(PROJECT_ROOT)
    slug = project_path.replace("/", "-").lstrip("-")
    return Path.home() / ".claude" / "projects" / slug / "memory"


class ReportWriter:
    def __init__(
        self,
        *,
        reports_dir: Path = REPORTS_DIR,
        memory_dir: Path | None = None,
    ) -> None:
        self.reports_dir = reports_dir
        self.memory_dir = memory_dir or _get_claude_memory_dir()

    async def write_full_report(
        self, content: str, scan_id: str, timestamp: datetime
    ) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        ts = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"scan_{scan_id[:8]}_{ts}.md"
        path = self.reports_dir / filename

        await asyncio.to_thread(path.write_text, content, "utf-8")
        logger.info("full_report_written", path=str(path))
        return path

    async def write_memory_summary(
        self, content: str, scan_id: str, timestamp: datetime
    ) -> Path:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        ts = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"scan_summary_{ts}.md"
        path = self.memory_dir / filename

        await asyncio.to_thread(path.write_text, content, "utf-8")
        logger.info("memory_summary_written", path=str(path))
        return path
