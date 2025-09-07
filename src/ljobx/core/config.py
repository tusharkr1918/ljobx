from pathlib import Path
from dataclasses import dataclass, field
from typing import List
import platform

# ----------------------------
# App constants
# ----------------------------
APP_NAME = "ljobx"
home = Path.home()

# ----------------------------
# Base directory
# ----------------------------
if platform.system() == "Windows":
    BASE_DIR = home / "Documents" / APP_NAME
else:
    BASE_DIR = home / APP_NAME

BASE_DIR.mkdir(parents=True, exist_ok=True)

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
    RAND_DELAY: Seconds = 5
    PROXIES: List[str] = field(default_factory=list)

config = Config()
