"""Shared fixtures for E2E tests — starts the parade server in a subprocess."""
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

PORT = 18080
BASE_URL = f"http://localhost:{PORT}"
ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="session")
def live_server():
    """Start a parade server on a dedicated test port for the duration of the session."""
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "parade.main",
            "--config", str(ROOT / "config" / "default.yaml"),
            "--profiles", str(ROOT / "fixture_profiles"),
            "--cues", str(ROOT / "cues"),
            "--port", str(PORT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )

    for _ in range(40):
        try:
            httpx.get(f"{BASE_URL}/api/state", timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.terminate()
        raise RuntimeError("parade server did not start within 8 seconds")

    yield BASE_URL

    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
def page(live_server, page):
    """Playwright page pre-navigated to the running app, WebSocket connected."""
    page.goto(live_server)
    page.wait_for_selector(".conn-dot.ok", timeout=8000)
    return page
