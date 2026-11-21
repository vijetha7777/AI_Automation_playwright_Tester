
import json
import re
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DISCOVERY_DIR = (
    BASE_DIR / "artifacts" / "discovery_results"
)

TEST_CASE_DIR = (
    BASE_DIR / "artifacts" / "reports" / "test_cases"
)

TEST_CASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# Actions that must not be executed automatically.
UNSAFE_KEYWORDS = [
    "delete",
    "remove",
    "approve",
    "reject",
    "submit",
    "apply",
    "add",
    "create",
    "save",
    "update",
    "cancel",
    "payment",
    "transfer",
    "request leave",
    "reset",
]

PAGE_MODULES = {
    "manager dashboard": "Manager Dashboard",
    "employee dashboard": "Manager Dashboard",
    "leave management overview": "Leave Management",
    "leave requests": "Leave Management",
    "holiday calendar": "Leave Management",
    "leave policies": "Leave Management",
    "leave types": "Leave Management",
    "ems": "EMS",
    "route management": "Route Management",
    "field executive": "Field Executive",
    "reimbursement": "Reimbursement",
    "hr": "HR",
    "communication": "Communication",
    "doa": "DOA",
    "certificate download": "Certificate Download",
}


class TestCaseGenerator:

    def __init__(self):
        self.test_cases = []
        self.counter = 0
        self.case_keys = set()
        self.navigation_case_keys = set()
        self.current_module_name = None
        self.current_page_url = None

    def find_latest_discovery(self):

        reports = list(
            DISCOVERY_DIR.glob("ayksa_discovery_*.json")
        )

        if not reports:
            raise FileNotFoundError(
                "No AYKSA discovery reports found."
            )

        return max(
            reports,
            key=lambda file: file.stat().st_mtime
        )

    def load_discovery(self, file_path):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    def next_test_id(self):

        self.counter += 1

        return f"AYKSA-TC-{self.counter:03d}"

    def is_sensitive_action(self, text):

        normalized = text.lower().strip()

        return any(
            keyword in normalized
            for keyword in UNSAFE_KEYWORDS
        )

    @staticmethod
    def normalize_text(text):

        return " ".join(
            str(text or "").split()
        )

    def element_name(self, element, navigation=False):

        if element.get("visible") is False or element.get("hidden") is True:
            return ""

        for key in ("accessibleName", "ariaLabel"):
            name = self.normalize_text(element.get(key))

            if name:
                return "" if name.isdigit() else name

        name = self.normalize_text(element.get("text"))

        if name.isdigit():
            name = ""

        if navigation and name:
            name = re.sub(r"^\d+\s+", "", name).strip()

        if not name:
            name = self.normalize_text(element.get("title"))

        return "" if name.isdigit() else name

    @staticmethod
    def element_role(element, default="button"):

        role = str(element.get("role") or "").strip().lower()

        if role in {"button", "link", "tab", "menuitem"}:
            return role

        tag = str(element.get("tag") or "").strip().lower()

        if tag == "a":
            return "link"

        return default

    @staticmethod
    def resolve_module_name(page, page_name):

        module_name = str(
            page.get("module_name") or ""
        ).strip()

        if module_name:
            return module_name

        normalized_page = " ".join(
            str(page_name or "").strip().lower().split()
        )

        if normalized_page in PAGE_MODULES:
            return PAGE_MODULES[normalized_page]

        for known_page, module in PAGE_MODULES.items():
            if known_page in normalized_page:
                return module

        return "Other / Unmapped"

    @staticmethod
    def resolve_navigation_module(name, current_module):

        normalized = " ".join(
            str(name or "").strip().lower().split()
        )

        if normalized.startswith("doa") or normalized in {
            "raise doa",
            "my doa",
        }:
            return "DOA"

        if normalized.startswith("certificate"):
            return "Certificate Download"

        if normalized in {"routes", "route", "live tracking"}:
            return "Route Management"

        if normalized.startswith("claim") or normalized in {
            "my claims",
            "manager claim approvals",
            "claim stats & history",
        }:
            return "Reimbursement"

        if normalized in {"team channels", "dm's", "communication"}:
            return "Communication"

        if normalized in {
            "hr dashboard",
            "employee management",
            "organization",
            "attendance",
            "policies & procedures",
            "employee policies",
            "configuration",
        }:
            return "HR"

        if normalized in {
            "leave requests",
            "leave management",
            "leave management overview",
            "holiday calendar",
            "leave policies",
            "leave types",
        }:
            return "Leave Management"

        if normalized in {
            "meeting & visits",
            "my partners",
            "my attendance",
            "my leaves",
            "my performance",
            "product catalogue",
            "purchase orders",
            "field executive",
        }:
            return "Field Executive"

        if normalized == "ems":
            return "EMS"

        if normalized == "manager dashboard":
            return "Manager Dashboard"

        return current_module

    def add_test_case(
        self,
        page_name,
        title,
        description,
        expected_result,
        category,
        priority="Medium",
        test_type="UI Validation",
        execution_mode="Read-only",
        element_name=None,
        element_role=None,
        expected_disabled=None,
        module_name=None,
        page_url=None
    ):

        key = (
            self.normalize_text(page_name).casefold(),
            category.casefold(),
            self.normalize_text(title).casefold()
        )

        if key in self.case_keys:
            return

        self.case_keys.add(key)

        test_case = {
            "test_id": self.next_test_id(),
            "page": page_name,
            "module": module_name or self.current_module_name,
            "page_url": page_url or self.current_page_url,
            "title": title,
            "description": description,
            "expected_result": expected_result,
            "category": category,
            "priority": priority,
            "test_type": test_type,
            "execution_mode": execution_mode,
            "status": "Not Executed"
        }

        if element_name is not None:
            test_case["element_name"] = element_name

        if element_role is not None:
            test_case["element_role"] = element_role

        if expected_disabled is not None:
            test_case["expected_disabled"] = expected_disabled

        self.test_cases.append(test_case)

    def generate_page_load_test(self, page_name):

        self.add_test_case(

            page_name=page_name,

            title=f"Verify {page_name} page loads",

            description=(
                f"Navigate to the {page_name} page "
                "using an authorized test session."
            ),

            expected_result=(
                "The requested page loads successfully "
                "and displays its expected content."
            ),

            category="Page Navigation",

            priority="High"
        )

    def generate_heading_tests(
        self,
        page_name,
        headings
    ):

        for heading in headings:

            heading_text = heading.get("text", "").strip()

            if not heading_text:
                continue

            self.add_test_case(

                page_name=page_name,

                title=f"Verify heading: {heading_text}",

                description=(
                    f"Check whether the heading "
                    f"'{heading_text}' is visible."
                ),

                expected_result=(
                    f"The heading '{heading_text}' "
                    "is displayed correctly."
                ),

                category="Content Validation",

                priority="Medium"
            )

    def generate_button_tests(
        self,
        page_name,
        buttons
    ):

        for button in buttons:

            text = self.element_name(button)

            if not text:
                continue

            if self.is_sensitive_action(text):
                continue

            disabled = button.get("disabled", False)

            self.add_test_case(

                page_name=page_name,

                title=f"Verify button: {text}",

                description=(
                    f"Verify that the '{text}' button is visible "
                    "and has its expected enabled state. "
                    "This check does not activate the button."
                ),

                expected_result=(
                    f"The '{text}' button is visible "
                    f"and its disabled state is {bool(disabled)}."
                ),

                category="Button Validation",

                priority="Medium",

                execution_mode="Read-only",
                element_name=text,
                element_role="button",
                expected_disabled=bool(disabled)
            )

    def generate_input_tests(
        self,
        page_name,
        inputs
    ):

        for index, field in enumerate(inputs, start=1):

            field_type = field.get("tag", "INPUT")

            field_name = (
                field.get("ariaLabel")
                or field.get("title")
                or field.get("name")
                or f"{field_type} field {index}"
            )

            self.add_test_case(

                page_name=page_name,

                title=f"Verify input field: {field_name}",

                description=(
                    f"Check whether the {field_name} "
                    "field is displayed and available."
                ),

                expected_result=(
                    "The input field is visible and "
                    "has the expected field type."
                ),

                category="Form Validation",

                priority="Medium"
            )

    def generate_table_tests(
        self,
        page_name,
        tables
    ):

        for index, table in enumerate(tables, start=1):

            headers = table.get("headers", [])

            self.add_test_case(

                page_name=page_name,

                title=f"Verify table {index} is displayed",

                description=(
                    f"Check whether table {index} "
                    "is present on the page."
                ),

                expected_result=(
                    "The table is displayed successfully "
                    "with its expected structure."
                ),

                category="Table Validation",

                priority="High"
            )

            for header in headers:

                self.add_test_case(

                    page_name=page_name,

                    title=f"Verify table column: {header}",

                    description=(
                        f"Check whether the table contains "
                        f"the '{header}' column."
                    ),

                    expected_result=(
                        f"The '{header}' column header "
                        "is displayed correctly."
                    ),

                    category="Table Validation",

                    priority="Medium"
                )

    def generate_navigation_tests(
        self,
        page_name,
        navigation_items
    ):

        for item in navigation_items:

            text = self.element_name(
                item,
                navigation=True
            )

            if not text:
                continue

            if self.is_sensitive_action(text):
                continue

            module_name = self.resolve_navigation_module(
                text,
                self.current_module_name
            )
            navigation_key = (
                self.normalize_text(text).casefold(),
                module_name.casefold()
            )

            if navigation_key in self.navigation_case_keys:
                continue

            self.navigation_case_keys.add(navigation_key)

            self.add_test_case(

                page_name=page_name,

                title=f"Verify navigation item: {text}",

                description=(
                    f"Check that '{text}' is visible on the "
                    f"{page_name} page as navigation for the "
                    f"{module_name} functionality. This check does "
                    "not activate the control."
                ),

                expected_result=(
                    f"The '{text}' navigation item is visible and "
                    f"accessible from {page_name}; it is grouped under "
                    f"{module_name}."
                ),

                category="Navigation Validation",

                priority="Medium",

                execution_mode="Read-only",
                element_name=text,
                element_role=self.element_role(
                    item,
                    default="button"
                ),
                module_name=module_name
            )

    def generate_tests(self, discovery_data):

        self.test_cases = []
        self.counter = 0
        self.case_keys = set()
        self.navigation_case_keys = set()

        pages = discovery_data.get("pages", [])

        print("\nGENERATING AYKSA TEST CASES")

        for page in pages:

            page_name = page.get(
                "page_name",
                "Unknown Page"
            )
            module_name = self.resolve_module_name(
                page,
                page_name
            )
            self.current_module_name = module_name
            self.current_page_url = (
                page.get("url")
                or page.get("data", {}).get("url")
            )

            data = page.get("data", {})

            print("\nProcessing:", page_name)

            # 1. Page load test
            self.generate_page_load_test(page_name)

            # 2. Heading validation
            self.generate_heading_tests(
                page_name,
                data.get("headings", [])
            )

            # 3. Button validation
            self.generate_button_tests(
                page_name,
                data.get("buttons", [])
            )

            # 4. Input validation
            self.generate_input_tests(
                page_name,
                data.get("inputs", [])
            )

            # 5. Table validation
            self.generate_table_tests(
                page_name,
                data.get("tables", [])
            )

            # Navigation controls include MUI role buttons, links, and tabs.
            navigation_items = []

            for key, default_role in (
                ("roleButtons", "button"),
                ("links", "link"),
                ("tabs", "tab"),
                ("menuItems", "menuitem"),
                ("navigationItems", "button")
            ):
                for item in data.get(key, []):
                    navigation_item = dict(item)
                    navigation_item["role"] = (
                        navigation_item.get("role")
                        or default_role
                    )
                    navigation_items.append(navigation_item)

            self.generate_navigation_tests(
                page_name,
                navigation_items
            )

        return self.test_cases

    def save_test_cases(self, source_report):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        with open(source_report, "r", encoding="utf-8") as file:
            discovery_data = json.load(file)

        output = {

            "application": "AYKSA",

            "generated_at": datetime.now().isoformat(),

            "source_discovery": source_report.name,

            "total_test_cases": len(self.test_cases),

            "generation_method": "Rule-based discovery analysis",

            "module_coverage": discovery_data.get(
                "module_coverage",
                []
            ),

            "test_cases": self.test_cases
        }

        output_file = (
            TEST_CASE_DIR
            / f"ayksa_test_cases_{timestamp}.json"
        )

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                output,
                file,
                indent=4,
                ensure_ascii=False
            )

        return output_file

    def print_summary(self, output_file):

        print("\n" + "=" * 60)
        print("AYKSA TEST CASE GENERATION SUMMARY")
        print("=" * 60)

        print("Total test cases:", len(self.test_cases))

        priorities = {}

        categories = {}

        for case in self.test_cases:

            priority = case["priority"]
            category = case["category"]

            priorities[priority] = (
                priorities.get(priority, 0) + 1
            )

            categories[category] = (
                categories.get(category, 0) + 1
            )

        print("\nPRIORITY DISTRIBUTION")

        for priority, count in priorities.items():
            print(f"{priority}: {count}")

        print("\nCATEGORY DISTRIBUTION")

        for category, count in categories.items():
            print(f"{category}: {count}")

        print("\nSAMPLE TEST CASES")

        for case in self.test_cases[:10]:

            print("\nID:", case["test_id"])
            print("Page:", case["page"])
            print("Title:", case["title"])
            print("Expected:", case["expected_result"])

        print("\nTEST CASE REPORT SAVED:")
        print(output_file)

    def run(self, discovery_file=None):

        print("\n" + "=" * 60)
        print("AYKSA AI TEST CASE GENERATOR")
        print("=" * 60)

        discovery_file = (
            Path(discovery_file)
            if discovery_file
            else self.find_latest_discovery()
        )

        print("\nUsing discovery report:")
        print(discovery_file)

        discovery_data = self.load_discovery(
            discovery_file
        )

        self.generate_tests(discovery_data)

        output_file = self.save_test_cases(
            discovery_file
        )

        self.print_summary(output_file)
        return output_file


if __name__ == "__main__":

    generator = TestCaseGenerator()

    try:

        generator.run()

    except Exception as error:

        print("\nTEST CASE GENERATION FAILED")
        print("Reason:", error)
