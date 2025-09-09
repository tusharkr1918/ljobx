from abc import ABC, abstractmethod
from typing import List

class ProxyProvider(ABC):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required")
        self.api_key = api_key

    @abstractmethod
    async def get_proxies(self) -> List[str]:
        pass

    @abstractmethod
    async def close(self):
        pass