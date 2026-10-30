"""
Playwright UI Automated Walkthrough & Quality Verification Script.
Walks through Decision View, Accuracy View, and Risk Buffer View on both Desktop and Mobile.
Captures screenshots and checks for console errors, broken charts, and layout issues.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots"))
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
if not os.path.exists(CHROME_PATH):
    CHROME_PATH = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"

def run_walkthrough():
    console_errors = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True
        )

        # -------------------------------------------------------------
        # 1. Desktop Walkthrough (1440 x 900)
        # -------------------------------------------------------------
        print("\n=== STARTING DESKTOP WALKTHROUGH (1440x900) ===")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error", "warning"] else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # Visit App
        print("Navigating to http://localhost:3000...")
        page.goto("http://localhost:3000", wait_until="networkidle")
        time.sleep(2)

        # 1.1 Decision View
        print("Walking through Decision View...")
        page.wait_for_selector("text=GB Wind Power Day-Ahead Trading Desk")
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_decision_view_desktop.png"), full_page=True)
        print("  Captured 01_decision_view_desktop.png")

        # Test interaction: change delivery date to Jan 15 and toggle vintages
        print("  Interacting: changing delivery date to 2026-01-15...")
        date_input = page.locator("input[type='date']").first
        date_input.fill("2026-01-15")
        time.sleep(1)

        # Toggle Vintages
        vintages_btn = page.locator("button:has-text('Forecast Vintages')").first
        if vintages_btn.is_visible():
            vintages_btn.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "02_decision_vintages_desktop.png"), full_page=True)
            print("  Captured 02_decision_vintages_desktop.png")

        # 1.2 Accuracy View
        print("\nWalking through Accuracy View...")
        page.click("button:has-text('Accuracy')")
        page.wait_for_selector("text=Signed Error Distribution Histogram")
        time.sleep(1.5)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "03_accuracy_view_desktop.png"), full_page=True)
        print("  Captured 03_accuracy_view_desktop.png")

        # Click different breakdown dimensions
        for dim_text in ["By Forecast Horizon", "By Wind Level Bucket", "By Delivery Day"]:
            btn = page.locator(f"button:has-text('{dim_text}')").first
            if btn.is_visible():
                btn.click()
                time.sleep(0.5)

        # 1.3 Risk Buffer View
        print("\nWalking through Risk Buffer View...")
        page.click("button:has-text('Risk Buffer')")
        page.wait_for_selector("text=Day-Ahead Wind Forecast & Derisked Hedging Band")
        time.sleep(1.5)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "04_risk_buffer_desktop.png"), full_page=True)
        print("  Captured 04_risk_buffer_desktop.png")

        # Test switching protection level to P95
        p95_btn = page.locator("button:has-text('P95')").first
        if p95_btn.is_visible():
            p95_btn.click()
            time.sleep(0.5)

        context.close()

        # -------------------------------------------------------------
        # 2. Mobile Walkthrough (390 x 844 - iPhone 14 / modern mobile)
        # -------------------------------------------------------------
        print("\n=== STARTING MOBILE WALKTHROUGH (390x844) ===")
        mobile_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
        )
        mobile_page = mobile_context.new_page()

        mobile_page.on("console", lambda msg: console_errors.append(f"[MOBILE {msg.type}] {msg.text}") if msg.type in ["error"] else None)
        mobile_page.on("pageerror", lambda err: page_errors.append(f"[MOBILE] {err}"))

        mobile_page.goto("http://localhost:3000", wait_until="networkidle")
        time.sleep(1.5)
        mobile_page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "05_decision_view_mobile.png"), full_page=True)
        print("  Captured 05_decision_view_mobile.png")

        mobile_page.click("button:has-text('Accuracy')")
        time.sleep(1.5)
        mobile_page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "06_accuracy_view_mobile.png"), full_page=True)
        print("  Captured 06_accuracy_view_mobile.png")

        mobile_page.click("button:has-text('Risk Buffer')")
        time.sleep(1.5)
        mobile_page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "07_risk_buffer_mobile.png"), full_page=True)
        print("  Captured 07_risk_buffer_mobile.png")

        mobile_context.close()
        browser.close()

    print("\n=== WALKTHROUGH DIAGNOSTICS ===")
    print(f"Total Page Errors: {len(page_errors)}")
    for pe in page_errors:
        print("  ERROR:", pe)

    print(f"Total Console Warnings/Errors: {len(console_errors)}")
    for ce in console_errors:
        print("  CONSOLE:", ce)

if __name__ == "__main__":
    run_walkthrough()

