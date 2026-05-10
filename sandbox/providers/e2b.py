"""E2B sandbox implementation using official e2b SDK."""

from sandbox.base import AbstractSandbox, CommandResult
from sandbox.exceptions import (
    SandboxConnectionError,
    SandboxFileNotFoundError,
    SandboxNotFoundError,
)

try:
    from e2b import AsyncSandbox
except ImportError:
    AsyncSandbox = None  # type: ignore


class E2BSandbox(AbstractSandbox):
    """E2B sandbox implementation.

    Uses official `e2b` SDK: https://github.com/e2b-dev/e2b-python
    """

    def __init__(self, api_key: str):
        """Initialize E2B sandbox.

        Args:
            api_key: E2B API key
        """
        if AsyncSandbox is None:
            raise ImportError(
                "e2b package is required for E2BSandbox. "
                "Install it with: pip install e2b"
            )
        self._api_key = api_key
        self._sandbox = None

    async def connect(self, sandbox_id: str) -> None:
        """Connect to an existing E2B sandbox by ID.

        E2B auto-resumes paused sandboxes on connect.
        """
        try:
            self._sandbox = await AsyncSandbox.connect(
                sandbox_id=sandbox_id,
                api_key=self._api_key,
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                raise SandboxNotFoundError(sandbox_id, "E2B") from e
            raise SandboxConnectionError(
                f"Failed to connect to E2B sandbox: {e}"
            ) from e

    async def exec(
        self,
        command: str,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        """Execute a shell command in E2B sandbox."""
        if self._sandbox is None:
            raise SandboxConnectionError("Not connected to sandbox")

        try:
            result = await self._sandbox.commands.run(
                command,
                timeout=int(timeout) if timeout else None,
            )
            return CommandResult(
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                exit_code=result.exit_code,
            )
        except TimeoutError as e:
            return CommandResult(
                stdout="",
                stderr=str(e),
                exit_code=124,  # Standard timeout exit code
                timed_out=True,
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg:
                return CommandResult(
                    stdout="",
                    stderr=str(e),
                    exit_code=124,
                    timed_out=True,
                )
            raise SandboxConnectionError(f"Command execution failed: {e}") from e

    async def read_file(self, path: str) -> bytes:
        """Read file content from E2B sandbox."""
        if self._sandbox is None:
            raise SandboxConnectionError("Not connected to sandbox")

        try:
            content = await self._sandbox.files.read(path, format="bytes")
            return content
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "no such file" in error_msg:
                raise SandboxFileNotFoundError(path) from e
            raise

    async def write_file(self, path: str, content: bytes) -> None:
        """Write file content to E2B sandbox."""
        if self._sandbox is None:
            raise SandboxConnectionError("Not connected to sandbox")

        await self._sandbox.files.write(path, content)

    async def is_running(self) -> bool:
        """Check if E2B sandbox is running."""
        if self._sandbox is None:
            return False
        try:
            return await self._sandbox.is_running()
        except Exception:
            return False

    async def close(self) -> None:
        """Close connection to E2B sandbox (does not kill sandbox)."""
        # E2B SDK doesn't require explicit close for connection
        # Sandbox continues running until timeout or explicit kill
        self._sandbox = None
