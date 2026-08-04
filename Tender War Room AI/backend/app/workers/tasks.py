import asyncio
import logging
from app.workers.celery_app import celery_app
from app.db.session import async_session_maker
from app.services.scraper_service import tender_scraper_service

logger = logging.getLogger("app.tasks")


async def _async_run_scraper(query: str) -> list:
    async with async_session_maker() as session:
        try:
            tenders = await tender_scraper_service.scrape_portal(session, query=query)
            return [str(t.id) for t in tenders]
        except Exception as e:
            logger.error("Failed to run scraper task: %s", str(e), exc_info=True)
            raise


@celery_app.task(name="app.workers.tasks.run_scraper_task", bind=True, max_retries=3, default_retry_delay=60)
def run_scraper_task(self, query: str = "SCCL") -> list:
    """
    Celery task that executes Playwright scraping in the background.
    """
    logger.info("Executing background scraper task for query: %s", query)
    try:
        # Run async coroutine in synchronous worker process thread
        return asyncio.run(_async_run_scraper(query))
    except Exception as exc:
        logger.warning("Scraper task failed, retrying. Error: %s", str(exc))
        # Automatic retry mechanism
        raise self.retry(exc=exc)


from app.services.extraction_service import pdf_extraction_service

async def _async_run_extraction(tender_id: str) -> str:
    async with async_session_maker() as session:
        try:
            tender = await pdf_extraction_service.extract_and_update_tender(session, tender_id)
            return str(tender.id)
        except Exception as e:
            logger.error("Failed to run extraction task for tender %s: %s", tender_id, str(e), exc_info=True)
            raise


@celery_app.task(name="app.workers.tasks.run_extraction_task", bind=True, max_retries=3, default_retry_delay=60)
def run_extraction_task(self, tender_id: str) -> str:
    """
    Celery task that executes metadata extraction in the background.
    """
    logger.info("Executing background extraction task for tender_id: %s", tender_id)
    try:
        return asyncio.run(_async_run_extraction(tender_id))
    except Exception as exc:
        logger.warning("Extraction task failed, retrying. Error: %s", str(exc))
        raise self.retry(exc=exc)

