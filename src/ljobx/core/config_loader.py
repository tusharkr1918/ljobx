# config_loader.py

import yaml
import httpx

class ConfigLoader:
    @staticmethod
    def load(path_or_url: str) -> dict:
        """
        Loads a YAML configuration from a file path, a URL, or a raw string.
        """
        config_text = ""
        # Check if it's a URL
        if path_or_url.lower().startswith(('http://', 'https://')):
            try:
                response = httpx.get(path_or_url, follow_redirects=True)
                response.raise_for_status()
                config_text = response.text
            except httpx.RequestError as e:
                raise ValueError(f"Failed to fetch YAML from URL: {e}")
        # Check if it's raw YAML content (contains newlines)
        elif '\n' in path_or_url:
            config_text = path_or_url
        # Assume it's a file path
        else:
            try:
                with open(path_or_url, 'r') as f:
                    config_text = f.read()
            except FileNotFoundError:
                raise ValueError(f"Config file not found: '{path_or_url}'")

        try:
            return yaml.safe_load(config_text)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML content: {e}")