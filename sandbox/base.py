"""Abstract base class for sandbox providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CommandResult:
    """Result of a command execution in sandbox."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    truncated: bool = field(default=False, repr=False)

    def ok(self) -> bool:
        """Return True if command succeeded (exit_code == 0)."""
        return self.exit_code == 0

    def format(self, max_chars: int | None = None) -> str:
        """Format output for LLM context.

        Args:
            max_chars: Maximum characters for combined output. If exceeded,
                       output is truncated and self.truncated is set to True.

        Returns:
            Formatted string with stdout, stderr, and exit_code tags.
        """
        stdout = self.stdout
        stderr = self.stderr

        if max_chars:
            combined_len = len(stdout) + len(stderr)
            if combined_len > max_chars:
                self.truncated = True
                # Prioritize stdout, then stderr
                if len(stdout) > max_chars:
                    stdout = stdout[:max_chars] + "\n... [truncated]"
                    stderr = ""
                else:
                    remaining = max_chars - len(stdout)
                    stderr = stderr[:remaining] + "\n... [truncated]"

        parts = [f"<stdout>\n{stdout}\n</stdout>"]
        if stderr:
            parts.append(f"<stderr>\n{stderr}\n</stderr>")
        parts.append(f"<exit_code>{self.exit_code}</exit_code>")

        if self.timed_out:
            parts.insert(0, "[Command timed out]")
        if self.truncated:
            parts.append("[Output truncated]")

        return "\n".join(parts)


class AbstractSandbox(ABC):
    """Abstract base class for all sandbox providers.

    All implementations MUST use the official SDK from the provider.

    Sandbox layer is simple:
    - exec(command, timeout) - no cwd, no env
    - read_file(path) / write_file(path, content)
    - connect(sandbox_id) / close()

    Working directory (cwd) is handled at the Tool layer by prepending
    `cd {cwd} && ` to the command string.
    """

    @abstractmethod
    async def connect(self, sandbox_id: str) -> None:
        """Connect to an existing sandbox by ID.

        - If sandbox exists and running → connect successfully
        - If sandbox exists but stopped → start it, then connect
        - If sandbox does not exist → raise SandboxNotFoundError

        Args:
            sandbox_id: The sandbox ID provided by user

        Raises:
            SandboxNotFoundError: Sandbox with given ID does not exist
            SandboxConnectionError: Failed to connect to sandbox
        """
        ...

    @abstractmethod
    async def exec(
        self,
        command: str,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        """Execute a shell command in the sandbox.

        Note: Sandbox layer does NOT have `cwd` parameter.
        Working directory is handled at the Tool layer by prepending
        `cd {cwd} && ` to the command string.

        Args:
            command: Full shell command string to execute
            timeout: Optional timeout in seconds

        Returns:
            CommandResult with stdout, stderr, exit_code
        """
        ...

    @abstractmethod
    async def read_file(self, path: str) -> bytes:
        """Read file content from sandbox.

        Args:
            path: Absolute path to file in sandbox

        Returns:
            File content as bytes

        Raises:
            SandboxFileNotFoundError: File does not exist
        """
        ...

    @abstractmethod
    async def write_file(self, path: str, content: bytes) -> None:
        """Write file content to sandbox.

        Args:
            path: Absolute path to file in sandbox
            content: File content as bytes
        """
        ...

    @abstractmethod
    async def is_running(self) -> bool:
        """Check if sandbox is currently running."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close connection (does NOT delete sandbox)."""
        ...

    async def __aenter__(self) -> "AbstractSandbox":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
