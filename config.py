
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

AYKSA_ENVIRONMENT = os.getenv(
    "AYKSA_ENVIRONMENT",
    "development"
)

AYKSA_BASE_URL = os.getenv(
    "AYKSA_BASE_URL",
    ""
)

AYKSA_DASHBOARD_URL = os.getenv(
    "AYKSA_DASHBOARD_URL",
    AYKSA_BASE_URL
)

BROWSER_TIMEOUT = int(
    os.getenv("BROWSER_TIMEOUT", "30000")
)

MAX_DISCOVERY_PAGES = int(
    os.getenv("MAX_DISCOVERY_PAGES", "15")
)

ARTIFACT_DIR = BASE_DIR / "artifacts"

SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"

RESULT_DIR = ARTIFACT_DIR / "discovery_results"

PROFILE_DIR = ARTIFACT_DIR / "browser_profile"

for folder in [
    SCREENSHOT_DIR,
    RESULT_DIR,
    PROFILE_DIR
]:
    folder.mkdir(parents=True, exist_ok=True)
