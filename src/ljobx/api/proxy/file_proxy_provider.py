# src/ljobx/api/proxy/file_proxy_provider.py

from typing import List, Dict
import re
import logging
from .proxy_provider import ProxyProvider

log = logging.getLogger(__name__)

# Regex to check if a string starts with a protocol like 'http://'
PROTOCOL_REGEX = re.compile(r"^[a-zA-Z0-9]+://")

class FileProxyProvider(ProxyProvider):
    """
    Loads proxies from local files based on a structured configuration.
    Can prepend a default protocol and filter out proxies with non-matching protocols.
    """
    def __init__(self, file_configs: List[Dict[str, str]]):
        super().__init__()
        if not isinstance(file_configs, list):
            raise ValueError("file_configs must be a list of dictionaries.")
        self.file_configs = file_configs
        log.debug(f"FileProxyProvider initialized with {len(self.file_configs)} file configuration(s).")

    async def get_proxies(self) -> List[str]:
        """
        Reads proxies from files, applying protocol logic as configured.
        """
        proxies: List[str] = []
        for config in self.file_configs:
            path = config.get("path")
            default_protocol = config.get("protocol")

            if not path:
                log.warning(f"Skipping file config due to missing 'path' key: {config}")
                continue

            try:
                with open(path, 'r') as f:
                    proxies_added = 0
                    for line in f:
                        proxy = line.strip()
                        if not proxy or proxy.startswith('#'):
                            continue

                        if proxy.lower().startswith("http://"):
                            log.debug(f"Skipping insecure http:// proxy from '{path}': '{proxy}'.")
                            continue

                        has_protocol = PROTOCOL_REGEX.match(proxy)

                        if has_protocol:
                            # The proxy in the file already has a protocol.
                            if default_protocol and not proxy.startswith(default_protocol + "://"):
                                log.debug(f"Skipping proxy from '{path}': '{proxy}' has a non-matching protocol.")
                                continue
                            proxies.append(proxy)
                            proxies_added += 1
                        else:
                            if default_protocol:
                                new_proxy = f"{default_protocol}://{proxy}"
                                proxies.append(new_proxy)
                                proxies_added += 1
                            else:
                                log.warning(f"Skipping proxy from '{path}': '{proxy}' has no protocol and no default was provided.")
                    log.debug(f"Loaded {proxies_added} proxies from '{path}'.")
            except FileNotFoundError:
                log.warning(f"Proxy file not found: '{path}'. Skipping.")
            except Exception as e:
                log.error(f"Error reading proxy file '{path}': {e}")
        return proxies

    async def close(self):
        """No resources to close for the file provider."""
        log.debug("FileProxyProvider has no active resources to close.")
        pass