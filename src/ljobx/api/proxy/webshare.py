from .proxy_provider import ProxyProvider
from typing import List
import httpx
from urllib.parse import urlparse
from ljobx.utils.logger import get_logger

log = get_logger(__name__)

class WebshareProvider(ProxyProvider):
    def __init__(self, api_key: str, page_size: int = 100):
        super().__init__(api_key)
        self.page_size = page_size
        self.client = httpx.AsyncClient()
        log.debug(f"WebshareProvider initialized with page_size={self.page_size}")

    async def get_proxies(self) -> List[str]:
        url = f"https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size={self.page_size}"
        headers = {"Authorization": f"Token {self.api_key}"}
        log.debug(f"Fetching proxies from {url}")

        try:
            resp = await self.client.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            proxies = [
                f"socks5://{item['username']}:{item['password']}@{item['proxy_address']}:{item['port']}"
                for item in data.get("results", [])
            ]
            log.info(f"Fetched {len(proxies)} proxies from {urlparse(url).hostname}" )
            return proxies

        except httpx.HTTPError as e:
            log.error(f"Error fetching proxies: {e}")
            return []

    async def close(self):
        await self.client.aclose()
        log.debug("HTTP client closed")
