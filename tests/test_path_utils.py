"""Tests for path utilities."""

import pytest
from tools.path_utils import resolve_cwd, resolve_path


class TestResolveCwd:
    """Tests for resolve_cwd function."""

    def test_none_returns_workspace_root(self):
        assert resolve_cwd(None, "/workspace") == "/workspace"

    def test_empty_string_returns_workspace_root(self):
        assert resolve_cwd("", "/workspace") == "/workspace"

    def test_whitespace_returns_workspace_root(self):
        assert resolve_cwd("   ", "/workspace") == "/workspace"

    def test_relative_path_simple(self):
        assert resolve_cwd("src", "/workspace") == "/workspace/src"

    def test_relative_path_with_dot(self):
        assert resolve_cwd("./src/app", "/workspace") == "/workspace/src/app"

    def test_relative_path_with_parent(self):
        assert resolve_cwd("../tmp", "/workspace") == "/tmp"

    def test_absolute_path_unchanged(self):
        assert resolve_cwd("/home/user", "/workspace") == "/home/user"

    def test_absolute_path_normalized(self):
        assert resolve_cwd("/tmp/../etc", "/workspace") == "/etc"

    def test_complex_relative_path(self):
        assert resolve_cwd("src/../tests/./unit", "/workspace") == "/workspace/tests/unit"


class TestResolvePath:
    """Tests for resolve_path function."""

    def test_absolute_path_unchanged(self):
        assert resolve_path("/etc/config", None, "/workspace") == "/etc/config"

    def test_absolute_path_normalized(self):
        assert resolve_path("/tmp/../etc/config", None, "/workspace") == "/etc/config"

    def test_relative_path_with_cwd(self):
        assert resolve_path("file.txt", "/workspace/src", "/workspace") == "/workspace/src/file.txt"

    def test_relative_path_without_cwd(self):
        assert resolve_path("file.txt", None, "/workspace") == "/workspace/file.txt"

    def test_relative_path_with_parent(self):
        assert resolve_path("../file.txt", "/workspace/src", "/workspace") == "/workspace/file.txt"
