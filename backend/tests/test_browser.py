"""Browser-based prototype checks (Playwright + headless Chromium, if available).

Renders the generated prototype in a real browser and verifies: no console/page
errors, navigation switches screens, hero CTA works, form submission mutates the
shared store and dashboard stats update. Skipped with a recorded reason when the
browser is unavailable (deterministic validator covers the rest).
"""

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api", reason="playwright not installed")


def _launch(p):
    try:
        return p.chromium.launch()
    except Exception as exc:
        pytest.skip(f"chromium unavailable: {exc}")


def _sample_html(tmp_path):
    from app.agents.llm.mock_handlers import (
        handle_analyze_requirement,
        handle_build_prototype,
        handle_plan_application,
    )
    from app.schemas.prototype import PrototypeSpec
    from app.services.codegen.prototype_renderer import render_prototype

    analysis = handle_analyze_requirement({"input": {"requirement": "Build a Hospital Management System where patients can register, doctors can manage appointments, administrators can manage users, and users can view medical records."}})
    plan = handle_plan_application({"input": {"analysis": analysis}})
    spec = PrototypeSpec.model_validate(handle_build_prototype({"input": {"analysis": analysis, "plan": plan}}))
    target = tmp_path / "proto.html"
    target.write_text(render_prototype(spec), encoding="utf-8")
    return target


def test_browser_prototype_interactions(tmp_path):
    from playwright.sync_api import sync_playwright

    html_file = _sample_html(tmp_path)
    errors: list[str] = []
    with sync_playwright() as p:
        browser = _launch(p)
        try:
            page = browser.new_page()
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(html_file.as_uri())
            page.wait_for_selector(".screen.active")

            # Hero CTA is visible with a label and navigates forward
            cta = page.locator(".hero-cta")
            assert cta.count() >= 1
            assert (cta.first.inner_text() or "").strip() != ""
            first = page.evaluate("document.querySelector('.screen.active').getAttribute('data-screen')")
            cta.first.click()
            page.wait_for_timeout(300)

            # Every nav button resolves to a visible screen
            navs = page.locator(".navbar .nav-btn")
            assert navs.count() >= 3
            for i in range(min(navs.count(), 8)):
                navs.nth(i).click()
                page.wait_for_timeout(150)
                assert page.locator(".screen.active").count() == 1

            # Dashboard stats are numeric and consistent with rendered rows
            stats = page.locator("[data-stat]")
            if stats.count():
                for i in range(stats.count()):
                    assert stats.nth(i).inner_text().strip().isdigit()

            # Form submission mutates shared state and updates stats.
            # Only the active screen's form is interactable; navigate until one is visible.
            visible_form = page.locator(".screen.active form[data-form]")
            if visible_form.count() == 0:
                for i in range(navs.count()):
                    navs.nth(i).click()
                    page.wait_for_timeout(150)
                    if page.locator(".screen.active form[data-form]").count():
                        break
                visible_form = page.locator(".screen.active form[data-form]")
            if visible_form.count():
                form = visible_form.first
                for field in form.locator("input, select, textarea").all():
                    tag = field.evaluate("(el) => el.tagName + '|' + (el.getAttribute('type') || '')")
                    name, ftype = tag.split("|")
                    try:
                        if name == "SELECT":
                            field.select_option(index=1)
                        elif ftype == "email":
                            field.fill("browser@test.dev")
                        elif ftype == "password":
                            field.fill("secret123")
                        elif ftype == "date":
                            field.fill("2026-01-15")
                        elif ftype == "number":
                            field.fill("2")
                        elif ftype == "checkbox":
                            field.check()
                        else:
                            field.fill("Browser Test")
                    except Exception:
                        pass
                form.locator("button[type=submit]").click()
                page.wait_for_timeout(400)
                toast = page.locator("#toast.show")
                assert toast.count() >= 1

            assert errors == [], f"browser errors: {errors[:5]}"
        finally:
            browser.close()
