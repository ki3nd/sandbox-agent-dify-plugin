"""Sandbox factory for creating sandbox instances."""

from enum import Enum

from sandbox.base import AbstractSandbox


class SandboxProvider(str, Enum):
    """Supported sandbox providers."""

    E2B = "e2b"
    DAYTONA = "daytona"
    # Future providers:
    # VERCEL = "vercel"
    # MODAL = "modal"


class SandboxFactory:
    """Factory for creating and connecting to sandboxes."""

    @staticmethod
    async def connect(
        provider: SandboxProvider | str,
        sandbox_id: str,
        *,
        api_key: str | None = None,
        api_url: str | None = None,
    ) -> AbstractSandbox:
        """Connect to an existing sandbox.

        Args:
            provider: Sandbox provider (e2b, daytona)
            sandbox_id: ID of existing sandbox
            api_key: API key for the provider
            api_url: Optional API URL (for Daytona)

        Returns:
            Connected sandbox instance

        Raises:
            SandboxNotFoundError: Sandbox does not exist
            SandboxConnectionError: Failed to connect
            ValueError: Invalid provider or missing credentials
        """
        # Normalize provider to enum
        if isinstance(provider, str):
            try:
                provider = SandboxProvider(provider.lower())
            except ValueError:
                raise ValueError(
                    f"Unknown provider: {provider}. "
                    f"Supported: {[p.value for p in SandboxProvider]}"
                )

        sandbox: AbstractSandbox

        if provider == SandboxProvider.E2B:
            if not api_key:
                raise ValueError("E2B requires api_key")
            from sandbox.providers.e2b import E2BSandbox

            sandbox = E2BSandbox(api_key=api_key)

        elif provider == SandboxProvider.DAYTONA:
            if not api_key:
                raise ValueError("Daytona requires api_key")
            from sandbox.providers.daytona import DaytonaSandbox

            sandbox = DaytonaSandbox(api_key=api_key, api_url=api_url)

        else:
            raise ValueError(f"Provider {provider} not yet implemented")

        await sandbox.connect(sandbox_id)
        return sandbox
