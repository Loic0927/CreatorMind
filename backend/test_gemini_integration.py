"""Opt-in live Gemini smoke test.

This module performs no provider configuration or network request during import or
pytest collection. Set RUN_GEMINI_INTEGRATION_TESTS=1 explicitly to opt in.
"""

import os

import pytest

from backend.services.gemini import generate_gemini_content


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GEMINI_INTEGRATION_TESTS") != "1",
    reason="Live Gemini integration tests require explicit opt-in.",
)


def test_live_gemini_smoke():
    result = generate_gemini_content(
        "Reply with a brief confirmation that the service is available."
    )
    assert result
