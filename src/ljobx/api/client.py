import httpx
import asyncio
from urllib.parse import urlencode
from fake_useragent import UserAgent

from ljobx.utils.logger import get_logger

logger = get_logger(__name__)


class ApiClient:
    """
    Handles all the network requests for the LinkedIn scraper using httpx.
    """
    BASE_LIST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    BASE_DETAILS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    def __init__(self, concurrency_limit=5, delay=1):
        self.client = httpx.AsyncClient()
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.delay = delay
        self.ua = UserAgent()

    def _headers(self):
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def _fetch(self, url, timeout=10):
        logger.debug("Fetching URL: %s", url)
        response = await self.client.get(url, headers=self._headers(), timeout=timeout)
        response.raise_for_status()
        return response.text

    async def get_job_list(self, query_params):
        url = f"{self.BASE_LIST_URL}?{urlencode(query_params)}"
        try:
            return await self._fetch(url, timeout=10)
        except Exception as e:
            logger.error("Error fetching job list for URL %s: %s", url, e)
            return None

    async def get_job_details(self, job_id):
        async with self.semaphore:
            await asyncio.sleep(self.delay)
            url = self.BASE_DETAILS_URL.format(job_id=job_id)
            try:
                return await self._fetch(url, timeout=15)
            except Exception as e:
                logger.warning("Could not fetch job details for ID %s: %s", job_id, e)
                return {"error": str(e)}

    async def close(self):
        await self.client.aclose()
