import httpx
import asyncio
import random
from typing import Dict, List
from urllib.parse import urlencode
from fake_useragent import UserAgent

from ljobx.utils.logger import get_logger

logger = get_logger(__name__)


class LinkedInApi:
    """
    Handles all the network requests for the LinkedIn scraper using httpx.
    """
    BASE_LIST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    BASE_DETAILS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    def __init__(self, concurrency_limit=5, delay=1, proxies: List[str] | None = None):
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.delay = delay
        self.ua = UserAgent()

        # Create a pool of pre-configured client instances, one for each proxy.
        # This allows for connection pooling and is much more efficient.
        if proxies:
            self.client_map: Dict[str | None, httpx.AsyncClient] = {
                proxy: httpx.AsyncClient(proxy=proxy) for proxy in proxies
            }
        else:
            self.client_map = {None: httpx.AsyncClient()}
        self._client_keys = list(self.client_map.keys())

    def _headers(self):
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def _fetch(self, url, timeout=10):
        proxy_key = random.choice(self._client_keys)
        client = self.client_map[proxy_key]

        if proxy_key:
            logger.debug(f"Fetching URL: {url} via proxy: ...{proxy_key[-20:]}")
        else:
            logger.debug(f"Fetching URL: {url}")

        response = await client.get(url, headers=self._headers(), timeout=timeout)
        response.raise_for_status()
        return response.text

    async def get_job_list(self, query_params):
        """
        Fetches a page of job listings with a delay.
        """
        async with self.semaphore:
            await asyncio.sleep(self.delay)
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
                return await self._fetch(url, timeout=2)
            except Exception as e:
                logger.warning("Could not fetch job details for ID %s: %s", job_id, e)
                return {"error": str(e)}

    async def close(self):
        """
        Properly closes all client instances in the pool.
        """
        logger.debug(f"Closing {len(self.client_map)} client instance(s)...")
        tasks = [client.aclose() for client in self.client_map.values()]
        await asyncio.gather(*tasks)
        logger.debug("All client instances closed.")

