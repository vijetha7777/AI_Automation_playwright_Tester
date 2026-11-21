
import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

TEST_CASE_DIR = (
    BASE_DIR / "artifacts" / "reports" / "test_cases"
)

PRIORITY_REPORT_DIR = (
    BASE_DIR / "artifacts" / "reports" / "prioritized_tests"
)


class TestPrioritizer:

    def __init__(self):

        PRIORITY_REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self.test_cases = []
        self.prioritized_tests = []
        self.module_coverage = []

    def find_latest_test_report(self):

        reports = list(
            TEST_CASE_DIR.glob("ayksa_test_cases_*.json")
        )

        if not reports:
            raise FileNotFoundError(
                "No generated test case reports found."
            )

        return max(
            reports,
            key=lambda file: file.stat().st_mtime
        )

    def load_test_cases(self, report_file):

        with open(
            report_file,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        self.test_cases = data.get("test_cases", [])
        self.module_coverage = data.get("module_coverage", [])

        if not self.test_cases:
            raise ValueError(
                "The test case report contains no test cases."
            )

        return data

    def calculate_priority(self, test):

        score = 0
        reasons = []

        # 1. Use the priority assigned by the generator.
        existing_priority = test.get(
            "priority",
            "Medium"
        ).lower()

        if existing_priority == "high":
            score += 40
            reasons.append("Originally marked High priority")

        elif existing_priority == "medium":
            score += 25
            reasons.append("Originally marked Medium priority")

        elif existing_priority == "low":
            score += 10
            reasons.append("Originally marked Low priority")

        # 2. Category-based scoring.
        category = test.get("category", "").lower()

        category_scores = {

            "page navigation": 30,

            "form validation": 25,

            "table validation": 25,

            "content validation": 20,

            "button validation": 15,

            "navigation validation": 15
        }

        category_score = category_scores.get(
            category,
            10
        )

        score += category_score

        reasons.append(
            f"Category: {test.get('category', 'Unknown')}"
        )

        # 3. Page importance.
        page_name = test.get("page", "").lower()

        important_pages = [
            "manager dashboard",
            "leave requests",
            "leave management overview"
        ]

        if any(
            name in page_name
            for name in important_pages
        ):

            score += 15

            reasons.append(
                "Page is considered important"
            )

        # 4. Test title keyword scoring.
        title = test.get("title", "").lower()

        critical_keywords = [
            "page loads",
            "navigation",
            "table is displayed"
        ]

        if any(
            keyword in title
            for keyword in critical_keywords
        ):

            score += 10

            reasons.append(
                "Test covers an important application behavior"
            )

        # 5. Execution safety.
        execution_mode = test.get(
            "execution_mode",
            "Read-only"
        )

        if execution_mode.lower() == "read-only":

            reasons.append(
                "Suitable for read-only test execution"
            )

        else:

            score -= 15

            reasons.append(
                "Requires additional execution safety review"
            )

        # Keep score within 0-100.
        score = max(0, min(score, 100))

        if score >= 75:
            priority_level = "Critical"

        elif score >= 60:
            priority_level = "High"

        elif score >= 40:
            priority_level = "Medium"

        else:
            priority_level = "Low"

        return {
            "priority_score": score,
            "calculated_priority": priority_level,
            "priority_reasons": reasons
        }

    def prioritize(self):

        self.prioritized_tests = []

        print("\nPRIORITIZING TEST CASES")

        for test in self.test_cases:

            priority_data = self.calculate_priority(
                test
            )

            prioritized_test = {
                **test,
                **priority_data
            }

            self.prioritized_tests.append(
                prioritized_test
            )

        # Highest score first.
        self.prioritized_tests.sort(
            key=lambda item: (
                item["priority_score"],
                item.get("test_id", "")
            ),
            reverse=True
        )

        # Assign execution order.
        for index, test in enumerate(
            self.prioritized_tests,
            start=1
        ):

            test["execution_order"] = index

        return self.prioritized_tests

    def save_report(self, source_file):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        output = {

            "application": "AYKSA",

            "generated_at": datetime.now().isoformat(),

            "source_test_report": source_file.name,

            "total_test_cases": len(
                self.prioritized_tests
            ),

            "prioritization_method": (
                "Rule-based weighted scoring"
            ),

            "module_coverage": self.module_coverage,

            "test_cases": self.prioritized_tests
        }

        output_file = (
            PRIORITY_REPORT_DIR
            / f"ayksa_prioritized_tests_{timestamp}.json"
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

        print("\n" + "=" * 65)
        print("AYKSA TEST PRIORITIZATION SUMMARY")
        print("=" * 65)

        print(
            "Total test cases:",
            len(self.prioritized_tests)
        )

        distribution = {
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0
        }

        for test in self.prioritized_tests:

            priority = test["calculated_priority"]

            distribution[priority] += 1

        print("\nPRIORITY DISTRIBUTION")

        for priority, count in distribution.items():

            print(f"{priority}: {count}")

        print("\nTOP 10 PRIORITIZED TEST CASES")

        for test in self.prioritized_tests[:10]:

            print("\nExecution order:", test["execution_order"])

            print("Test ID:", test.get("test_id"))

            print("Page:", test.get("page"))

            print("Title:", test.get("title"))

            print(
                "Priority:",
                test["calculated_priority"]
            )

            print(
                "Score:",
                test["priority_score"]
            )

            print(
                "Reason:",
                "; ".join(test["priority_reasons"])
            )

        print("\nPRIORITIZED REPORT SAVED:")
        print(output_file)

    def run(self, source_file=None):

        print("\n" + "=" * 65)
        print("AYKSA TEST PRIORITIZATION ENGINE")
        print("=" * 65)

        source_file = (
            Path(source_file)
            if source_file
            else self.find_latest_test_report()
        )

        print("\nSOURCE TEST REPORT:")
        print(source_file)

        self.load_test_cases(source_file)

        self.prioritize()

        output_file = self.save_report(
            source_file
        )

        self.print_summary(output_file)
        return output_file


if __name__ == "__main__":

    prioritizer = TestPrioritizer()

    try:

        prioritizer.run()

    except Exception as error:

        print("\nTEST PRIORITIZATION FAILED")
        print("Reason:", error)
