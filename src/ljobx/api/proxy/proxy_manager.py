import httpx
import asyncio
from typing import Type, List

from .webshare import WebshareProvider
from .proxy_provider import ProxyProvider
from ljobx.utils.logger import get_logger

log = get_logger(__name__)

class ProxyRouter:
    _providers: dict[str, Type[ProxyProvider]] = {
        "webshare": WebshareProvider,
    }

    @classmethod
    def create_providers_from_config(cls, config_data: dict) -> List[ProxyProvider]:
        provider_configs = config_data.get("proxy_providers")
        if not isinstance(provider_configs, list):
            raise ValueError("Config must contain a 'proxy_providers' key with a list.")

        initialized_providers = []
        for config in provider_configs:
            name = config.get("name")
            provider_cls = cls._providers.get(name.lower())
            if not provider_cls:
                raise ValueError(f"No provider found for '{name}'")

            provider_args = config.get("config", {})
            provider_instance = provider_cls(**provider_args)

            safe_provider_args = provider_args.copy()
            if 'api_key' in safe_provider_args:
                safe_provider_args['api_key'] = '**********'

            log.debug(f"Initialized provider '{name}' with config: {safe_provider_args}")
            initialized_providers.append(provider_instance)
        return initialized_providers

    @staticmethod
    async def _check_proxy(proxy: str, timeout: int = 5) -> str | None:
        test_url = "https://api.ipify.org"
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as client:
                resp = await client.get(test_url)
                resp.raise_for_status()
            log.debug(f"Proxy valid: {proxy}")
            return proxy
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            log.debug(f"Proxy invalid: {proxy} | Error: {e}")
            return None

    @classmethod
    async def _filter_valid_proxies(cls, proxies: List[str]) -> List[str]:
        log.info(f"Validating {len(proxies)} proxies...")
        tasks = [cls._check_proxy(p) for p in proxies]
        results = await asyncio.gather(*tasks)
        valid_proxies = [proxy for proxy in results if proxy is not None]
        log.info(f"Validation complete: {len(valid_proxies)} / {len(proxies)} proxies are valid.")
        return valid_proxies

    @classmethod
    async def get_proxies_from_config(cls, config_data: dict, validate: bool = True) -> List[str]:
        providers = cls.create_providers_from_config(config_data)
        if not providers:
            log.warning("No proxy providers initialized from config")
            return []

        log.info(f"Fetching proxies from {len(providers)} provider(s)...")
        fetch_tasks = [provider.get_proxies() for provider in providers]
        list_of_proxy_lists = await asyncio.gather(*fetch_tasks)

        close_tasks = [provider.close() for provider in providers]
        await asyncio.gather(*close_tasks)

        all_proxies = list(set(
            proxy for sublist in list_of_proxy_lists for proxy in sublist
        ))

        log.info(f"Found a total of {len(all_proxies)} unique proxies.")
        if validate:
            return await cls._filter_valid_proxies(all_proxies)
        log.warning("Proxy validation is disabled, skipping validation...")
        return all_proxies

