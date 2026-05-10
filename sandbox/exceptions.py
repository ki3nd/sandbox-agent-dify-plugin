"""Sandbox exceptions."""


class SandboxError(Exception):
    """Base exception for sandbox errors."""

    pass


class SandboxNotFoundError(SandboxError):
    """Sandbox with given ID does not exist."""

    def __init__(self, sandbox_id: str, provider: str):
        self.sandbox_id = sandbox_id
        self.provider = provider
        super().__init__(
            f"Sandbox '{sandbox_id}' not found on {provider}. "
            f"Please create a sandbox first via {provider} dashboard or API."
        )


class SandboxConnectionError(SandboxError):
    """Failed to connect to sandbox."""

    pass


class SandboxExecError(SandboxError):
    """Command execution failed."""

    pass


class SandboxTimeoutError(SandboxError):
    """Command exceeded timeout."""

    pass


class SandboxFileNotFoundError(SandboxError):
    """File not found in sandbox."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"File not found in sandbox: {path}")
