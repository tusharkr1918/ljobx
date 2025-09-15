
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
    """
    Handles all the network requests for the LinkedIn scraper using httpx,
    with round-robin proxy rotation and basic failover.
    """

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

        # Track proxy health (failures + cooldown)
        # If any proxy fails, it will be skipped for a while until it recovers
        # We decide it based on the number of failures and the time since the last failure
        # Additional, max cooling time is 60s even though it fails multiple times

        # None, is used as a fallback client when no proxies are provided
        # this happens when the all proxies are cooling down

        self._proxy_failures: Dict[str | None, int] = {k: 0 for k in self._client_keys}
        self._proxy_cooldown: Dict[str | None, float] = {k: 0 for k in self._client_keys}

    def _headers(self):
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get_next_proxy(self) -> str | None:
        """
        Round-robin selection, skipping proxies in cooldown.
        """
        for _ in range(len(self._client_keys)):
            proxy_key = next(self._proxy_cycle)
            if time.time() >= self._proxy_cooldown[proxy_key]:
                return proxy_key
        return None  # fallback if all are cooling down

    def _mark_failure(self, proxy_key: str | None):
        """
        Increment failure count and apply cooldown.
        """
        self._proxy_failures[proxy_key] += 1
        backoff = min(60, 2 ** self._proxy_failures[proxy_key])  # exponential backoff up to 60s
        self._proxy_cooldown[proxy_key] = time.time() + backoff
        logger.warning(
            "Proxy %s failed (%d times). Cooling down for %ds.",
            proxy_key,
            self._proxy_failures[proxy_key],
            backoff,
        )

    def _mark_success(self, proxy_key: str | None):
        """
        Reset failure counter on success.
        """
        self._proxy_failures[proxy_key] = 0
        self._proxy_cooldown[proxy_key] = 0

    async def _fetch_with_retry(self, url, attempts=3):
        for _ in range(attempts):
            proxy_key = self._get_next_proxy()
            try:
                return await self._fetch(url, proxy_key=proxy_key)
            except [httpx.HTTPStatusError, httpx.RequestError, httpx.ConnectError] as e:
                self._mark_failure(proxy_key)
                logger.debug("Proxy %s failed on retry: %s", proxy_key, e)
                continue
        return None

    async def _fetch(self, url, timeout=10, proxy_key=None):
        if proxy_key is None:
            proxy_key = self._get_next_proxy()
        client = self.client_map[proxy_key]

        if proxy_key:
            logger.debug(f"Fetching URL: {url} via proxy: ...{proxy_key[-20:]}")
        else:
            logger.debug(f"Fetching URL: {url}")

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
