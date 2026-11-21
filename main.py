import argparse
import asyncio
import webbrowser
from pathlib import Path

from automation.test_executor import AYKSAAutonomousTestExecutor
from discovery.browser_discovery import AYKSADiscoveryAgent
from intelligence.failure_analysis_agent import AYKSAFailureAnalysisAgent
from intelligence.test_case_generator import TestCaseGenerator
from intelligence.test_prioritizer import TestPrioritizer


def open_report_page(report_paths):
    html_report = next(
        (
            Path(report_path).resolve()
            for report_path in report_paths
            if Path(report_path).suffix.casefold() == ".html"
        ),
        None,
    )

    if html_report is None:
        raise FileNotFoundError(
            "Failure analysis did not provide an HTML dashboard."
        )

    if not html_report.is_file():
        raise FileNotFoundError(
            f"HTML dashboard was not created: {html_report}"
        )

    if webbrowser.open_new(html_report.as_uri()):
        print("\nOpened the AYKSA results dashboard in a separate browser window.")
    else:
        print(
            "\nCould not open the dashboard automatically. "
            f"Open this file in your browser: {html_report}"
        )


async def main(discover_only=False, open_report=True):

    print("=" * 60)
    print("AYKSA AUTONOMOUS QA WORKFLOW")
    print("=" * 60)
    print(
        "This workflow only navigates pages and checks visible UI. "
        "It does not activate business actions."
    )

    discovery_agent = AYKSADiscoveryAgent()
    discovery_report = await discovery_agent.start()

    if not discovery_report:
        raise RuntimeError(
            "Discovery could not verify the AYKSA Manager Dashboard. "
            "No new test run was started."
        )

    if discover_only:
        print("\nDiscovery-only run complete.")
        return

    test_report = TestCaseGenerator().run(discovery_report)
    priority_report = TestPrioritizer().run(test_report)

    executor = AYKSAAutonomousTestExecutor()
    executor.requested_report_path = str(priority_report)
    await executor.run()

    if not executor.execution_report_path:
        raise RuntimeError(
            "The execution report was not created; failure analysis "
            "cannot continue."
        )

    reports = AYKSAFailureAnalysisAgent(
        executor.execution_report_path
    ).run()

    print("\nEND-TO-END AYKSA QA WORKFLOW COMPLETE")
    if open_report:
        open_report_page(reports)
    else:
        html_report = next(
            Path(report_path).resolve()
            for report_path in reports
            if Path(report_path).suffix.casefold() == ".html"
        )
        print("Results dashboard:", html_report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Discover AYKSA pages and run the read-only QA workflow."
        )
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Refresh module/page discovery without generating or running tests.",
    )
    parser.add_argument(
        "--no-open-report",
        action="store_true",
        help="Save the final dashboard without opening a browser window.",
    )
    arguments = parser.parse_args()
    asyncio.run(
        main(
            discover_only=arguments.discover_only,
            open_report=not arguments.no_open_report,
        )
    )
