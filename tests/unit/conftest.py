"""
pytest configuration for tests/unit/.

When pytest-asyncio is installed this file does nothing — the built-in
pytest-asyncio plugin handles @pytest.mark.asyncio tests.

When pytest-asyncio is absent we patch pytest's internal
pytest_pyfunc_call hook so that async test functions
(annotated with @pytest.mark.asyncio) are executed via asyncio.run().
nest_asyncio is applied first so that nested event loops work.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the project root is on sys.path so 'api' resolves to the api/ package.
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Allow nested event loops so asyncio.run() can be called inside other loops
try:
    import nest_asyncio

    nest_asyncio.apply()
except ImportError:
    pass

import pytest


def _run_async_test(func):
    """Run an async test function using the current event loop (or a new one)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — asyncio.run() creates one safely
        return asyncio.run(func())

    # There IS a running loop (nested test harness).
    # nest_asyncio.patch() was applied above, so run_until_complete works.
    return loop.run_until_complete(func())


# Check whether pytest-asyncio is available — if so, let it do its job.
try:
    import pytest_asyncio

    _ASYNCIO_AVAILABLE = True
except ImportError:
    _ASYNCIO_AVAILABLE = False


if not _ASYNCIO_AVAILABLE:
    # Override pytest_pyfunc_call to handle async functions marked with
    # @pytest.mark.asyncio.  Without trylast=True this hook runs before
    # the built-in runner so we can execute the coroutine ourselves
    # before pytest skips it.
    @pytest.hookimpl
    def pytest_pyfunc_call(pyfuncitem):
        if pyfuncitem.get_closest_marker("asyncio") and asyncio.iscoroutinefunction(
            pyfuncitem.obj
        ):
            _run_async_test(pyfuncitem.obj)
            return True
        return None  # let the built-in runner handle non-async tests
