import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import AYKSA_DASHBOARD_URL


EXECUTION_REPORT_DIR = (
    BASE_DIR / "artifacts" / "reports" / "execution"
)
BUG_ANALYSIS_DIR = (
    BASE_DIR / "artifacts" / "reports" / "bug_analysis"
)
PRIORITY_REPORT_DIR = (
    BASE_DIR / "artifacts" / "reports" / "prioritized_tests"
)

AYKSA_MODULES = [
    "EMS",
    "Manager Dashboard",
    "Leave Management",
    "Route Management",
    "Field Executive",
    "Reimbursement",
    "HR",
    "Communication",
    "DOA",
    "Certificate Download",
    "Other / Unmapped",
]

MODULE_PAGE_NAMES = {
    "manager dashboard": "Manager Dashboard",
    "employee dashboard": "Manager Dashboard",
    "leave management": "Leave Management",
    "leave management overview": "Leave Management",
    "leave requests": "Leave Management",
    "holiday calendar": "Leave Management",
    "leave policies": "Leave Management",
    "leave types": "Leave Management",
    "route management": "Route Management",
    "field executive": "Field Executive",
    "reimbursement": "Reimbursement",
    "hr": "HR",
    "communication": "Communication",
    "doa": "DOA",
    "certificate download": "Certificate Download",
    "ems": "EMS",
}

LOCATOR_ERROR_PATTERNS = (
    "multiple visible controls",
    "no visible control",
    "not uniquely identified",
    "strict mode violation",
    "locator",
)

EXECUTION_ERROR_PATTERNS = (
    "timeout",
    "timed out",
    "target closed",
    "browser has been closed",
    "navigation failed",
    "net::err_",
    "connection",
)


class AYKSAFailureAnalysisAgent:
    """Classify execution failures and prepare a module-oriented QA report."""

    def __init__(self, execution_report=None):
        self.execution_report = Path(execution_report) if execution_report else None

    @staticmethod
    def find_latest_execution_report():

        reports = list(
            EXECUTION_REPORT_DIR.glob("ayksa_execution_*.json")
        )

        if not reports:
            raise FileNotFoundError(
                f"No execution reports found in {EXECUTION_REPORT_DIR}"
            )

        return max(
            reports,
            key=lambda report: report.stat().st_mtime
        )

    def load_execution_report(self):

        report_path = self.execution_report or self.find_latest_execution_report()

        if not report_path.is_file():
            raise FileNotFoundError(
                f"Execution report does not exist: {report_path}"
            )

        with report_path.open("r", encoding="utf-8") as file:
            report = json.load(file)

        if not isinstance(report, dict):
            raise ValueError("Execution report must contain a JSON object.")

        results = report.get("results")

        if not isinstance(results, list):
            raise ValueError(
                "Execution report must contain a 'results' list."
            )

        for index, result in enumerate(results, start=1):
            if not isinstance(result, dict):
                raise ValueError(
                    f"Execution result {index} must be a JSON object."
                )

        return report_path, report

    @staticmethod
    def find_test_catalog(execution_path, execution_report):

        source = execution_report.get(
            "source_prioritized_test_report"
        )

        if source:
            source_path = Path(source)

            if not source_path.is_absolute():
                source_path = BASE_DIR / source_path

            if source_path.is_file():
                return source_path

        reports = list(
            PRIORITY_REPORT_DIR.glob("ayksa_prioritized_tests_*.json")
        )
        reports = [
            report
            for report in reports
            if report.stat().st_mtime <= execution_path.stat().st_mtime
        ]

        if not reports:
            return None

        return max(
            reports,
            key=lambda report: report.stat().st_mtime
        )

    @staticmethod
    def load_test_catalog(catalog_path):

        if catalog_path is None:
            return []

        with catalog_path.open("r", encoding="utf-8") as file:
            catalog = json.load(file)

        test_cases = catalog.get("test_cases", [])

        if not isinstance(test_cases, list):
            raise ValueError(
                f"Test catalog must contain a 'test_cases' list: {catalog_path}"
            )

        return test_cases

    @staticmethod
    def resolve_module(page_name, module_name=None):

        normalized_module = " ".join(
            str(module_name or "").strip().lower().split()
        )

        for module in AYKSA_MODULES:
            if normalized_module == module.lower():
                return module

        normalized = " ".join(
            str(page_name or "").strip().lower().split()
        )

        if normalized in MODULE_PAGE_NAMES:
            return MODULE_PAGE_NAMES[normalized]

        for page, module in MODULE_PAGE_NAMES.items():
            if page in normalized:
                return module

        return "Other / Unmapped"

    @staticmethod
    def classify_failure(result):

        failure_type = str(
            result.get("failure_type") or ""
        ).strip().lower()
        message = str(result.get("message") or "")
        normalized_message = message.lower()

        if failure_type == "locator_failure" or any(
            pattern in normalized_message
            for pattern in LOCATOR_ERROR_PATTERNS
        ):
            return {
                "classification": "AUTOMATION_LOCATOR",
                "triage_status": "Fix or scope the test locator; not an established application bug",
                "confirmed_bug": False,
                "manual_reproduction_required": True,
            }

        if failure_type == "execution_error" or any(
            pattern in normalized_message
            for pattern in EXECUTION_ERROR_PATTERNS
        ):
            return {
                "classification": "EXECUTION_OR_ENVIRONMENT",
                "triage_status": "Check browser, network, session, or test-runner health first",
                "confirmed_bug": False,
                "manual_reproduction_required": True,
            }

        if failure_type == "ui_validation_failure":
            return {
                "classification": "POTENTIAL_UI_BEHAVIOR",
                "triage_status": "Potential application behavior issue; reproduce manually before logging as a bug",
                "confirmed_bug": False,
                "manual_reproduction_required": True,
            }

        return {
            "classification": "UNCLASSIFIED_FAILURE",
            "triage_status": "Insufficient evidence; review the test, screenshot, and page manually",
            "confirmed_bug": False,
            "manual_reproduction_required": True,
        }

    @staticmethod
    def suggested_severity(result, classification):

        if classification != "POTENTIAL_UI_BEHAVIOR":
            return "Unassigned"

        priority = str(
            result.get("priority")
            or result.get("calculated_priority")
            or ""
        ).strip().lower()

        if priority in {"critical", "high"}:
            return "High (suggested)"

        if priority == "medium":
            return "Medium (suggested)"

        if priority == "low":
            return "Low (suggested)"

        return "Unassigned"

    @staticmethod
    def reproduction_steps(result):

        page = str(result.get("page") or "the affected AYKSA page")
        test_title = str(result.get("title") or "the failed check")
        element_name = str(result.get("element_name") or "")
        expected = str(result.get("expected_result") or "")

        steps = [
            "Sign in using an authorized test account.",
            f"Open the {page} module/page using the normal application navigation.",
            f"Repeat the read-only check: {test_title}.",
        ]

        if element_name:
            steps.append(
                f"Inspect the visible control named '{element_name}' "
                "without activating it."
            )

        if expected:
            steps.append(f"Compare the observed UI with: {expected}")
        else:
            steps.append(
                "Compare the visible UI with the test description and "
                "record the exact observed result."
            )

        return steps

    @staticmethod
    def recurrence_key(finding):

        message = str(finding.get("observed_result") or "").lower()
        message = re.sub(r"https?://\S+", "<url>", message)
        message = re.sub(r"\bayksa-tc-\d+\b", "<test-id>", message)
        message = re.sub(r"\b\d+\b", "<number>", message)
        message = " ".join(message.split())

        return (
            finding["module"],
            finding["classification"],
            message or finding["title"].lower()
        )

    def analyze(
        self,
        report_path,
        execution_report,
        test_catalog=None
    ):

        catalog_by_test_id = {
            str(test.get("test_id")): test
            for test in test_catalog or []
            if isinstance(test, dict) and test.get("test_id") is not None
        }
        failures = [
            result
            for result in execution_report["results"]
            if str(result.get("status", "")).strip().upper() == "FAIL"
        ]

        grouped_findings = defaultdict(list)

        for execution_result in failures:
            catalog_case = catalog_by_test_id.get(
                str(execution_result.get("test_id")),
                {}
            )
            result = {
                **catalog_case,
                **execution_result,
            }
            module = self.resolve_module(
                result.get("page"),
                catalog_case.get("module")
            )
            triage = self.classify_failure(result)
            screenshot = result.get("screenshot")
            screenshot_path = Path(screenshot) if screenshot else None

            finding = {
                "finding_id": "",
                "test_id": result.get("test_id"),
                "module": module,
                "page": result.get("page"),
                "title": result.get("title"),
                "category": result.get("category"),
                "classification": triage["classification"],
                "triage_status": triage["triage_status"],
                "confirmed_bug": triage["confirmed_bug"],
                "manual_reproduction_required": triage[
                    "manual_reproduction_required"
                ],
                "suggested_severity": self.suggested_severity(
                    result,
                    triage["classification"]
                ),
                "test_priority": (
                    result.get("priority")
                    or result.get("calculated_priority")
                    or "Unassigned"
                ),
                "observed_result": result.get("message") or (
                    "The execution report has no failure message."
                ),
                "expected_result": result.get("expected_result"),
                "description": result.get("description"),
                "page_url": result.get("page_url"),
                "executed_at": result.get("executed_at"),
                "failure_type": result.get("failure_type"),
                "element_name": result.get("element_name"),
                "element_role": result.get("element_role"),
                "screenshot": screenshot,
                "screenshot_available": bool(
                    screenshot_path and screenshot_path.is_file()
                ),
                "screenshot_error": result.get("screenshot_error"),
                "reproduction_steps": self.reproduction_steps(result),
                "related_finding_ids": [],
            }

            grouped_findings[module].append(finding)

        execution_by_test_id = {
            str(result.get("test_id")): result
            for result in execution_report["results"]
            if result.get("test_id") is not None
        }

        ordered_findings = []

        for module in AYKSA_MODULES:
            ordered_findings.extend(grouped_findings.get(module, []))

        for index, finding in enumerate(ordered_findings, start=1):
            finding["finding_id"] = f"AYKSA-F-{index:04d}"

        recurrence_groups = defaultdict(list)

        for finding in ordered_findings:
            recurrence_groups[self.recurrence_key(finding)].append(finding)

        for related in recurrence_groups.values():
            if len(related) < 2:
                continue

            finding_ids = [
                finding["finding_id"]
                for finding in related
            ]

            for finding in related:
                finding["related_finding_ids"] = [
                    finding_id
                    for finding_id in finding_ids
                    if finding_id != finding["finding_id"]
                ]

        findings_by_test_id = {
            str(finding.get("test_id")): finding
            for finding in ordered_findings
            if finding.get("test_id") is not None
        }
        all_test_cases = []

        for test in test_catalog or []:
            if not isinstance(test, dict):
                continue

            test_id = str(test.get("test_id") or "")
            execution = execution_by_test_id.get(test_id)
            finding = findings_by_test_id.get(test_id)
            status = (
                str(execution.get("status") or "NOT EXECUTED").upper()
                if execution
                else "NOT EXECUTED"
            )

            all_test_cases.append({
                **test,
                "module": self.resolve_module(
                    test.get("page"),
                    test.get("module")
                ),
                "application_url": (
                    (execution.get("page_url") if execution else None)
                    or execution_report.get("application_url")
                    or AYKSA_DASHBOARD_URL
                ),
                "execution_status": status,
                "execution_message": (
                    execution.get("message") if execution else None
                ),
                "executed_at": (
                    execution.get("executed_at") if execution else None
                ),
                "page_url": (
                    (execution.get("page_url") if execution else None)
                    or test.get("page_url")
                ),
                "screenshot": (
                    execution.get("screenshot") if execution else None
                ),
                "screenshot_error": (
                    execution.get("screenshot_error") if execution else None
                ),
                "finding_id": (
                    finding.get("finding_id") if finding else None
                ),
                "finding_classification": (
                    finding.get("classification") if finding else None
                ),
                "triage_status": (
                    finding.get("triage_status") if finding else None
                ),
                "suggested_severity": (
                    finding.get("suggested_severity") if finding else None
                ),
                "confirmed_bug": (
                    finding.get("confirmed_bug", False) if finding else False
                ),
                "related_finding_ids": (
                    finding.get("related_finding_ids", []) if finding else []
                ),
                "finding_analysis": (
                    {
                        "finding_id": finding["finding_id"],
                        "classification": finding["classification"],
                        "triage_status": finding["triage_status"],
                        "confirmed_bug": finding["confirmed_bug"],
                        "suggested_severity": finding["suggested_severity"],
                        "observed_result": finding["observed_result"],
                        "expected_result": finding["expected_result"],
                        "description": finding["description"],
                        "page_url": finding["page_url"],
                        "failure_type": finding["failure_type"],
                        "executed_at": finding["executed_at"],
                        "reproduction_steps": finding["reproduction_steps"],
                        "screenshot": finding["screenshot"],
                        "screenshot_available": finding[
                            "screenshot_available"
                        ],
                        "related_finding_ids": finding[
                            "related_finding_ids"
                        ],
                    }
                    if finding
                    else None
                ),
            })

        classification_counts = Counter(
            finding["classification"]
            for finding in ordered_findings
        )
        coverage_by_module = {
            entry.get("module"): entry
            for entry in execution_report.get("module_coverage", [])
            if isinstance(entry, dict) and entry.get("module")
        }
        modules = []

        for module in AYKSA_MODULES:
            module_findings = grouped_findings.get(module, [])
            module_cases = [
                test
                for test in all_test_cases
                if test["module"] == module
            ]
            module_statuses = Counter(
                test["execution_status"]
                for test in module_cases
            )
            coverage = coverage_by_module.get(module, {})
            modules.append({
                "module": module,
                "coverage_status": coverage.get(
                    "status",
                    "not_recorded"
                ),
                "coverage_message": coverage.get("message"),
                "discovered_pages": coverage.get("page_count", 0),
                "total_test_cases": len(module_cases),
                "passed_checks": module_statuses["PASS"],
                "failed_checks": len(module_findings),
                "not_executed_checks": module_statuses["NOT EXECUTED"],
                "potential_ui_issues": sum(
                    finding["classification"] == "POTENTIAL_UI_BEHAVIOR"
                    for finding in module_findings
                ),
                "automation_locator_issues": sum(
                    finding["classification"] == "AUTOMATION_LOCATOR"
                    for finding in module_findings
                ),
                "execution_or_environment_issues": sum(
                    finding["classification"] == "EXECUTION_OR_ENVIRONMENT"
                    for finding in module_findings
                ),
                "finding_ids": [
                    finding["finding_id"]
                    for finding in module_findings
                ],
                "test_ids": [
                    test.get("test_id")
                    for test in module_cases
                ],
            })

        total_tests = execution_report.get(
            "total_tests",
            len(execution_report["results"])
        )
        catalog_path = self.find_test_catalog(
            report_path,
            execution_report
        )

        return {
            "application": execution_report.get("application", "AYKSA"),
            "analysis_generated_at": datetime.now().isoformat(),
            "source_execution_report": str(report_path),
            "application_url": (
                execution_report.get("application_url")
                or AYKSA_DASHBOARD_URL
            ),
            "source_test_catalog": str(catalog_path) if catalog_path else None,
            "execution_time": execution_report.get("execution_time"),
            "analysis_method": "Evidence-based rule triage; no failures are marked as confirmed bugs automatically.",
            "summary": {
                "total_tests": total_tests,
                "catalog_test_cases": len(all_test_cases),
                "passed": execution_report.get("passed"),
                "failed": len(failures),
                "potential_ui_issues": classification_counts[
                    "POTENTIAL_UI_BEHAVIOR"
                ],
                "automation_locator_issues": classification_counts[
                    "AUTOMATION_LOCATOR"
                ],
                "execution_or_environment_issues": classification_counts[
                    "EXECUTION_OR_ENVIRONMENT"
                ],
                "unclassified_failures": classification_counts[
                    "UNCLASSIFIED_FAILURE"
                ],
                "confirmed_bugs": 0,
                "manual_review_required": len(failures),
            },
            "browser_errors": execution_report.get("browser_errors", []),
            "modules": modules,
            "findings": ordered_findings,
            "test_cases": all_test_cases,
        }

    def run(self):

        report_path, execution_report = self.load_execution_report()
        catalog_path = self.find_test_catalog(
            report_path,
            execution_report
        )
        test_catalog = self.load_test_catalog(catalog_path)
        analysis = self.analyze(
            report_path,
            execution_report,
            test_catalog
        )

        from reports.bug_reporter import BugReportWriter

        output_files = BugReportWriter(BUG_ANALYSIS_DIR).write(analysis)

        print("\nAYKSA FAILURE ANALYSIS COMPLETE")
        print("Source report:", report_path)
        print("Tests:", analysis["summary"]["total_tests"])
        print("Failed checks:", analysis["summary"]["failed"])
        print("Potential UI issues:", analysis["summary"]["potential_ui_issues"])
        print(
            "Automation locator issues:",
            analysis["summary"]["automation_locator_issues"]
        )
        print("Confirmed bugs:", analysis["summary"]["confirmed_bugs"])
        print("\nModule summary")

        for module in analysis["modules"]:
            if module["failed_checks"]:
                print(
                    f"- {module['module']}: "
                    f"{module['failed_checks']} finding(s)"
                )

        print("\nReports")

        for output_file in output_files:
            print(output_file)

        return output_files


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Analyze the latest AYKSA Playwright execution report and "
            "create module-grouped, manually verifiable findings."
        )
    )
    parser.add_argument(
        "execution_report",
        nargs="?",
        help=(
            "Optional execution JSON file. When omitted, the latest "
            "AYKSA execution report is used."
        )
    )
    args = parser.parse_args()

    try:
        AYKSAFailureAnalysisAgent(args.execution_report).run()
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        print(f"\nFAILURE ANALYSIS FAILED: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
