from __future__ import annotations
import asyncio
import httpx
import random
import time
import itertools
import logging
from typing import Dict, List, Optional
from urllib.parse import urlencode
from fake_useragent import UserAgent
from dataclasses import dataclass

# --- Configure basic logging for demonstration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AllProxiesFailedError(Exception):
    """Custom exception raised when all proxies fail for a request."""
    pass

class LinkedInClient:
    """
    An efficient and resilient async HTTP client for LinkedIn,
    optimized for handling large proxy pools with lazy client initialization.
    """
    BASE_LIST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    BASE_DETAILS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    @dataclass(slots=True)
    class _ProxyState:
        """A simple data class to hold the state of each proxy."""
        address: Optional[str]
        failures: int = 0
        cooldown_until: float = 0.0

    def __init__(
            self,
            concurrency_limit: int = 5,
            delay: Optional[Dict[str, int]] = None,
            proxies: Optional[List[str]] = None,
            max_retries_per_request: int = 10,
    ):
        self.concurrency_limit = concurrency_limit
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.delay = delay or {"min_val": 0, "max_val": 0}
        self.ua = UserAgent()
        self.max_retries = max_retries_per_request

        # --- This dictionary will store our persistent clients, created on demand ---
        self._clients: Dict[Optional[str], httpx.AsyncClient] = {}

        if not proxies:
            self._proxies: List[LinkedInClient._ProxyState] = [self._ProxyState(address=None)]
        else:
            random.shuffle(proxies)
            self._proxies: List[LinkedInClient._ProxyState] = [self._ProxyState(address=p) for p in proxies]

        logger.info(f"Initialized with {len(self._proxies)} proxies. Clients will be created on demand.")
        self._proxy_cycle = itertools.cycle(self._proxies)

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def _get_next_available_proxy(self) -> Optional[LinkedInClient._ProxyState]:
        for _ in range(len(self._proxies)):
            proxy_state = next(self._proxy_cycle)
            if time.time() >= proxy_state.cooldown_until:
                return proxy_state
        return None

    @staticmethod
    def _mark_failure(proxy_state: LinkedInClient._ProxyState):
        proxy_state.failures += 1
        backoff_time = min(300, 2**proxy_state.failures)
        proxy_state.cooldown_until = time.time() + backoff_time
        logger.warning(
            f"Proxy {proxy_state.address} failed ({proxy_state.failures} times). "
            f"Cooldown for {backoff_time}s."
        )

    @staticmethod
    def _mark_success(proxy_state: LinkedInClient._ProxyState):
        if proxy_state.failures > 0:
            logger.info(f"Proxy {proxy_state.address} is working again. Resetting failure count.")
        proxy_state.failures = 0
        proxy_state.cooldown_until = 0

    async def _fetch_with_retries(self, url: str, timeout: int = 10) -> str:
        last_exception = None
        for attempt in range(self.max_retries):
            proxy_state = self._get_next_available_proxy()

            if proxy_state is None:
                logger.warning("All proxies are on cooldown. Waiting for 5 seconds...")
                await asyncio.sleep(5)
                continue

            try:
                # Get the client for this proxy, or create it if it doesn't exist.
                client = self._clients.get(proxy_state.address)
                if client is None or client.is_closed:
                    log_message = (
                        f"Creating client for proxy: {proxy_state.address}"
                        if proxy_state.address
                        else "Creating local client (no proxy)"
                    )
                    logger.info(log_message)

                    client = httpx.AsyncClient(proxy=proxy_state.address, follow_redirects=True)
                    self._clients[proxy_state.address] = client

                via_message = f"via {proxy_state.address}" if proxy_state.address else "via local IP"
                logger.debug(f"Attempt {attempt + 1}/{self.max_retries}: Fetching {url} {via_message}")

                response = await client.get(url, headers=self._headers(), timeout=timeout)
                response.raise_for_status()

                self._mark_success(proxy_state)
                return response.text

            except Exception as e:
                proxy_id = proxy_state.address if proxy_state.address else "local IP"
                logger.error(f"Attempt {attempt + 1} failed for {url} with proxy {proxy_id}: {e}")
                self._mark_failure(proxy_state)

        raise AllProxiesFailedError(
            f"Failed to fetch {url} after {self.max_retries} attempts. "
            f"Last error: {last_exception}"
        )

    async def get_job_list(self, params: Dict) -> str:
        async with self.semaphore:
            await asyncio.sleep(random.uniform(self.delay["min_val"], self.delay["max_val"]))
            url = f"{self.BASE_LIST_URL}?{urlencode(params)}"
            return await self._fetch_with_retries(url)

    async def get_job_details(self, job_id: str) -> str:
        async with self.semaphore:
            await asyncio.sleep(random.uniform(self.delay["min_val"], self.delay["max_val"]))
            url = self.BASE_DETAILS_URL.format(job_id=job_id)
            return await self._fetch_with_retries(url, timeout=5)

    async def close(self):
        """Gracefully close all created client sessions."""
        logger.info(f"Closing {len(self._clients)} client instance(s)...")
        tasks = [client.aclose() for client in self._clients.values()]
        await asyncio.gather(*tasks)
        logger.info("All client instances closed.")

# --- Example Usage (same as before) ---
async def main():
    # Using 'None' will test with your local IP.
    # Replace with your proxy list: proxies=["http://user:pass@host:port", ...]
    client = LinkedInClient(
        proxies=None,
        concurrency_limit=5,
        delay={"min_val": 1, "max_val": 3},
        max_retries_per_request=5
    )
    try:
        search_params = {
            "keywords": "Python Developer",
            "location": "Noida, Uttar Pradesh, India",
            "start": 0
        }
        print("Fetching job list...")
        job_list_html = await client.get_job_list(search_params)
        print(f"Successfully fetched job list (first 100 chars): {job_list_html[:100].strip()}...")
    except AllProxiesFailedError as e:
        print(f"A critical request failed after all retries: {e}")
    except httpx.ConnectError as e:
        print(f"Connection could not be established: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())