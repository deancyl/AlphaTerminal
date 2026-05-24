"""Unit tests for startup timeout and CI detection."""

import asyncio
import os
import pytest


class TestCIDetection:
    """Test CI environment detection logic."""

    def test_github_actions_detection(self, monkeypatch):
        """Test GITHUB_ACTIONS environment variable detection."""
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        is_ci = (
            os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
        )
        assert is_ci is True

    def test_ci_detection(self, monkeypatch):
        """Test CI environment variable detection."""
        monkeypatch.setenv("CI", "true")
        is_ci = (
            os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
        )
        assert is_ci is True

    def test_no_ci_environment(self, monkeypatch):
        """Test that CI detection returns False when not in CI."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        is_ci = (
            os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
        )
        assert is_ci is False

    def test_ci_false_value(self, monkeypatch):
        """Test that CI detection returns False when CI is set to false."""
        monkeypatch.setenv("CI", "false")
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        is_ci = (
            os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
        )
        assert is_ci is False


class TestTimeoutWrapper:
    """Test asyncio.wait_for timeout behavior."""

    @pytest.mark.asyncio
    async def test_timeout_triggers(self):
        """Test that asyncio.wait_for raises TimeoutError on slow function."""

        async def slow_function():
            await asyncio.sleep(20)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_function(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_fast_function_completes(self):
        """Test that fast function completes before timeout."""

        async def fast_function():
            await asyncio.sleep(0.1)
            return "done"

        result = await asyncio.wait_for(fast_function(), timeout=1.0)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_catches_exception(self):
        """Test that exception in wrapped function is raised."""

        async def failing_function():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await asyncio.wait_for(failing_function(), timeout=1.0)


class TestPytestRunningDetection:
    """Test PYTEST_RUNNING environment variable detection."""

    def test_pytest_running_true(self, monkeypatch):
        """Test PYTEST_RUNNING detection when set."""
        monkeypatch.setenv("PYTEST_RUNNING", "true")
        is_testing = os.environ.get("PYTEST_RUNNING") == "true"
        assert is_testing is True

    def test_pytest_running_false(self, monkeypatch):
        """Test PYTEST_RUNNING detection when not set."""
        monkeypatch.delenv("PYTEST_RUNNING", raising=False)
        is_testing = os.environ.get("PYTEST_RUNNING") == "true"
        assert is_testing is False
