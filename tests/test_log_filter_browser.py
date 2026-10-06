"""Optional browser regression: pip install playwright && playwright install chromium.

Run with pytest tests/test_log_filter_browser.py. PLAYWRIGHT_CHROMIUM_EXECUTABLE
can select an existing Chromium installation. No browser dependency is needed
by the application or the normal API test suite.
"""
import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from artifact_viewer.config import Settings
from artifact_viewer.main import create_app

playwright = pytest.importorskip("playwright.sync_api")


def test_log_filter_browser(tmp_path):
    content = "start\nWARN needle needle\nERROR needle <script>alert(1)</script>\nother\n" + "long " * 80
    with TestClient(create_app(Settings(db_path=tmp_path / "browser.db"))) as client:
        artifact = client.post("/api/artifacts", json={"kind": "log", "content": content}).json()
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE"))
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def serve(route):
                response = client.get(urlsplit(route.request.url).path)
                route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)

            page.route("http://ephemera.test/**", serve)
            page.goto("http://ephemera.test/a/" + artifact["id"])
            field = page.get_by_role("textbox", name="Filter log lines")
            status = page.get_by_role("status")
            visible = page.locator(".ln:visible")
            assert visible.count() == 5
            field.fill("needle")
            assert status.inner_text() == "2 of 5 lines"
            assert page.locator("mark").count() == 3
            assert visible.first.locator(".ln-gutter").get_attribute("data-line") == "2"
            assert visible.first.locator(".ln-gutter").evaluate("el => getComputedStyle(el, '::before').content") == '"2"'
            assert page.locator(".ln-error:visible").count() == 1
            assert page.locator(".ln-warn:visible").count() == 1
            assert page.locator(".ln-text script").count() == 0
            page.get_by_role("button", name="Next", exact=True).click()
            assert page.locator("mark.is-current").count() == 1
            first = page.locator("mark.is-current")
            assert first.evaluate("el => Array.from(document.querySelectorAll('mark')).indexOf(el)") == 0
            page.get_by_role("button", name="Previous", exact=True).click()
            assert first.evaluate("el => Array.from(document.querySelectorAll('mark')).indexOf(el)") == 2
            field.focus()
            field.press("n")
            assert field.input_value() == "needlen"
            field.fill("needle")
            field.evaluate("el => el.blur()")
            page.keyboard.press("n")
            assert first.evaluate("el => Array.from(document.querySelectorAll('mark')).indexOf(el)") == 0
            page.keyboard.press("N")
            assert first.evaluate("el => Array.from(document.querySelectorAll('mark')).indexOf(el)") == 2
            page.get_by_role("button", name="1 error", exact=True).click()
            assert visible.count() == 1
            assert status.inner_text() == "1 of 5 lines"
            assert page.locator("mark").count() == 1
            page.get_by_role("button", name="1 error", exact=True).click()
            assert visible.count() == 2
            field.fill("/WARN|ERROR/")
            assert visible.count() == 2
            field.fill("/[/")
            assert field.get_attribute("aria-invalid") == "true"
            assert visible.count() == 5
            assert page.get_by_role("button", name="Next", exact=True).is_disabled()
            field.fill("missing")
            assert status.inner_text() == "0 of 5 lines"
            field.fill("/^/")
            assert visible.count() == 5
            assert page.locator("mark").count() == 5
            field.fill("/needle/g")  # only /regex/ is special; everything else is literal
            assert visible.count() == 0
            field.fill("needle")
            assert page.locator("mark").count() == 3  # no stale regex lastIndex or markup
            page.get_by_role("button", name="1 warning", exact=True).click()
            page.get_by_role("button", name="Clear", exact=True).click()
            assert field.input_value() == ""
            assert visible.count() == 5
            assert page.locator("mark").count() == 0
            assert page.locator('.ichip[aria-pressed="true"]').count() == 0
            page.get_by_role("button", name="Toggle wrap").click()
            assert page.locator(".code-body").evaluate("el => el.classList.contains('is-wrapped')")
            field.fill("needle")
            assert visible.count() == 2  # hidden still wins over flex/table row layout
            page.get_by_role("button", name="Toggle line numbers").click()
            assert visible.count() == 2
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            screenshot = os.getenv("LOG_FILTER_SCREENSHOT")
            if screenshot:
                page.screenshot(path=screenshot, full_page=True)
            assert not errors
            browser.close()
