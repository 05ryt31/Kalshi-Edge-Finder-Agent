#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.session import create_tables
from src.utils.logger import setup_logging
from src.worker.tasks import run_scan_task


async def main():
    setup_logging()
    await create_tables()

    print("Starting manual scan...")
    scan_id = await run_scan_task()
    print(f"Scan completed: {scan_id}")


if __name__ == "__main__":
    asyncio.run(main())
