import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from app.database import async_session
from app.models import Galaxy
from app.services import audit_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 60


async def _weekly_audit():
    """Run audit on all galaxies with retry logic."""
    logger.info("Weekly audit triggered")
    async with async_session() as db:
        galaxies = (await db.execute(select(Galaxy))).scalars().all()
    for galaxy in galaxies:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = await audit_service.run_audit(galaxy.id)
                logger.info(f"Audit complete for galaxy {galaxy.id}: {result}")
                break
            except Exception as e:
                logger.error(f"Audit failed for galaxy {galaxy.id} (attempt {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                else:
                    logger.error(f"Audit exhausted all {MAX_RETRIES} retries for galaxy {galaxy.id}")


async def _weekly_digest():
    """Send weekly digest emails to all users in all galaxies."""
    logger.info("Weekly digest triggered")
    from app.services import digest_service
    async with async_session() as db:
        galaxies = (await db.execute(select(Galaxy))).scalars().all()
    for galaxy in galaxies:
        try:
            delivered = await digest_service.send_digest_to_users(galaxy.id)
            logger.info(f"Digest sent for galaxy {galaxy.id}: {len(delivered)} recipients")
        except Exception as e:
            logger.error(f"Digest failed for galaxy {galaxy.id}: {e}")


def start_scheduler():
    scheduler.add_job(_weekly_audit, CronTrigger(day_of_week="sun", hour=2, minute=0), id="weekly_audit", replace_existing=True)
    scheduler.add_job(_weekly_digest, CronTrigger(day_of_week="mon", hour=8, minute=0), id="weekly_digest", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started — audit Sun 2AM, digest Mon 8AM")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
