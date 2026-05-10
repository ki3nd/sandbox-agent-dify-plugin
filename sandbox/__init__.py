"""Sandbox abstraction layer for remote sandbox providers."""

from sandbox.base import AbstractSandbox, CommandResult
from sandbox.exceptions import (
    SandboxError,
    SandboxNotFoundError,
    SandboxConnectionError,
    SandboxExecError,
    SandboxTimeoutError,
    SandboxFileNotFoundError,
)
from sandbox.factory import SandboxFactory, SandboxProvider

__all__ = [
    # Base
    "AbstractSandbox",
    "CommandResult",
    # Exceptions
    "SandboxError",
    "SandboxNotFoundError",
    "SandboxConnectionError",
    "SandboxExecError",
    "SandboxTimeoutError",
    "SandboxFileNotFoundError",
    # Factory
    "SandboxFactory",
    "SandboxProvider",
]
