from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@runtime_checkable
class Sandbox(Protocol):
    """Abstract interface for a guest sandbox environment."""

    @property
    def sandbox_name(self) -> str:
        """Unique identifier matching ^sbx-[a-z0-9]{8,}$."""
        ...

    @property
    def execution_target(self) -> str:
        """Target environment name ('celesto_sandbox')."""
        ...

    @property
    def state(self) -> str:
        """Current lifecycle state."""
        ...

    async def wait_until_ready(self, timeout_seconds: float = 30.0) -> bool:
        """Probe guest environment until ready or bounded timeout expires."""
        ...

    async def run_command(self, command: str, timeout_seconds: float = 60.0) -> CommandResult:
        """Execute command inside the guest environment.

        Must enforce security policy, audit logging, and never fall back to host execution.
        """
        ...

    async def write_file(self, path: str, content: str | bytes) -> None:
        """Write file inside the guest filesystem."""
        ...

    async def read_file(self, path: str) -> bytes:
        """Read file from the guest filesystem."""
        ...

    async def delete(self) -> None:
        """Tear down and clean up sandbox resources."""
        ...

    async def __aenter__(self) -> "Sandbox":
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        ...


@runtime_checkable
class SandboxProvider(Protocol):
    """Factory for provisioning sandboxes."""

    @property
    def provider_name(self) -> str:
        ...

    async def create_sandbox(self, sandbox_name: str, **kwargs) -> Sandbox:
        ...
