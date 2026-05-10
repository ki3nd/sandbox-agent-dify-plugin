"""Daytona sandbox implementation using official daytona SDK."""

from sandbox.base import AbstractSandbox, CommandResult
from sandbox.exceptions import (
    SandboxConnectionError,
    SandboxFileNotFoundError,
    SandboxNotFoundError,
)

try:
    from daytona import AsyncDaytona, DaytonaConfig, SandboxState
except ImportError:
    AsyncDaytona = None  # type: ignore
    DaytonaConfig = None  # type: ignore
    SandboxState = None  # type: ignore


class DaytonaSandbox(AbstractSandbox):
    """Daytona sandbox implementation.

    Uses official `daytona` SDK: https://github.com/daytonaio/sdk
    """

    def __init__(self, api_key: str, api_url: str | None = None):
        """Initialize Daytona sandbox.

        Args:
            api_key: Daytona API key
            api_url: Optional Daytona API URL (defaults to cloud)
        """
        if AsyncDaytona is None:
            raise ImportError(
                "daytona package is required for DaytonaSandbox. "
                "Install it with: pip install daytona"
            )
        config = DaytonaConfig(api_key=api_key)
        if api_url:
            config.api_url = api_url
        self._client = AsyncDaytona(config)
        self._sandbox = None

    async def connect(self, sandbox_id: str) -> None:
        """Connect to an existing Daytona sandbox by ID.

        If sandbox is stopped, it will be started.
        """
        try:
            self._sandbox = await self._client.get(sandbox_id)

            # If stopped, start it
            if self._sandbox.state == SandboxState.STOPPED:
                await self._sandbox.start()
            elif self._sandbox.state != SandboxState.STARTED:
                raise SandboxConnectionError(
                    f"Sandbox is in unexpected state: {self._sandbox.state}"
                )
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                raise SandboxNotFoundError(sandbox_id, "Daytona") from e
            if isinstance(e, SandboxConnectionError):
                raise
            raise SandboxConnectionError(
                f"Failed to connect to Daytona sandbox: {e}"
            ) from e

    async def exec(
        self,
        command: str,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        """Execute a shell command in Daytona sandbox."""
        if self._sandbox is None:
            raise SandboxConnectionError("Not connected to sandbox")

        try:
            result = await self._sandbox.process.exec(
                command,
                timeout=int(timeout) if timeout else None,
            )
            return CommandResult(
                stdout=result.result or "",
                stderr="",  # Daytona combines stdout/stderr
                exit_code=result.exit_code or 0,
            )
        except TimeoutError as e:
            return CommandResult(
                stdout="",
                stderr=str(e),
                exit_code=124,
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
        """Read file content from Daytona sandbox."""
        if self._sandbox is None:
            raise SandboxConnectionError("Not connected to sandbox")

        try:
            content = await self._sandbox.fs.download_file(path)
            return content
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "no such file" in error_msg:
                raise SandboxFileNotFoundError(path) from e
            raise

    async def write_file(self, path: str, content: bytes) -> None:
        """Write file content to Daytona sandbox."""
        if self._sandbox is None:
            raise SandboxConnectionError("Not connected to sandbox")

        await self._sandbox.fs.upload_file(content, path)

    async def is_running(self) -> bool:
        """Check if Daytona sandbox is running."""
        if self._sandbox is None:
            return False
        try:
            await self._sandbox.refresh_data()
            return self._sandbox.state == SandboxState.STARTED
        except Exception:
            return False

    async def close(self) -> None:
        """Close connection to Daytona sandbox."""
        if self._client:
            await self._client.close()
        self._sandbox = None
