import time
import httpx
import asyncio
import random
import itertools
from typing import Dict, List
from urllib.parse import urlencode
from fake_useragent import UserAgent

from ljobx.utils.logger import get_logger

logger = get_logger(__name__)

class LinkedInClient:
    BASE_LIST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    BASE_DETAILS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    def __init__(self, concurrency_limit=5, delay: Dict[str, int] | None = None, proxies: List[str] | None = None):
        self.concurrency_limit = concurrency_limit
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.delay = delay
        self.ua = UserAgent()

        if proxies:
            self.client_map: Dict[str | None, httpx.AsyncClient] = {
                proxy: httpx.AsyncClient(proxy=proxy) for proxy in proxies
            }
        else:
            self.client_map = {None: httpx.AsyncClient()}

        self._client_keys = list(self.client_map.keys())
        self._proxy_cycle = itertools.cycle(self._client_keys)
        self._proxy_failures: Dict[str | None, int] = {k: 0 for k in self._client_keys}
        self._proxy_cooldown: Dict[str | None, float] = {k: 0 for k in self._client_keys}

    def _headers(self):
        return { "User-Agent": self.ua.random, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9" }

    def _get_next_proxy(self) -> str | None:
        for _ in range(len(self._client_keys)):
            proxy_key = next(self._proxy_cycle)
            if time.time() >= self._proxy_cooldown[proxy_key]: return proxy_key
        return None

    def _mark_failure(self, proxy_key: str | None):
        self._proxy_failures[proxy_key] += 1
        backoff = min(60, 2 ** self._proxy_failures[proxy_key])
        self._proxy_cooldown[proxy_key] = time.time() + backoff
        logger.warning("Proxy %s failed (%d times). Cooling down for %ds.", proxy_key, self._proxy_failures[proxy_key], backoff)

    def _mark_success(self, proxy_key: str | None):
        self._proxy_failures[proxy_key] = 0
        self._proxy_cooldown[proxy_key] = 0

    async def _fetch(self, url, timeout=10, proxy_key=None):
        if proxy_key is None: proxy_key = self._get_next_proxy()
        client = self.client_map[proxy_key]
        if proxy_key: logger.debug(f"...{proxy_key[-20:]}, URL: {url}")
        else: logger.debug(f"Fetching URL: {url}")
        try:
            response = await client.get(url, headers=self._headers(), timeout=timeout)
            response.raise_for_status()
            self._mark_success(proxy_key)
            return response.text
        except Exception as e:
            self._mark_failure(proxy_key)
            raise logger.error("Error fetching URL %s: %s", url, e)

    async def get_job_list(self, query_params):

        async with self.semaphore:
            await asyncio.sleep(random.randint(self.delay["min_val"], self.delay["max_val"]))
            url = f"{self.BASE_LIST_URL}?{urlencode(query_params)}"
            try:
                return await self._fetch(url, timeout=10)
            except Exception as e:
                logger.error("Error fetching job list for URL %s: %s", url, e)
                return None

    async def get_job_details(self, job_id):
        async with self.semaphore:
            await asyncio.sleep(random.randint(self.delay["min_val"], self.delay["max_val"]))
            url = self.BASE_DETAILS_URL.format(job_id=job_id)
            try:
                return await self._fetch(url, timeout=5)
            except Exception as e:
                logger.warning("Could not fetch job details for ID %s: %s", job_id, e)
                return {"error": str(e)}

    async def close(self):
        logger.debug(f"Closing {len(self.client_map)} client instance(s)...")
        tasks = [client.aclose() for client in self.client_map.values()]
        await asyncio.gather(*tasks)
        logger.debug("All client instances closed.")