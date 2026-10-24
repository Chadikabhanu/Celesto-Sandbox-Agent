"""Sandbox exception hierarchy."""


class SandboxError(Exception):
    """Base exception for all sandbox operations."""
    pass


class CommandBlockedError(SandboxError):
    """Raised when a command violates the security command policy."""

    def __init__(self, message: str, command: str | None = None, sandbox_name: str | None = None) -> None:
        super().__init__(message)
        self.command = command
        self.sandbox_name = sandbox_name


class GuestTimeoutError(SandboxError):
    """Raised when guest readiness or command execution exceeds bounded timeout."""
    pass


class CleanupFailedError(SandboxError):
    """Raised when sandbox teardown fails."""
    pass


class ProviderConfigurationError(SandboxError):
    """Raised when provider configuration or required credentials are missing."""
    pass


class HostEscapeAttemptError(SandboxError):
    """Raised when an operation attempts host-level execution or fallback."""
    pass
