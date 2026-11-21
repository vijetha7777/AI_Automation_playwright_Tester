
import asyncio
import json
import re
from datetime import datetime

from playwright.async_api import async_playwright

from config import (
    AYKSA_DASHBOARD_URL,
    BROWSER_TIMEOUT,
    PROFILE_DIR,
    SCREENSHOT_DIR,
    RESULT_DIR,
)


class AYKSADiscoveryAgent:

    def __init__(self):
        self.browser_context = None
        self.page = None
        self.records = []
        self.module_status = {}

        self.module_navigation_items = [
            "EMS",
            "Route Management",
            "Field Executive",
            "Reimbursement",
            "HR",
            "Communication",
            "DOA",
            "Certificate Download",
        ]

        self.leave_sections = [
            "Leave Requests",
            "Holiday Calendar",
            "Leave Policies",
            "Leave Types",
        ]

        self.leave_overview_url = (
            "https://ayksadev-adminportal.onrender.com/dashboard/leave"
        )

    async def start(self):

        async with async_playwright() as playwright:

            self.browser_context = (
                await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    headless=False,
                    viewport={"width": 1440, "height": 900},
                    args=["--start-maximized"]
                )
            )

            self.page = (
                self.browser_context.pages[0]
                if self.browser_context.pages
                else await self.browser_context.new_page()
            )

            self.page.set_default_timeout(BROWSER_TIMEOUT)

            print("\nOPENING AYKSA DASHBOARD")

            await self.page.goto(
                AYKSA_DASHBOARD_URL,
                wait_until="domcontentloaded"
            )

            await self.page.wait_for_timeout(4000)

            if "/login" in self.page.url.lower():

                print("\nLOGIN REQUIRED")

                input(
                    "Log in manually and open Manager Dashboard. "
                    "Then press ENTER..."
                )

                await self.page.wait_for_timeout(4000)

            if "/dashboard/employee-dashboard" not in self.page.url:

                print("Manager Dashboard could not be verified.")
                print("Current URL:", self.page.url)

                await self.browser_context.close()
                return None

            print("Manager Dashboard verified.")

            await self.inspect_page("Manager Dashboard")
            self.module_status["Manager Dashboard"] = {
                "status": "discovered",
                "message": "Manager Dashboard was inspected successfully.",
            }

            await self.discover_leave_management()

            for module_name in self.module_navigation_items:
                await self.discover_module(module_name)

            report_path = self.save_report()

            await self.browser_context.close()
            return report_path

    async def open_manager_dashboard(self):

        await self.page.goto(
            AYKSA_DASHBOARD_URL,
            wait_until="domcontentloaded"
        )
        await self.page.wait_for_timeout(1800)

        if "/login" in self.page.url.lower():
            raise RuntimeError(
                "The AYKSA session expired during module discovery."
            )

    async def discover_leave_management(self):

        print("\nDISCOVERING MODULE: Leave Management")
        await self.open_manager_dashboard()
        success = await self.click_sidebar_item("Leave Management")

        if not success:
            self.module_status["Leave Management"] = {
                "status": "not_discovered",
                "message": (
                    "Leave Management was not opened from the visible "
                    "navigation for this authenticated session."
                ),
            }
            print("Leave Management was not opened; skipping its pages.")
            return

        await self.page.wait_for_timeout(1800)
        self.leave_overview_url = self.page.url
        await self.inspect_page(
            "Leave Management Overview",
            module_name="Leave Management"
        )
        self.module_status["Leave Management"] = {
            "status": "discovered",
            "message": "Leave Management overview was inspected.",
        }

        for section in self.leave_sections:
            if not await self.return_to_overview():
                print(
                    "Stopping Leave Management discovery because "
                    "the overview could not be restored."
                )
                break

            await self.inspect_leave_section(section)

    async def discover_module(self, module_name):

        print(f"\nDISCOVERING MODULE: {module_name}")

        try:
            await self.open_manager_dashboard()
            opened = await self.click_module_navigation(module_name)

            if not opened:
                self.module_status[module_name] = {
                    "status": "not_discovered",
                    "message": (
                        "A matching visible navigation item was not "
                        "available to this authenticated session."
                    ),
                }
                print(
                    f"{module_name} was not found as a visible navigation "
                    "item; no page was recorded for it."
                )
                return

            await self.page.wait_for_timeout(1800)
            page_title = self.classify_module_page(
                module_name,
                self.page.url
            )

            if not any(
                record["url"] == self.page.url
                and record.get("module_name") == module_name
                for record in self.records
            ):
                await self.inspect_page(
                    page_title,
                    module_name=module_name
                )
            self.module_status[module_name] = {
                "status": "discovered",
                "message": (
                    f"{module_name} was opened and its visible page "
                    "was inspected."
                ),
            }

        except Exception as error:
            self.module_status[module_name] = {
                "status": "discovery_error",
                "message": str(error),
            }
            print(
                f"Could not inspect {module_name}: {error}"
            )

    @staticmethod
    def classify_module_page(module_name, page_url):

        path = page_url.rstrip("/").split("/")[-1]
        if path and path.lower() not in {
            "employee-dashboard",
            "dashboard",
        }:
            return " ".join(
                word.capitalize()
                for word in re.split(r"[-_]+", path)
                if word
            )

        return module_name

    async def click_module_navigation(self, module_name):

        selector = (
            "nav [role='button'], aside [role='button'], "
            "[role='navigation'] [role='button'], "
            ".MuiDrawer-root [role='button'], "
            ".MuiListItem-root[role='button'], "
            "nav a[href], aside a[href], "
            "[role='navigation'] a[href], .MuiDrawer-root a[href]"
        )
        controls = self.page.locator(selector)
        matches = []

        for index in range(await controls.count()):
            control = controls.nth(index)

            if not await control.is_visible():
                continue

            name = await control.get_attribute("aria-label")

            if not name:
                name = await control.evaluate(
                    """element => {
                        const clone = element.cloneNode(true);
                        clone.querySelectorAll(
                            '[aria-hidden="true"], .MuiBadge-badge, [class*="MuiBadge-badge"]'
                        ).forEach(child => child.remove());
                        return (
                            clone.innerText ||
                            clone.textContent ||
                            element.getAttribute("title") ||
                            ""
                        ).replace(/\\s+/g, " ").trim();
                    }"""
                )

            name = re.sub(
                r"^\d+\s+(?=\D)",
                "",
                " ".join(str(name or "").split())
            ).strip()

            if name.casefold() == module_name.casefold():
                matches.append(control)

        if len(matches) != 1:
            print(
                f"Visible {module_name!r} navigation matches: "
                f"{len(matches)}"
            )
            return False

        url_before = self.page.url
        body_before = " ".join(
            (await self.page.locator("body").inner_text()).split()
        )
        await matches[0].click()
        await self.page.wait_for_timeout(1500)
        body_after = " ".join(
            (await self.page.locator("body").inner_text()).split()
        )

        if self.page.url == url_before and body_after == body_before:
            print(
                f"{module_name} click did not change the page or visible "
                "content; not recording a page."
            )
            return False

        return True

    async def inspect_page(self, page_name, module_name=None):

        print("\n" + "=" * 60)
        print("INSPECTING:", page_name)
        print("URL:", self.page.url)
        print("=" * 60)

        await self.page.wait_for_timeout(1200)

        data = await self.page.evaluate("""
        () => {

            const isVisible = (element) => {

                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();

                return (
                    style.display !== "none" &&
                    style.visibility !== "hidden" &&
                    Number(style.opacity) !== 0 &&
                    rect.width > 0 &&
                    rect.height > 0
                );
            };

            const describe = (element) => ({

                tag: element.tagName,

                text: (
                    element.innerText ||
                    element.textContent ||
                    ""
                ).trim().replace(/\\\\s+/g, " ").slice(0, 300),

                ariaLabel: element.getAttribute("aria-label"),

                role: element.getAttribute("role"),

                title: element.getAttribute("title"),

                href: element.getAttribute("href"),

                className:
                    typeof element.className === "string"
                    ? element.className
                    : "",

                disabled: element.disabled === true
            });

            const accessibleName = (element) => {

                const ariaLabel = element.getAttribute("aria-label");

                if (ariaLabel && ariaLabel.trim()) {
                    return ariaLabel.trim();
                }

                const labelledBy = element.getAttribute("aria-labelledby");

                if (labelledBy) {
                    const label = labelledBy
                        .split(/\\s+/)
                        .map(id => document.getElementById(id))
                        .filter(Boolean)
                        .map(labelElement => labelElement.innerText || labelElement.textContent || "")
                        .join(" ")
                        .trim();

                    if (label) {
                        return label.replace(/\\s+/g, " ");
                    }
                }

                const clone = element.cloneNode(true);

                clone.querySelectorAll(
                    '[aria-hidden="true"], .MuiBadge-badge, [class*="MuiBadge-badge"]'
                ).forEach(child => child.remove());

                const content = (
                    clone.innerText ||
                    clone.textContent ||
                    ""
                ).trim().replace(/\\s+/g, " ");

                return content || element.getAttribute("title") || "";
            };

            const describeInteractive = (element) => ({
                ...describe(element),
                accessibleName: accessibleName(element),
                visible: true
            });

            const buttons = Array.from(
                document.querySelectorAll("button")
            )
            .filter(isVisible)
            .map(describeInteractive);

            const roleButtons = Array.from(
                document.querySelectorAll('[role="button"]')
            )
            .filter(isVisible)
            .map(describeInteractive);

            const links = Array.from(
                document.querySelectorAll('a[href], [role="link"]')
            )
            .filter(isVisible)
            .map(describeInteractive);

            const tabs = Array.from(
                document.querySelectorAll('[role="tab"]')
            )
            .filter(isVisible)
            .map(describeInteractive);

            const menuItems = Array.from(
                document.querySelectorAll('[role="menuitem"]')
            )
            .filter(isVisible)
            .map(describeInteractive);

            const navigationItems = Array.from(
                document.querySelectorAll(
                    "nav a[href], nav [role='button'], nav [role='link'], " +
                    "aside a[href], aside [role='button'], aside [role='link'], " +
                    "[role='navigation'] a[href], [role='navigation'] [role='button'], " +
                    ".MuiDrawer-root a[href], .MuiDrawer-root [role='button'], " +
                    ".MuiListItem-root[role='button']"
                )
            )
            .filter(isVisible)
            .map(describeInteractive);

            const inputs = Array.from(
                document.querySelectorAll(
                    "input, textarea, select"
                )
            )
            .filter(isVisible)
            .map(describe);

            const headings = Array.from(
                document.querySelectorAll(
                    "h1, h2, h3, h4, h5, h6"
                )
            )
            .filter(isVisible)
            .map(describe);

            const tables = Array.from(
                document.querySelectorAll("table")
            )
            .filter(isVisible)
            .map(table => ({

                headers: Array.from(
                    table.querySelectorAll("th")
                ).map(th => th.innerText.trim()),

                rowCount: table.querySelectorAll("tbody tr").length
            }));

            return {

                title: document.title,

                url: window.location.href,

                bodyText: document.body
                    ? document.body.innerText.slice(0, 12000)
                    : "",

                buttons,
                roleButtons,
                links,
                tabs,
                menuItems,
                navigationItems,
                inputs,
                headings,
                tables,

                totalVisibleButtons: buttons.length,

                totalVisibleRoleButtons: roleButtons.length,

                totalVisibleLinks: links.length,

                totalVisibleTabs: tabs.length,

                totalVisibleMenuItems: menuItems.length,

                totalVisibleInputs: inputs.length,

                totalVisibleTables: tables.length
            };
        }
        """)

        self.records.append({

            "page_name": page_name,
            "module_name": module_name or self.infer_module_name(page_name),

            "captured_at": datetime.now().isoformat(),

            "url": self.page.url,

            "data": data
        })

        print("\nBUTTON DETAILS")

        for item in data["buttons"]:

            print(
                "Text:", item["text"],
                "| ARIA:", item["ariaLabel"],
                "| Disabled:", item["disabled"]
            )

        print("\nCUSTOM ROLE BUTTONS")

        for item in data["roleButtons"]:
            print("Name:", item["accessibleName"])

        print("\nLINKS AND TABS")

        for item in data["links"] + data["tabs"] + data["menuItems"]:
            print("Role:", item["role"], "| Name:", item["accessibleName"])

        print("\nHEADINGS")

        for item in data["headings"]:
            print(item["text"])

        print("\nSUMMARY")

        print("Buttons:", data["totalVisibleButtons"])
        print("Navigation items:", data["totalVisibleRoleButtons"])
        print("Links:", data["totalVisibleLinks"])
        print("Tabs:", data["totalVisibleTabs"])
        print("Menu items:", data["totalVisibleMenuItems"])
        print("Inputs:", data["totalVisibleInputs"])
        print("Tables:", data["totalVisibleTables"])

        safe_name = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            page_name
        )

        screenshot_path = (
            SCREENSHOT_DIR /
            f"discovery_{len(self.records):03d}_{safe_name}.png"
        )

        await self.page.screenshot(
            path=str(screenshot_path),
            full_page=True
        )

        print("Screenshot:", screenshot_path)

    @staticmethod
    def infer_module_name(page_name):

        leave_pages = {
            "Leave Management Overview",
            "Leave Requests",
            "Holiday Calendar",
            "Leave Policies",
            "Leave Types",
        }

        if page_name in leave_pages:
            return "Leave Management"

        return page_name

    async def click_sidebar_item(self, item_name):

        print("\nSearching sidebar:", item_name)

        locator = self.page.locator(
            ".MuiListItem-root[role='button'], "
            "[role='navigation'] [role='button'], "
            "nav [role='button'], aside [role='button']"
        )

        count = await locator.count()

        matches = []

        for index in range(count):

            element = locator.nth(index)

            try:

                if not await element.is_visible():
                    continue

                text = await element.get_attribute("aria-label")

                if not text:
                    text = await element.evaluate(
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

                text = re.sub(
                    r"^\\d+\\s+(?=\\D)",
                    "",
                    " ".join(str(text or "").split())
                ).strip()

                if text == item_name:
                    matches.append(element)

            except Exception:
                continue

        print("Visible matches:", len(matches))

        if len(matches) != 1:
            print("Sidebar item is not uniquely identified.")
            return False

        try:

            await matches[0].click()

            await self.page.wait_for_timeout(2500)

            return True

        except Exception as error:

            print("Sidebar navigation error:", error)
            return False

    async def return_to_overview(self):

        print("\nRETURNING TO LEAVE MANAGEMENT OVERVIEW")

        overview_button = self.page.locator(
            'button[aria-label="Back to leave management overview"]'
        )

        try:

            if await overview_button.count() == 1:

                if await overview_button.is_visible():

                    await overview_button.click()

                    await self.page.wait_for_timeout(2000)

            # Confirm the overview cards are present.
            leave_requests_card = self.page.locator(
                'button[aria-label="Open Leave Requests"]'
            )

            await leave_requests_card.wait_for(
                state="visible",
                timeout=10000
            )

            print("Leave Management overview restored.")

            return True

        except Exception as error:

            print("Could not restore overview:", error)

            return False

    async def inspect_leave_section(self, section_name):

        print("\n" + "-" * 55)
        print("OPENING LEAVE SECTION:", section_name)
        print("-" * 55)

        accessible_name = f"Open {section_name}"

        section_button = self.page.locator(
            f'button[aria-label="{accessible_name}"]'
        )

        try:

            await section_button.wait_for(
                state="visible",
                timeout=10000
            )

            if await section_button.count() != 1:

                print("Section button is not unique.")
                return

            await section_button.click()

            await self.page.wait_for_timeout(2500)

            body_text = await self.page.locator(
                "body"
            ).inner_text()

            if section_name.lower() not in body_text.lower():

                print(
                    "Expected section text not found:",
                    section_name
                )

                return

            print("Section opened:", section_name)

            await self.inspect_page(
                section_name,
                module_name="Leave Management"
            )

        except Exception as error:

            print(
                "Could not inspect section:",
                section_name,
                "|",
                error
            )

    def save_report(self):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        report = {

            "application": "AYKSA",

            "environment": "Development",

            "captured_at": datetime.now().isoformat(),

            "total_pages_inspected": len(self.records),

            "module_coverage": [
                {
                    "module": module_name,
                    "status": self.module_status.get(
                        module_name,
                        {
                            "status": "not_discovered",
                            "message": (
                                "No page was recorded for this module."
                            ),
                        },
                    )["status"],
                    "page_count": sum(
                        record.get("module_name") == module_name
                        for record in self.records
                    ),
                    "message": self.module_status.get(
                        module_name,
                        {
                            "message": (
                                "No page was recorded for this module."
                            ),
                        },
                    )["message"],
                }
                for module_name in (
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
                )
            ],

            "pages": self.records
        }

        report_path = (
            RESULT_DIR /
            f"ayksa_discovery_{timestamp}.json"
        )

        report_path.write_text(
            json.dumps(
                report,
                indent=4,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        print("\n" + "=" * 60)
        print("DISCOVERY REPORT SAVED")
        print("=" * 60)

        print(
            "Total pages inspected:",
            len(self.records)
        )

        print("Report:", report_path)
        return report_path


if __name__ == "__main__":

    agent = AYKSADiscoveryAgent()

    asyncio.run(agent.start())
