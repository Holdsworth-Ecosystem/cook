"""Cook service entry point.

One scheduled job:
- request_processor: every 30 seconds  handles food intelligence queries
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from cook.config import get_settings
from cook.request_processor import process_pending_requests

log = structlog.get_logger(__name__)


def _configure_logging(level: str) -> None:
    from sturmey.telemetry import configure_structlog, init_telemetry

    configure_structlog(level)
    init_telemetry("cook")


async def main() -> None:
    settings = get_settings()
    _configure_logging(settings.log_level)

    from sturmey.version_check import check_sturmey_version

    check_sturmey_version()

    scheduler = AsyncIOScheduler(timezone="Europe/London")

    scheduler.add_job(
        process_pending_requests,
        trigger=IntervalTrigger(seconds=30),
        id="cook_request_processor",
        name="Cook request processor",
        replace_existing=True,
        max_instances=1,
        next_run_time=datetime.now(),
    )

    stop_event = asyncio.Event()

    def _handle_signal(sig: signal.Signals) -> None:
        log.info("shutdown_signal_received", signal=sig.name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig)

    log.info("cook_starting", jobs=["request_processor (every 30s)"])
    scheduler.start()
    log.info("cook_daemon_started")

    try:
        await stop_event.wait()
    finally:
        scheduler.shutdown(wait=False)
        log.info("cook_daemon_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
