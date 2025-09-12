import httpx
import asyncio
from typing import Type, List

from .webshare_provider import WebshareProvider
from .proxy_provider import ProxyProvider
from ljobx.utils.logger import get_logger

log = get_logger(__name__)

class ProxyManager:
    """
    A class to manage multiple proxy providers, fetch proxies, and optionally validate them.

    :ivar _providers: Mapping of provider names to their classes.
    """

    _providers: dict[str, Type[ProxyProvider]] = {
        "webshare": WebshareProvider,
    }


    @classmethod
    def create_providers_from_config(cls, config_data: dict) -> List[ProxyProvider]:
        """
        Initialize proxy provider instances from configuration.

        :param config_data: Should contain 'proxy_providers', a list of provider configs.
        :return: List of initialized provider instances.
        :raises ValueError: If config is invalid or provider name is unknown.
        """

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
        """
        Check if a proxy is valid by sending a test request.

        :param proxy: Proxy URL to test.
        :param timeout: Request timeout in seconds. Defaults to 5.
        :return: The proxy if valid, otherwise None.
        """

        test_url = "https://api.ipify.org"

        # This looks bs and kinda time-consuming, but I don't know any other way
        # to validate proxies. Although, I have made it flag-based, if needed one
        # can disable validating proxies from proxy configuration file as
        # validate_proxies: false

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
        """
        Filter a list of proxies to include only valid ones.

        :param proxies: List of proxy URLs.
        :return: List containing only valid proxies.
        """

        log.info(f"Validating {len(proxies)} proxies...")
        tasks = [cls._check_proxy(p) for p in proxies]
        results = await asyncio.gather(*tasks)
        valid_proxies = [proxy for proxy in results if proxy is not None]
        log.info(f"Validation complete: {len(valid_proxies)} / {len(proxies)} proxies are valid.")
        return valid_proxies

    @classmethod
    async def get_proxies_from_config(cls, config_data: dict, validate: bool = True) -> List[str]:
        """
        Fetch proxies from all configured providers and optionally validate them.

        :param config_data: Configuration with proxy provider information.
        :param validate: If True, return only valid proxies. Defaults to True.
        :return: List of unique proxies (validated if requested).
        """

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

