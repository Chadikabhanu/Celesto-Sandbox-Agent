import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable

from src.sandbox.audit import record_command_audit
from src.sandbox.exceptions import (
    CleanupFailedError,
    CommandBlockedError,
    GuestTimeoutError,
)
from src.sandbox.interface import CommandResult, Sandbox, SandboxProvider
from src.sandbox.policy import CommandPolicy, default_policy

logger = logging.getLogger(__name__)


class FakeSandbox(Sandbox):
    """Simulated in-memory sandbox for unit testing lifecycle, policy, and audit logic.

    WARNING: This is a test fake. It must NOT be presented as real Celesto sandbox evidence.
    It executes NO commands on the host machine.
    """

    is_fake: bool = True

    def __init__(
        self,
        sandbox_name: str,
        policy: CommandPolicy | None = None,
        simulate_ready_timeout: bool = False,
        simulate_cleanup_failure: bool = False,
        ready_probe_delay_seconds: float = 0.05,
    ) -> None:
        self._sandbox_name = sandbox_name
        self._execution_target = "celesto_sandbox"
        self._state = "provisioning"
        self._policy = policy or default_policy
        self._simulate_ready_timeout = simulate_ready_timeout
        self._simulate_cleanup_failure = simulate_cleanup_failure
        self._ready_probe_delay = ready_probe_delay_seconds

        # In-memory virtual guest filesystem
        self.guest_files: dict[str, bytes] = {}
        # History of commands executed inside this fake
        self.executed_commands: list[str] = []
        # Custom mock command responders: command -> CommandResult
        self.custom_command_handlers: dict[str, Callable[[str], CommandResult]] = {}
        self._is_deleted = False

    @property
    def sandbox_name(self) -> str:
        return self._sandbox_name

    @property
    def execution_target(self) -> str:
        return self._execution_target

    @property
    def state(self) -> str:
        return self._state

    async def wait_until_ready(self, timeout_seconds: float = 30.0) -> bool:
        """Probe guest environment until ready with bounded timeout."""
        if self._simulate_ready_timeout:
            await asyncio.sleep(min(timeout_seconds, 0.1))
            self._state = "failed"
            raise GuestTimeoutError(
                f"Guest sandbox '{self.sandbox_name}' failed to become ready within {timeout_seconds}s."
            )

        await asyncio.sleep(self._ready_probe_delay)
        self._state = "ready"
        return True

    async def run_command(self, command: str, timeout_seconds: float = 60.0) -> CommandResult:
        """Simulate command execution inside guest. Never falls back to host execution."""
        if self._is_deleted:
            raise RuntimeError(f"Cannot run command on deleted sandbox '{self.sandbox_name}'.")

        # 1. Enforce security policy
        decision = self._policy.evaluate(command)

        # 2. Append to audit log (Requirement 8 & 9)
        record_command_audit(
            sandbox_name=self.sandbox_name,
            command=command,
            decision="allowed" if decision.allowed else "blocked",
            execution_target=self.execution_target,
            extra={"simulated": True, "policy_reason": decision.reason},
        )

        # 3. Veto prohibited commands before guest dispatch
        if not decision.allowed:
            raise CommandBlockedError(
                message=decision.reason or "Command blocked by security policy",
                command=command,
                sandbox_name=self.sandbox_name,
            )

        # 4. Execute inside in-memory virtual guest environment
        self.executed_commands.append(command)

        # Check custom handlers
        if command in self.custom_command_handlers:
            return self.custom_command_handlers[command](command)

        # Built-in in-memory guest command simulations
        if command in ("id", "whoami"):
            return CommandResult(stdout="uid=1000(agent) gid=1000(agent)\n", stderr="", exit_code=0)
        elif command == "uname -a":
            return CommandResult(stdout="Linux celesto-guest 6.6.0-celesto #1 SMP x86_64\n", stderr="", exit_code=0)
        elif command.startswith("cat "):
            target_path = command.split(" ", 1)[1].strip()
            if target_path in self.guest_files:
                return CommandResult(stdout=self.guest_files[target_path].decode("utf-8", errors="replace"), stderr="", exit_code=0)
            return CommandResult(stdout="", stderr=f"cat: {target_path}: No such file or directory\n", exit_code=1)
        elif command == "pytest":
            return CommandResult(stdout="=== 1 passed in 0.05s ===\n", stderr="", exit_code=0)

        # Default simulated successful execution
        return CommandResult(stdout=f"Simulated execution: {command}\n", stderr="", exit_code=0)

    async def write_file(self, path: str, content: str | bytes) -> None:
        """Write file to in-memory guest filesystem."""
        if self._is_deleted:
            raise RuntimeError(f"Cannot write file to deleted sandbox '{self.sandbox_name}'.")
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.guest_files[path] = data

    async def read_file(self, path: str) -> bytes:
        """Read file from in-memory guest filesystem."""
        if self._is_deleted:
            raise RuntimeError(f"Cannot read file from deleted sandbox '{self.sandbox_name}'.")
        if path not in self.guest_files:
            raise FileNotFoundError(f"Guest file not found: {path}")
        return self.guest_files[path]

    async def delete(self) -> None:
        """Simulate sandbox deletion and resource teardown."""
        self._state = "terminating"
        if self._simulate_cleanup_failure:
            self._state = "failed"
            raise CleanupFailedError(f"Simulated teardown failure for sandbox '{self.sandbox_name}'")

        self.guest_files.clear()
        self._is_deleted = True
        self._state = "deleted"

    async def __aenter__(self) -> "FakeSandbox":
        await self.wait_until_ready()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.delete()


class FakeCelestoProvider(SandboxProvider):
    """Provider creating FakeSandbox instances for deterministic testing."""

    provider_name: str = "fake"

    def __init__(
        self,
        simulate_ready_timeout: bool = False,
        simulate_cleanup_failure: bool = False,
    ) -> None:
        self.simulate_ready_timeout = simulate_ready_timeout
        self.simulate_cleanup_failure = simulate_cleanup_failure
        self.created_sandboxes: list[FakeSandbox] = []

    async def create_sandbox(self, sandbox_name: str, **kwargs: Any) -> FakeSandbox:
        sbx = FakeSandbox(
            sandbox_name=sandbox_name,
            simulate_ready_timeout=self.simulate_ready_timeout,
            simulate_cleanup_failure=self.simulate_cleanup_failure,
            **kwargs,
        )
        self.created_sandboxes.append(sbx)
        return sbx
