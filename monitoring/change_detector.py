
import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

BASELINE_FILE = (
    BASE_DIR
    / "artifacts"
    / "snapshots"
    / "baseline"
    / "ayksa_baseline.json"
)

DISCOVERY_DIR = (
    BASE_DIR
    / "artifacts"
    / "discovery_results"
)

REPORT_DIR = (
    BASE_DIR
    / "artifacts"
    / "reports"
    / "change_detection"
)


class ChangeDetector:

    def __init__(self):

        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

    def load_json(self, file_path):

        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {file_path}"
            )

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    def find_latest_discovery(self):

        reports = list(
            DISCOVERY_DIR.glob("ayksa_discovery_*.json")
        )

        if not reports:
            raise FileNotFoundError(
                "No discovery reports available."
            )

        return max(
            reports,
            key=lambda file: file.stat().st_mtime
        )

    def normalize_elements(self, page_data):

        elements = []

        categories = [
            ("button", "buttons"),
            ("navigation", "roleButtons"),
            ("link", "links"),
            ("input", "inputs"),
            ("heading", "headings"),
        ]

        for element_type, field in categories:

            for item in page_data.get(field, []):

                text = " ".join(
                    str(item.get("text", "")).split()
                )

                aria_label = (
                    item.get("ariaLabel") or ""
                )

                role = item.get("role") or ""

                tag = item.get("tag") or ""

                identity = (
                    element_type,
                    text,
                    aria_label,
                    role,
                    tag
                )

                elements.append({

                    "type": element_type,

                    "text": text,

                    "aria_label": aria_label,

                    "role": role,

                    "tag": tag,

                    "identity": identity,

                    "details": {
                        "text": text,
                        "aria_label": aria_label,
                        "role": role,
                        "tag": tag,
                        "disabled": item.get("disabled", False),
                        "href": item.get("href")
                    }
                })

        # Include table structure as a separate element.
        for index, table in enumerate(
            page_data.get("tables", [])
        ):

            headers = table.get("headers", [])

            elements.append({

                "type": "table",

                "text": f"Table {index + 1}",

                "aria_label": "",

                "role": "",

                "tag": "TABLE",

                "identity": (
                    "table",
                    index,
                    tuple(headers)
                ),

                "details": {
                    "headers": headers,
                    "row_count": table.get("rowCount", 0)
                }
            })

        return elements

    def compare_page(self, baseline_page, latest_page):

        baseline_data = baseline_page.get("data", {})
        latest_data = latest_page.get("data", {})

        old_elements = self.normalize_elements(
            baseline_data
        )

        new_elements = self.normalize_elements(
            latest_data
        )

        old_map = {
            item["identity"]: item
            for item in old_elements
        }

        new_map = {
            item["identity"]: item
            for item in new_elements
        }

        old_keys = set(old_map.keys())
        new_keys = set(new_map.keys())

        added = []
        removed = []
        modified = []

        for identity in new_keys - old_keys:

            added.append(
                new_map[identity]["details"]
            )

        for identity in old_keys - new_keys:

            removed.append(
                old_map[identity]["details"]
            )

        # Check whether matching elements changed.
        for identity in old_keys & new_keys:

            old_details = old_map[identity]["details"]
            new_details = new_map[identity]["details"]

            if old_details != new_details:

                modified.append({

                    "before": old_details,

                    "after": new_details
                })

        # Check page heading changes.
        old_title = baseline_data.get("title", "")
        new_title = latest_data.get("title", "")

        page_title_changed = old_title != new_title

        return {

            "page_name": baseline_page.get("page_name"),

            "url": latest_page.get("url"),

            "added_elements": added,

            "removed_elements": removed,

            "modified_elements": modified,

            "page_title_changed": page_title_changed,

            "old_page_title": old_title,

            "new_page_title": new_title,

            "added_count": len(added),

            "removed_count": len(removed),

            "modified_count": len(modified)
        }

    def run_comparison(self):

        print("\n" + "=" * 65)
        print("AYKSA UI CHANGE DETECTION ENGINE")
        print("=" * 65)

        # Load baseline.
        baseline = self.load_json(
            BASELINE_FILE
        )

        # Find latest discovery report.
        latest_file = self.find_latest_discovery()

        print("\nBASELINE:")
        print(BASELINE_FILE)

        print("\nLATEST DISCOVERY:")
        print(latest_file)

        latest = self.load_json(
            latest_file
        )

        baseline_pages = {
            page.get("page_name"): page
            for page in baseline.get("pages", [])
        }

        latest_pages = {
            page.get("page_name"): page
            for page in latest.get("pages", [])
        }

        results = []

        for page_name, latest_page in latest_pages.items():

            if page_name not in baseline_pages:

                results.append({

                    "page_name": page_name,

                    "status": "NEW_PAGE",

                    "added_elements": [],

                    "removed_elements": [],

                    "modified_elements": []
                })

                continue

            comparison = self.compare_page(
                baseline_pages[page_name],
                latest_page
            )

            results.append(comparison)

        # Detect pages missing from the latest discovery.
        for page_name in baseline_pages:

            if page_name not in latest_pages:

                results.append({

                    "page_name": page_name,

                    "status": "NOT_DISCOVERED",

                    "added_elements": [],

                    "removed_elements": [],

                    "modified_elements": []
                })

        total_added = sum(
            page.get("added_count", 0)
            for page in results
        )

        total_removed = sum(
            page.get("removed_count", 0)
            for page in results
        )

        total_modified = sum(
            page.get("modified_count", 0)
            for page in results
        )

        new_pages = sum(
            1 for page in results
            if page.get("status") == "NEW_PAGE"
        )

        missing_pages = sum(
            1 for page in results
            if page.get("status") == "NOT_DISCOVERED"
        )

        report = {

            "application": "AYKSA",

            "comparison_time": datetime.now().isoformat(),

            "baseline_file": str(BASELINE_FILE),

            "latest_discovery_file": str(latest_file),

            "summary": {

                "pages_in_baseline": len(baseline_pages),

                "pages_in_latest_discovery": len(latest_pages),

                "new_pages": new_pages,

                "not_discovered_pages": missing_pages,

                "added_elements": total_added,

                "removed_elements": total_removed,

                "modified_elements": total_modified
            },

            "page_results": results
        }

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        report_file = (
            REPORT_DIR
            / f"ayksa_change_report_{timestamp}.json"
        )

        with open(
            report_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                report,
                file,
                indent=4,
                ensure_ascii=False
            )

        self.print_results(report)

        print("\nREPORT SAVED:")
        print(report_file)

        return report

    def print_results(self, report):

        summary = report["summary"]

        print("\n" + "=" * 65)
        print("CHANGE DETECTION SUMMARY")
        print("=" * 65)

        print(
            "Pages in baseline:",
            summary["pages_in_baseline"]
        )

        print(
            "Pages in latest discovery:",
            summary["pages_in_latest_discovery"]
        )

        print(
            "New pages:",
            summary["new_pages"]
        )

        print(
            "Pages not discovered:",
            summary["not_discovered_pages"]
        )

        print(
            "Added elements:",
            summary["added_elements"]
        )

        print(
            "Removed elements:",
            summary["removed_elements"]
        )

        print(
            "Modified elements:",
            summary["modified_elements"]
        )

        for page in report["page_results"]:

            print("\nPAGE:", page["page_name"])

            if page.get("status"):
                print("Status:", page["status"])

            for item in page.get("added_elements", []):

                print(
                    "[ADDED]",
                    item.get("type"),
                    item.get("text")
                )

            for item in page.get("removed_elements", []):

                print(
                    "[REMOVED]",
                    item.get("type"),
                    item.get("text")
                )

            for item in page.get("modified_elements", []):

                print(
                    "[MODIFIED]",
                    item["before"],
                    "=>",
                    item["after"]
                )


if __name__ == "__main__":

    detector = ChangeDetector()

    try:

        detector.run_comparison()

    except Exception as error:

        print("\nCHANGE DETECTION FAILED")
        print("Reason:", error)
