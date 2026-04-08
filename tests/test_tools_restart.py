# tests/test_tools_restart.py
import sys
import importlib
import pytest
from unittest.mock import patch, MagicMock


def _get_restart_cmd(platform_str):
    """Helper: patch sys.platform and extract the command passed to Popen."""
    with patch("sys.platform", platform_str), \
         patch("subprocess.Popen") as mock_popen:
        import core.tools as tools_mod
        importlib.reload(tools_mod)
        tools_mod._restart_server()
        assert mock_popen.called
        return mock_popen.call_args[0][0]  # first positional arg = the shell command


def test_restart_uses_systemctl_on_linux():
    cmd = _get_restart_cmd("linux")
    assert "systemctl" in cmd
    assert "adjutant" in cmd


def test_restart_uses_launchctl_on_mac():
    cmd = _get_restart_cmd("darwin")
    assert "launchctl" in cmd
    assert "adjutantapp" in cmd


def test_restart_uses_schtasks_on_windows():
    cmd = _get_restart_cmd("win32")
    assert "schtasks" in cmd
    assert "Adjutant" in cmd
