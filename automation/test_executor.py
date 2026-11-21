
import argparse
import sys
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


# Project root
BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


from config import (
    AYKSA_DASHBOARD_URL,
    BROWSER_TIMEOUT,
    PROFILE_DIR,
    SCREENSHOT_DIR,
)


PRIORITY_DIR = (
    BASE_DIR / "artifacts" / "reports" / "prioritized_tests"
)

EXECUTION_REPORT_DIR = (
    BASE_DIR / "artifacts" / "reports" / "execution"
)

EXECUTION_REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

SCREENSHOT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


class LocatorResolutionError(Exception):
    """Raised when a requested visible control cannot be resolved uniquely."""


class UIValidationError(AssertionError):
    """Raised when a located UI element does not meet its expected state."""


class AYKSAAutonomousTestExecutor:

    def __init__(self):
        self.context = None
        self.page = None
        self.playwright = None
        self.test_cases = []
        self.results = []
        self.page_errors = []
        self.current_page_name = None
        self.test_report_path = None
        self.execution_report_path = None
        self.requested_report_path = None
        self.requested_test_id = None
        self.discovered_page_urls = {}
        self.module_coverage = []
        self.execution_run_id = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        self.child_sections = [
            "Leave Requests",
            "Holiday Calendar",
            "Leave Policies",
            "Leave Types"
        ]

    def find_latest_test_report(self):

        reports = list(
            PRIORITY_DIR.glob("ayksa_prioritized_tests_*.json")
        )

        if not reports:
            raise FileNotFoundError(
                "No prioritized test reports found."
            )

        return max(
            reports,
            key=lambda file: file.stat().st_mtime
        )

    def load_tests(self, report_file):

        self.test_report_path = Path(report_file).resolve()

        with open(report_file, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.test_cases = data.get("test_cases", [])
        self.module_coverage = data.get("module_coverage", [])
        self.discovered_page_urls = {
            str(test.get("page")): test.get("page_url")
            for test in self.test_cases
            if test.get("page") and test.get("page_url")
        }

        if not self.test_cases:
            raise ValueError("No test cases found.")

    def select_requested_test(self):

        if not self.requested_test_id:
            return

        selected_tests = [
            test
            for test in self.test_cases
            if str(test.get("test_id")) == self.requested_test_id
        ]

        if not selected_tests:
            raise ValueError(
                f"Test ID {self.requested_test_id!r} was not found "
                f"in {self.test_report_path}."
            )

        self.test_cases = selected_tests
        print("Running one selected test:", self.requested_test_id)

    async def start_browser(self):

        self.playwright = await async_playwright().start()

        self.context = (
            await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                viewport={"width": 1440, "height": 900},
                args=["--start-maximized"]
            )
        )

        self.page = (
            self.context.pages[0]
            if self.context.pages
            else await self.context.new_page()
        )

        self.page.set_default_timeout(BROWSER_TIMEOUT)

        self.page.on(
            "pageerror",
            lambda error: self.page_errors.append(str(error))
        )

        print("\nAYKSA browser session started.")

    async def verify_login(self):

        print("\nOPENING MANAGER DASHBOARD")

        await self.page.goto(
            AYKSA_DASHBOARD_URL,
            wait_until="domcontentloaded"
        )

        await self.page.wait_for_timeout(3000)

        if "/login" in self.page.url.lower():

            print("\nLOGIN REQUIRED")
            print("Log in manually using your authorized account.")

            await asyncio.to_thread(
                input,
                "Press ENTER after Manager Dashboard is visible..."
            )

            await self.page.wait_for_timeout(2000)

        if "/login" in self.page.url.lower():
            raise RuntimeError("Login was not completed.")

        if "/dashboard/employee-dashboard" not in self.page.url:
            raise RuntimeError(
                "Manager Dashboard URL could not be verified."
            )

        self.current_page_name = "Manager Dashboard"

        print("Dashboard verified:", self.page.url)

    @staticmethod
    def normalize_control_name(name):

        normalized = " ".join(str(name or "").split())

        return re.sub(
            r"^\d+\s+(?=\D)",
            "",
            normalized
        ).strip()

    @staticmethod
    def control_selector(role):

        selectors = {
            "button": "button, [role='button']",
            "link": "a[href], [role='link']",
            "tab": "[role='tab']",
            "menuitem": "[role='menuitem']"
        }

        if role not in selectors:
            raise ValueError(f"Unsupported interactive role: {role}")

        return selectors[role]

    async def visible_named_control(self, label, roles):

        exact_matches = []

        for role in roles:
            locator = self.page.get_by_role(
                role,
                name=label,
                exact=True
            )

            for index in range(await locator.count()):
                element = locator.nth(index)

                if await element.is_visible():
                    exact_matches.append(element)

        if len(exact_matches) == 1:
            return exact_matches[0]

        if len(exact_matches) > 1:
            raise LocatorResolutionError(
                f"Multiple visible controls have accessible name "
                f"{label!r} and role(s) {', '.join(roles)}."
            )

        selector = ", ".join(
            self.control_selector(role)
            for role in roles
        )
        controls = self.page.locator(selector)
        matches = []

        for index in range(await controls.count()):
            element = controls.nth(index)

            if not await element.is_visible():
                continue

            candidate_name = await element.get_attribute("aria-label")

            if not candidate_name:
                labelled_by = await element.get_attribute(
                    "aria-labelledby"
                )

                if labelled_by:
                    candidate_name = await element.evaluate(
                        """(element, ids) => ids
                            .split(/\\s+/)
                            .map(id => document.getElementById(id))
                            .filter(Boolean)
                            .map(label => label.innerText || label.textContent || "")
                            .join(" ")""",
                        labelled_by
                    )

            if not candidate_name:
                candidate_name = await element.evaluate(
                    """element => {
                        const clone = element.cloneNode(true);

                        clone.querySelectorAll(
                            '[aria-hidden="true"], .MuiBadge-badge, [class*="MuiBadge-badge"]'
                        ).forEach(child => child.remove());

                        return (
                            clone.innerText ||
                            clone.textContent ||
                            ""
                        ).replace(/\\s+/g, " ").trim();
                    }"""
                )

            if not candidate_name:
                candidate_name = await element.get_attribute("title")

            if (
                self.normalize_control_name(candidate_name).casefold()
                == self.normalize_control_name(label).casefold()
            ):
                matches.append(element)

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 1:
            raise LocatorResolutionError(
                f"Multiple visible controls match {label!r} "
                f"for role(s) {', '.join(roles)}."
            )

        raise LocatorResolutionError(
            f"No visible control named {label!r} was found "
            f"for role(s) {', '.join(roles)} on {self.page.url}."
        )

    async def return_to_leave_overview(self):

        back_button = await self.visible_named_control(
            "Back to leave management overview",
            ("button",)
        )

        await back_button.click()
        await self.page.wait_for_timeout(1200)

        await self.visible_named_control(
            "Open Leave Requests",
            ("button",)
        )

        self.current_page_name = "Leave Management Overview"

    async def navigate_to_page(self, page_name, page_url=None):

        overview_url = self.discovered_page_urls.get(
            "Leave Management Overview"
        )

        if (
            page_name in self.child_sections
            and page_url
            and overview_url
            and page_url.rstrip("/") == overview_url.rstrip("/")
            and self.current_page_name != page_name
        ):
            await self.navigate_to_page("Leave Management Overview")
            card = await self.visible_named_control(
                f"Open {page_name}",
                ("button",)
            )
            await card.click()
            await self.page.wait_for_timeout(1800)
            self.current_page_name = page_name
            return

        if page_url:
            target = urlparse(page_url)
            application = urlparse(AYKSA_DASHBOARD_URL)

            if (
                target.scheme not in {"http", "https"}
                or not target.netloc
                or target.netloc.casefold() != application.netloc.casefold()
            ):
                raise ValueError(
                    f"Discovered page URL is not on the configured AYKSA "
                    f"site: {page_url}"
                )

            if self.page.url != page_url:
                await self.page.goto(
                    page_url,
                    wait_until="domcontentloaded"
                )
                await self.page.wait_for_timeout(1200)

            if "/login" in self.page.url.lower():
                raise RuntimeError(
                    "Session expired while opening the discovered "
                    f"{page_name} page."
                )

            self.current_page_name = page_name
            return

        if self.current_page_name == page_name:
            return

        print("\nNAVIGATING TO:", page_name)

        if page_name == "Manager Dashboard":

            await self.page.goto(
                AYKSA_DASHBOARD_URL,
                wait_until="domcontentloaded"
            )

            await self.page.wait_for_timeout(2000)

            if "/login" in self.page.url.lower():
                raise RuntimeError("Session expired.")

            self.current_page_name = page_name
            return

        if page_name == "Leave Management Overview":

            if self.current_page_name in self.child_sections:
                await self.return_to_leave_overview()
                return

            sidebar = await self.visible_named_control(
                "Leave Management",
                ("button",)
            )

            await sidebar.click()
            await self.page.wait_for_timeout(2000)

            self.current_page_name = page_name
            return

        if page_name in self.child_sections:

            await self.navigate_to_page(
                "Leave Management Overview"
            )

            card = await self.visible_named_control(
                f"Open {page_name}",
                ("button",)
            )
            await card.click()
            await self.page.wait_for_timeout(1800)

            self.current_page_name = page_name
            return

        raise ValueError(
            f"Unsupported page: {page_name}"
        )

    async def check_page_navigation(self, test):

        body = await self.page.locator("body").inner_text()
        page_name = test.get("page", "")

        if page_name.casefold() not in body.casefold():
            raise UIValidationError(
                f"Page content not found: {page_name}"
            )

        return "Expected page content is visible."

    async def check_heading(self, test):

        heading = test["title"].replace(
            "Verify heading:", ""
        ).strip()

        locator = self.page.get_by_role(
            "heading",
            name=heading,
            exact=True
        )

        visible_headings = []

        for index in range(await locator.count()):
            element = locator.nth(index)

            if await element.is_visible():
                visible_headings.append(element)

        if visible_headings:
            return f"Heading is visible: {heading}"

        raise LocatorResolutionError(
            f"No visible heading named {heading!r} was found."
        )

    @staticmethod
    def test_element_name(test, prefix):

        name = test.get("element_name")

        if name:
            return name

        return test.get("title", "").replace(prefix, "", 1).strip()

    async def check_button(self, test):

        button_name = self.test_element_name(
            test,
            "Verify button:"
        )
        element = await self.visible_named_control(
            button_name,
            ("button",)
        )

        expected_disabled = test.get("expected_disabled")

        if expected_disabled is None:
            match = re.search(
                r"disabled state is (true|false)",
                test.get("expected_result", ""),
                re.IGNORECASE
            )

            if match:
                expected_disabled = match.group(1).lower() == "true"

        if expected_disabled is not None:
            aria_disabled = (
                await element.get_attribute("aria-disabled")
            )
            actual_disabled = (
                (aria_disabled or "").lower() == "true"
                or not await element.is_enabled()
            )

            if actual_disabled != bool(expected_disabled):
                raise UIValidationError(
                    f"Button {button_name!r} is visible but its disabled "
                    f"state is {actual_disabled}; expected "
                    f"{bool(expected_disabled)}."
                )

        return f"Button is visible: {button_name}"

    async def check_navigation(self, test):

        item_name = self.test_element_name(
            test,
            "Verify navigation item:"
        )
        role = test.get("element_role")
        role_groups = {
            "button": ("button",),
            "link": ("link",),
            "tab": ("tab",),
            "menuitem": ("menuitem",)
        }
        roles = role_groups.get(
            role,
            ("button", "link", "tab", "menuitem")
        )

        await self.visible_named_control(item_name, roles)

        return f"Navigation control is visible: {item_name}"

    async def check_input(self, _test):

        fields = self.page.locator(
            "input, textarea, select"
        )

        visible_count = 0

        for index in range(await fields.count()):
            if await fields.nth(index).is_visible():
                visible_count += 1

        if visible_count == 0:
            raise UIValidationError("No visible input fields were found.")

        page_name = _test.get("page") or "current page"

        return (
            f"Found {visible_count} visible input fields "
            f"on {page_name}."
        )

    async def check_table(self, test):

        title = test.get("title", "")

        column_match = re.search(
            r"Verify table column:\s*(.+)",
            title
        )

        if column_match:

            column_name = column_match.group(1).strip()
            headers = self.page.locator("table th")

            for index in range(await headers.count()):

                header = headers.nth(index)

                if not await header.is_visible():
                    continue

                text = " ".join(
                    (await header.inner_text()).split()
                )

                if text == column_name:
                    return f"Column visible: {column_name}"

            raise UIValidationError(
                f"Column not found: {column_name}"
            )

        table_match = re.search(
            r"Verify table\s+(\d+)",
            title
        )

        if not table_match:
            raise ValueError(
                f"Unrecognized table test: {title}"
            )

        table_number = int(table_match.group(1))

        tables = self.page.locator("table")
        visible_tables = []

        for index in range(await tables.count()):
            table = tables.nth(index)

            if await table.is_visible():
                visible_tables.append(table)

        if len(visible_tables) < table_number:
            raise UIValidationError(
                f"Table {table_number} not found."
            )

        return f"Table {table_number} is visible."

    async def execute_test(self, test):

        checks = {
            "Page Navigation": self.check_page_navigation,
            "Content Validation": self.check_heading,
            "Button Validation": self.check_button,
            "Navigation Validation": self.check_navigation,
            "Form Validation": self.check_input,
            "Table Validation": self.check_table
        }

        category = test.get("category", "")

        if category not in checks:
            raise ValueError(
                f"Unsupported category: {category}"
            )

        return await checks[category](test)

    async def record_result(
        self,
        test,
        status,
        message,
        screenshot=None,
        failure_type=None,
        screenshot_error=None
    ):

        result = {
            "test_id": test.get("test_id"),
            "page": test.get("page"),
            "page_url": self.page.url if self.page else None,
            "title": test.get("title"),
            "description": test.get("description"),
            "expected_result": test.get("expected_result"),
            "category": test.get("category"),
            "element_name": test.get("element_name"),
            "element_role": test.get("element_role"),
            "priority": (
                test.get("calculated_priority")
                or test.get("priority")
            ),
            "status": status,
            "message": message,
            "screenshot": screenshot,
            "executed_at": datetime.now().isoformat()
        }

        if failure_type:
            result["failure_type"] = failure_type

        if screenshot_error:
            result["screenshot_error"] = screenshot_error

        self.results.append(result)

    async def capture_test_screenshot(self, test_id, status):

        if not self.page:
            return None, "No active browser page was available for capture."

        safe_test_id = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            str(test_id)
        )
        screenshot_file = (
            SCREENSHOT_DIR
            / f"{self.execution_run_id}_{safe_test_id}_{status.lower()}.png"
        )

        try:
            await self.page.screenshot(
                path=str(screenshot_file),
                full_page=True
            )
        except Exception as error:
            return None, str(error)

        return str(screenshot_file), None

    async def run_tests(self):

        print("\nSTARTING READ-ONLY TEST EXECUTION")

        for index, test in enumerate(
            self.test_cases,
            start=1
        ):

            test_id = test.get("test_id", f"TEST-{index}")
            page_name = test.get("page", "Unknown")

            print("\n" + "-" * 55)
            print(f"TEST {index}/{len(self.test_cases)}")
            print("ID:", test_id)
            print("Page:", page_name)
            print("Title:", test.get("title"))

            try:

                await self.navigate_to_page(
                    page_name,
                    test.get("page_url")
                )

                message = await self.execute_test(test)

                print("RESULT: PASS")
                print(message)

                screenshot_path, screenshot_error = (
                    await self.capture_test_screenshot(
                        test_id,
                        "PASS"
                    )
                )
                if screenshot_error:
                    print("SCREENSHOT ERROR:", screenshot_error)

                await self.record_result(
                    test,
                    "PASS",
                    message,
                    screenshot=screenshot_path,
                    screenshot_error=screenshot_error
                )

            except Exception as error:

                print("RESULT: FAIL")
                print("DETAIL:", str(error))

                screenshot_path, screenshot_error = (
                    await self.capture_test_screenshot(
                        test_id,
                        "FAIL"
                    )
                )
                if screenshot_error:
                    print("SCREENSHOT ERROR:", screenshot_error)

                if isinstance(error, LocatorResolutionError):
                    failure_type = "locator_failure"
                elif isinstance(error, UIValidationError):
                    failure_type = "ui_validation_failure"
                else:
                    failure_type = "execution_error"

                await self.record_result(
                    test,
                    "FAIL",
                    str(error),
                    screenshot_path,
                    failure_type,
                    screenshot_error
                )

    def save_execution_report(self):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        passed = sum(
            result["status"] == "PASS"
            for result in self.results
        )

        failed = sum(
            result["status"] == "FAIL"
            for result in self.results
        )

        report = {
            "application": "AYKSA",
            "application_url": AYKSA_DASHBOARD_URL,
            "execution_time": datetime.now().isoformat(),
            "source_prioritized_test_report": (
                str(self.test_report_path)
                if self.test_report_path
                else None
            ),
            "module_coverage": self.module_coverage,
            "selected_test_ids": [
                result.get("test_id")
                for result in self.results
            ],
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "pass_percentage": round(
                passed / len(self.results) * 100,
                2
            ) if self.results else 0,
            "results": self.results,
            "browser_errors": self.page_errors
        }

        output_file = (
            EXECUTION_REPORT_DIR
            / f"ayksa_execution_{timestamp}.json"
        )

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                report,
                file,
                indent=4,
                ensure_ascii=False
            )

        print("\n" + "=" * 60)
        print("AYKSA EXECUTION SUMMARY")
        print("=" * 60)

        print("Total:", len(self.results))
        print("Passed:", passed)
        print("Failed:", failed)

        print(
            "Pass percentage:",
            report["pass_percentage"],
            "%"
        )

        print(
            "JavaScript errors:",
            len(self.page_errors)
        )

        print("\nReport:", output_file)
        self.execution_report_path = output_file
        return output_file

    async def run(self):

        report_file = (
            Path(self.requested_report_path)
            if self.requested_report_path
            else self.find_latest_test_report()
        )

        print("Prioritized report:", report_file)

        self.load_tests(report_file)

        self.select_requested_test()

        await self.start_browser()

        try:
            await self.verify_login()
            await self.run_tests()
            self.save_execution_report()

        finally:

            if self.context:
                await self.context.close()

            if self.playwright:
                await self.playwright.stop()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Execute AYKSA UI tests in a visible Playwright browser."
    )
    parser.add_argument(
        "--test-id",
        help="Execute only the specified test ID from the selected report."
    )
    parser.add_argument(
        "--report",
        help=(
            "Prioritized test JSON file. Defaults to the latest report."
        )
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help=(
            "After execution, create a new case-by-case failure analysis "
            "dashboard from that exact execution report."
        )
    )
    arguments = parser.parse_args()

    executor = AYKSAAutonomousTestExecutor()
    executor.requested_test_id = arguments.test_id
    executor.requested_report_path = arguments.report

    try:
        asyncio.run(executor.run())

        if arguments.analyze and executor.execution_report_path:
            from intelligence.failure_analysis_agent import (
                AYKSAFailureAnalysisAgent,
            )

            AYKSAFailureAnalysisAgent(
                executor.execution_report_path
            ).run()

    except Exception as error:
        print("\nAUTONOMOUS EXECUTION FAILED")
        print("Reason:", error)
