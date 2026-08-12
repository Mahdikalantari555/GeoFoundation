"""Playwright webapp tests for the GeoMemory Streamlit dashboard."""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

DASHBOARD_URL = os.environ.get("GEOMEMORY_DASH_URL", "http://localhost:8501")
WORKSPACE_ROOT = os.environ.get("GEOMEMORY_TEST_WS", "/tmp/geomemory_dashboard_ws")


def _resolve_brave() -> str:
    """Resolve the newest installed Brave snap binary, falling back to a fixed path.

    Playwright cannot download Chromium here (no sudo), so we drive the locally
    installed Brave browser instead. Snap installs Brave under versioned dirs
    like /snap/brave/664/...; pick the highest version to stay current.
    """
    import glob

    candidates = sorted(glob.glob("/snap/brave/*/opt/brave.com/brave/brave"), reverse=True)
    if candidates:
        return candidates[0]
    fixed = "/snap/brave/current/opt/brave.com/brave/brave"
    return fixed


BRAVE_PATH = _resolve_brave()
print(f"Using Brave at: {BRAVE_PATH}")
ARTIFACTS = Path("/tmp/geomemory_playwright_artifacts")
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def _screenshot(page, name: str) -> None:
    try:
        path = ARTIFACTS / f"{name}.png"
        page.screenshot(path=str(path), full_page=False)
        print(f"screenshot: {path}")
    except Exception as exc:  # noqa: BLE001
        print(f"screenshot failed {name}: {exc}")


def _wait_for_streamlit(page) -> None:
    """Wait for Streamlit to finish loading."""
    page.wait_for_load_state("networkidle", timeout=30_000)
    # Wait for the sidebar to appear
    page.wait_for_selector("text=Workspace path", timeout=30_000)


def test_dashboard_loads_and_opens_workspace() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=BRAVE_PATH, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        page.set_default_timeout(30_000)

        page.goto(DASHBOARD_URL, wait_until="networkidle")
        _wait_for_streamlit(page)
        _screenshot(page, "01-landing")
        assert "GeoMemory" in page.content()

        # Use the text input by label
        page.fill("text=Workspace path >> input", WORKSPACE_ROOT)
        page.click("button:has-text('Apply')")
        page.wait_for_timeout(2000)
        _screenshot(page, "02-created-workspace")

        page.click("text=Open workspace")
        page.wait_for_timeout(2000)
        _screenshot(page, "03-opened-workspace")

        page.click("text=Use bundled models")
        page.wait_for_timeout(1500)
        _screenshot(page, "04-models-set")

        page.click("text=Overview")
        page.wait_for_timeout(1000)
        _screenshot(page, "05-overview")

        page.click("text=Search")
        page.wait_for_timeout(1000)
        _screenshot(page, "06-search")

        page.click("text=Ask / QA")
        page.wait_for_timeout(1000)
        _screenshot(page, "07-ask")

        page.click("text=Ingest")
        page.wait_for_timeout(1000)
        _screenshot(page, "08-ingest")

        page.click("text=Assets")
        page.wait_for_timeout(1000)
        _screenshot(page, "09-assets")

        page.click("text=Feedback")
        page.wait_for_timeout(1000)
        _screenshot(page, "10-feedback")

        page.click("text=Eval")
        page.wait_for_timeout(1000)
        _screenshot(page, "11-eval")

        page.click("text=Settings")
        page.wait_for_timeout(1000)
        _screenshot(page, "12-settings")

        page.screenshot(path=str(ARTIFACTS / "final.png"), full_page=False)
        browser.close()


if __name__ == "__main__":
    test_dashboard_loads_and_opens_workspace()
