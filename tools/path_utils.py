"""Path utilities for sandbox tools."""

import os


def resolve_cwd(cwd: str | None, workspace_root: str) -> str:
    """Resolve cwd to absolute path.

    - None or empty → workspace_root
    - Relative path → workspace_root + cwd
    - Absolute path → as-is (normalized)

    Args:
        cwd: Working directory from tool args (may be None, empty, relative, or absolute)
        workspace_root: Default workspace root from config

    Returns:
        Absolute normalized path

    Examples:
        >>> resolve_cwd(None, "/workspace")
        '/workspace'
        >>> resolve_cwd("", "/workspace")
        '/workspace'
        >>> resolve_cwd("src", "/workspace")
        '/workspace/src'
        >>> resolve_cwd("./src/app", "/workspace")
        '/workspace/src/app'
        >>> resolve_cwd("../tmp", "/workspace")
        '/tmp'
        >>> resolve_cwd("/home/user", "/workspace")
        '/home/user'
        >>> resolve_cwd("/tmp/../etc", "/workspace")
        '/etc'
    """
    if not cwd or cwd.strip() == "":
        return workspace_root

    if cwd.startswith("/"):
        # Absolute path → normalize only
        return os.path.normpath(cwd)
    else:
        # Relative path → join with workspace_root
        return os.path.normpath(f"{workspace_root}/{cwd}")


def resolve_path(path: str, cwd: str | None, workspace_root: str) -> str:
    """Resolve file path to absolute path.

    Used by apply_patch and other file operations.

    - Absolute path → normalized as-is
    - Relative path → resolved from cwd (which defaults to workspace_root)

    Args:
        path: File path (may be relative or absolute)
        cwd: Current working directory (may be None)
        workspace_root: Default workspace root from config

    Returns:
        Absolute normalized path
    """
    if path.startswith("/"):
        return os.path.normpath(path)

    base = cwd if cwd else workspace_root
    return os.path.normpath(f"{base}/{path}")
