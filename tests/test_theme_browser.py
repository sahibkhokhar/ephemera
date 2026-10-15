"""Optional real-browser regression checks.

Install playwright and run `python -m playwright install chromium`, then
`python -m pytest tests/test_theme_browser.py -q`.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from artifact_viewer.config import Settings
from artifact_viewer.main import create_app

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as runner:
        browser = runner.chromium.launch()
        yield browser
        browser.close()


@pytest.mark.parametrize("system", ["light", "dark"])
@pytest.mark.parametrize("saved", [None, "light", "dark", "invalid", "blocked"])
def test_theme_label_before_and_after_deferred_script(browser, tmp_path, system, saved):
    settings = Settings(db_path=tmp_path / "artifacts.db", base_url="http://theme.test")
    with TestClient(create_app(settings)) as client, browser.new_context(color_scheme=system) as context:
        if saved == "blocked":
            context.add_init_script("""
                Object.defineProperty(window, 'localStorage', {
                    get() { throw new Error('Storage unavailable'); }
                });
            """)
        elif saved is not None:
            context.add_init_script(
                "if (localStorage.getItem('ephemera-theme') === null) "
                f"localStorage.setItem('ephemera-theme', {json.dumps(saved)});"
            )

        app_enabled = False

        def serve(route):
            path = route.request.url.removeprefix("http://theme.test")
            response = client.get(path)
            # Let the page paint with the real CSS and pre-paint bootstrap,
            # but without the deferred script that used to conceal this bug.
            body = response.content if app_enabled or path != "/static/app.js" else b""
            route.fulfill(status=response.status_code, headers=dict(response.headers), body=body)

        context.route("http://theme.test/**", serve)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://theme.test/")
        selected = saved if saved in ("light", "dark") else system

        def check(theme, initialized):
            next_theme = "dark" if theme == "light" else "light"
            if initialized:
                playwright.expect(page.locator("[data-theme-toggle]")).to_have_attribute(
                    "aria-label", f"Switch to {next_theme} mode"
                )
            button = page.get_by_role("button", name=(
                f"Switch to {next_theme} mode" if initialized else f"{next_theme} mode"
            ), exact=True)
            assert button.count() == 1
            assert button.inner_text().strip().endswith(f"{next_theme} mode")
            assert button.get_attribute("aria-pressed") == (
                str(theme == "light").lower() if initialized else None
            )
            assert page.locator("body").evaluate(
                "el => getComputedStyle(el).backgroundColor"
            ) == ("rgb(247, 247, 245)" if theme == "light" else "rgb(13, 13, 13)")

        check(selected, initialized=False)
        app_enabled = True
        page.add_script_tag(url="http://theme.test/static/app.js")
        check(selected, initialized=True)

        changed_system = "dark" if system == "light" else "light"
        page.emulate_media(color_scheme=changed_system)
        if saved not in ("light", "dark"):
            selected = changed_system
        check(selected, initialized=True)

        for _ in range(2):
            page.locator("[data-theme-toggle]").click()
            selected = "dark" if selected == "light" else "light"
            check(selected, initialized=True)
            if saved != "blocked":
                assert page.evaluate("localStorage.getItem('ephemera-theme')") == selected

        if saved != "blocked":
            page.reload()
            check(selected, initialized=True)
            page.emulate_media(color_scheme=system)
            check(selected, initialized=True)
        assert errors == []
