from pathlib import Path
from dataclasses import dataclass, field
from typing import List
import platform
import os

# ----------------------------
# App constants
# ----------------------------
APP_NAME = "ljobx"
home = Path.home()

# ----------------------------
# Base directory for logs and output
# ----------------------------
if platform.system() == "Windows":
    BASE_DIR = home / "Documents" / APP_NAME
else:
    BASE_DIR = home / APP_NAME

BASE_DIR.mkdir(parents=True, exist_ok=True)


if platform.system() == "Windows":
    # Use the %APPDATA% environment variable for the correct roaming path
    config_path_str = os.getenv('APPDATA', home)
    CONFIG_DIR = Path(config_path_str) / APP_NAME
else:
    CONFIG_DIR = home / ".config" / APP_NAME

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PROXY_CONFIG_PATH = CONFIG_DIR / "proxy_config.yml"

# ----------------------------
# Logs directory
# ----------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "scraper.log"


# ----------------------------
# Dataclass for config
# ----------------------------
Seconds = int

@dataclass(frozen=True)
class Config:
    BASE_DIR: Path = BASE_DIR
    LOG_FILE: Path = LOG_FILE
    DEFAULT_PROXY_CONFIG_PATH: Path = DEFAULT_PROXY_CONFIG_PATH
    RAND_DELAY: Seconds = 5
    PROXIES: List[str] = field(default_factory=list)

config = Config()