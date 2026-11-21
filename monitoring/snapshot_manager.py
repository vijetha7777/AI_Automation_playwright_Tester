
import json
import shutil
from datetime import datetime
from pathlib import Path


# Project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Source discovery reports
DISCOVERY_DIR = BASE_DIR / "artifacts" / "discovery_results"

# Baseline storage
SNAPSHOT_DIR = BASE_DIR / "artifacts" / "snapshots"
BASELINE_DIR = SNAPSHOT_DIR / "baseline"

BASELINE_FILE = BASELINE_DIR / "ayksa_baseline.json"
BASELINE_SOURCE_FILE = BASELINE_DIR / "source_discovery_report.json"


class SnapshotManager:

    def __init__(self):

        DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    def find_latest_discovery_report(self):

        reports = list(
            DISCOVERY_DIR.glob("ayksa_discovery_*.json")
        )

        if not reports:
            raise FileNotFoundError(
                "No AYKSA discovery reports found."
            )

        # Most recently modified report
        latest_report = max(
            reports,
            key=lambda file: file.stat().st_mtime
        )

        return latest_report

    def create_baseline(self):

        print("\n" + "=" * 60)
        print("AYKSA BASELINE SNAPSHOT ENGINE")
        print("=" * 60)

        # Find latest discovery report
        source_file = self.find_latest_discovery_report()

        print("\nLatest discovery report:")
        print(source_file)

        # Read discovery JSON
        with open(
            source_file,
            "r",
            encoding="utf-8"
        ) as file:

            discovery_data = json.load(file)

        pages = discovery_data.get("pages", [])

        if not pages:
            raise ValueError(
                "Discovery report contains no page records."
            )

        # Create baseline structure
        baseline_data = {

            "application": "AYKSA",

            "snapshot_type": "baseline",

            "created_at": datetime.now().isoformat(),

            "source_report": source_file.name,

            "total_pages": len(pages),

            "pages": pages
        }

        # Save baseline JSON
        with open(
            BASELINE_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                baseline_data,
                file,
                indent=4,
                ensure_ascii=False
            )

        # Preserve a copy of the original report
        shutil.copy2(
            source_file,
            BASELINE_SOURCE_FILE
        )

        print("\n" + "=" * 60)
        print("BASELINE CREATED SUCCESSFULLY")
        print("=" * 60)

        print("Application:", baseline_data["application"])
        print("Total pages:", baseline_data["total_pages"])
        print("Source report:", source_file.name)
        print("Baseline file:", BASELINE_FILE)
        print("Source copy:", BASELINE_SOURCE_FILE)

        print("\nCaptured pages:")

        for page in pages:

            print(
                "-",
                page.get("page_name", "Unknown page")
            )

        return BASELINE_FILE


if __name__ == "__main__":

    manager = SnapshotManager()

    try:
        manager.create_baseline()

    except Exception as error:

        print("\nBASELINE CREATION FAILED")
        print("Reason:", error)
