from pathlib import Path
from dataclasses import dataclass, field
from typing import List
import platform
import platformdirs

# ----------------------------
# App constants
# ----------------------------
APP_NAME = "ljobx"

home = Path.home()

# ----------------------------
# Output directory (user-friendly)
# ----------------------------
BASE_OUTPUT_DIR = home / "Documents" / APP_NAME / "outputs"
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Logs directory (OS-standard)
# ----------------------------
if platform.system() == "Windows":
    LOG_DIR = Path(platformdirs.user_log_dir(APP_NAME))
elif platform.system() == "Darwin":  # macOS
    LOG_DIR = Path(platformdirs.user_log_dir(APP_NAME))
else:  # Linux / other
    LOG_DIR = Path(platformdirs.user_data_dir(APP_NAME)) / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "scraper.log"

# ----------------------------
# Dataclass for config
# ----------------------------
Seconds = int

@dataclass(frozen=True)
class Config:
    BASE_OUTPUT_DIR: Path = BASE_OUTPUT_DIR
    LOG_FILE: Path = LOG_FILE
    RAND_DELAY: Seconds = 5
    PROXIES: List[str] = field(default_factory=lambda: [
        # "http://102.177.176.109:80"
        # I may work on it later, this will work pretty good with our async requests
        # for now, let it be empty
    ])

config = Config()
