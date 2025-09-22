# ljobx/api/proxy/webshare_provider.py

from .proxy_provider import ProxyProvider
from typing import List
import httpx
from urllib.parse import urlparse
from ljobx.utils.logger import get_logger

log = get_logger(__name__)

class WebshareProvider(ProxyProvider):
    """
    Concrete ProxyProvider implementation for webshare.io.

    Fetches proxies from the Webshare API and formats them as usable proxy URLs,
    with support for fetching multiple pages.

    :param api_key: API key for Webshare.io.
    :param page_size: Number of proxies to fetch per request. Defaults to 100.
    :param max_pages: The maximum number of pages to fetch. Defaults to 5.
    """

    def __init__(self, api_key: str, page_size: int = 100, max_pages: int = 5):
        if not api_key:
            raise ValueError("API key is required for WebshareProvider")
        super().__init__(api_key)
        self.page_size = page_size
        self.max_pages = max_pages
        self.client = httpx.AsyncClient()
        log.debug(
            f"WebshareProvider initialized with page_size={self.page_size}, max_pages={self.max_pages}"
        )

    async def get_proxies(self) -> List[str]:
        """
        Fetch a list of proxies from Webshare.io, iterating through pages.

        :return: List of proxies in the format socks5://username:password@host:port.
        :raises httpx.HTTPError: If an API request fails.
        """
        all_proxies = []
        headers = {"Authorization": f"Token {self.api_key}"}

        for page_num in range(1, self.max_pages + 1):
            url = f"https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page={page_num}&page_size={self.page_size}"
            log.debug(f"Fetching page {page_num}/{self.max_pages} from {urlparse(url).hostname}")

            try:
                resp = await self.client.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                page_proxies = data.get("results", [])
                if not page_proxies:
                    log.info(f"No more proxies found on page {page_num}. Stopping.")
                    break

                formatted_proxies = [
                    f"socks5://{item['username']}:{item['password']}@{item['proxy_address']}:{item['port']}"
                    for item in page_proxies
                ]
                all_proxies.extend(formatted_proxies)
                log.debug(f"Fetched {len(formatted_proxies)} proxies from page {page_num}.")

            except httpx.HTTPError as e:
                log.error(f"Error fetching proxies on page {page_num}: {e}")
                # Decide if you want to stop on error or continue to the next page.
                # For this implementation, we'll stop.
                break

        log.info(f"Fetched a total of {len(all_proxies)} proxies from Webshare.")
        return all_proxies

    async def close(self):
        """
        Close the internal HTTP client used to fetch proxies.

        This should be called when the provider is no longer needed to free up resources.
        """
        await self.client.aclose()
        log.debug("HTTP client closed")