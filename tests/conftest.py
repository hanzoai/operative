import asyncio
import os
import warnings
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def mock_screen_dimensions():
    with mock.patch.dict(
        os.environ, {"HEIGHT": "800", "WIDTH": "1280", "DISPLAY_NUM": "1"}
    ):
        yield


@pytest.fixture(autouse=True)
def suppress_unraisable_warnings():
    """Suppress RuntimeWarning and PytestUnraisableExceptionWarning during tests."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning, message="coroutine.*was never awaited")
        warnings.filterwarnings("ignore", category=pytest.PytestUnraisableExceptionWarning)
        yield


@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for each test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
