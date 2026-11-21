
import asyncio
import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from config import (
    AYKSA_DASHBOARD_URL,
    BROWSER_TIMEOUT,
    PROFILE_DIR,
    SCREENSHOT_DIR,
    RESULT_DIR,
)


async def main():
    print("=" * 60)
    print("AYKSA DASHBOARD DOM DIAGNOSTIC")
    print("=" * 60)

    async with async_playwright() as playwright:

        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--start-maximized"]
        )

        page = context.pages[0] if context.pages else await context.new_page()
        page.set_default_timeout(BROWSER_TIMEOUT)

        print("\nOpening Manager Dashboard...")
        await page.goto(
            AYKSA_DASHBOARD_URL,
            wait_until="domcontentloaded"
        )

        print("URL:", page.url)

        print("\nIf login is required, log in manually.")
        print("Wait until the Manager Dashboard is fully visible.")
        input("\nPress ENTER after the dashboard is ready...")

        print("\nWaiting for dashboard rendering...")
        await page.wait_for_timeout(8000)

        diagnostic = await page.evaluate("""
        () => {
            const visible = (element) => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();

                return (
                    style.display !== "none" &&
                    style.visibility !== "hidden" &&
                    rect.width > 0 &&
                    rect.height > 0
                );
            };

            const describe = (element) => ({
                tag: element.tagName,
                text: (element.innerText || element.textContent || "")
                    .trim()
                    .replace(/\\\\s+/g, " ")
                    .slice(0, 300),
                ariaLabel: element.getAttribute("aria-label"),
                role: element.getAttribute("role"),
                title: element.getAttribute("title"),
                href: element.getAttribute("href"),
                className: typeof element.className === "string"
                    ? element.className
                    : "",
                visible: visible(element),
                disabled: element.disabled === true
            });

            const allElements = Array.from(
                document.querySelectorAll("body *")
            );

            const buttons = Array.from(
                document.querySelectorAll("button")
            ).map(describe);

            const roleButtons = Array.from(
                document.querySelectorAll('[role="button"]')
            ).map(describe);

            const links = Array.from(
                document.querySelectorAll("a")
            ).map(describe);

            const inputs = Array.from(
                document.querySelectorAll("input, textarea, select")
            ).map(describe);

            const clickableElements = allElements
                .filter(element => {
                    const style = window.getComputedStyle(element);

                    return (
                        element.onclick !== null ||
                        element.getAttribute("onclick") !== null ||
                        style.cursor === "pointer"
                    );
                })
                .map(describe)
                .slice(0, 150);

            const headings = Array.from(
                document.querySelectorAll("h1, h2, h3, h4")
            ).map(describe);

            const iframes = Array.from(
                document.querySelectorAll("iframe")
            ).map(frame => ({
                src: frame.src,
                title: frame.title
            }));

            return {
                pageTitle: document.title,
                url: window.location.href,
                readyState: document.readyState,
                bodyText: document.body
                    ? document.body.innerText.slice(0, 12000)
                    : "",
                bodyHTMLStart: document.body
                    ? document.body.innerHTML.slice(0, 5000)
                    : "",
                totalDOMElements: allElements.length,
                buttons,
                roleButtons,
                links,
                inputs,
                clickableElements,
                headings,
                iframes
            };
        }
        """)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        json_path = RESULT_DIR / f"dashboard_diagnostic_{timestamp}.json"
        screenshot_path = SCREENSHOT_DIR / f"dashboard_diagnostic_{timestamp}.png"

        json_path.write_text(
            json.dumps(diagnostic, indent=4, ensure_ascii=False),
            encoding="utf-8"
        )

        await page.screenshot(
            path=str(screenshot_path),
            full_page=True
        )

        print("\n" + "=" * 60)
        print("DIAGNOSTIC RESULTS")
        print("=" * 60)

        print("Title:", diagnostic["pageTitle"])
        print("URL:", diagnostic["url"])
        print("Document state:", diagnostic["readyState"])
        print("Total DOM elements:", diagnostic["totalDOMElements"])

        print("\nBUTTONS:", len(diagnostic["buttons"]))
        for item in diagnostic["buttons"]:
            print(item)

        print("\nROLE BUTTONS:", len(diagnostic["roleButtons"]))
        for item in diagnostic["roleButtons"]:
            print(item)

        print("\nLINKS:", len(diagnostic["links"]))
        for item in diagnostic["links"][:30]:
            print(item)

        print("\nHEADINGS:", len(diagnostic["headings"]))
        for item in diagnostic["headings"]:
            print(item)

        print("\nCLICKABLE ELEMENTS:", len(diagnostic["clickableElements"]))
        for item in diagnostic["clickableElements"][:50]:
            print(item)

        print("\nVISIBLE PAGE TEXT:")
        print(diagnostic["bodyText"][:5000])

        print("\nJSON REPORT:", json_path)
        print("SCREENSHOT:", screenshot_path)

        print("\nKeep the browser open until the diagnostic is complete.")
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
