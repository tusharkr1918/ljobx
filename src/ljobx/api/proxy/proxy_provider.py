from abc import ABC, abstractmethod
from typing import List

class ProxyProvider(ABC):
    """
    Abstract base class for proxy providers.

    This class defines the standard interface for all proxy provider implementations.
    Each concrete provider (e.g., WebshareProvider) must implement methods to fetch
    proxies and close any associated resources.

    :param api_key: API key required to access the provider.
    """
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required")
        self.api_key = api_key

    @abstractmethod
    async def get_proxies(self) -> List[str]:
        """
        Fetch a list of proxies from the provider.

        :return: List of proxy URLs.
        """
        pass

    @abstractmethod
    async def close(self):
        """
        Close any resources or sessions used by the provider.
        """
        pass
