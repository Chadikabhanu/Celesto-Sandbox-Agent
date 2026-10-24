import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import tempfile
from typing import Any

from src.sandbox.audit import record_command_audit
from src.sandbox.exceptions import (
    CleanupFailedError,
    CommandBlockedError,
    GuestTimeoutError,
    ProviderConfigurationError,
)
from src.sandbox.interface import CommandResult, Sandbox, SandboxProvider
from src.sandbox.policy import CommandPolicy, default_policy

logger = logging.getLogger(__name__)


def _get_celesto_sdk():
    """Lazily load the Celesto SDK and its components.

    Keeps provider initialization lazy so the control plane can start
    without requiring Celesto or its binary dependencies.
    """
    try:
        import celesto
        from celesto.callbacks import Callback
        from celesto.exceptions import CommandBlockedError as CelestoCommandBlockedError
        return celesto, Callback, CelestoCommandBlockedError
    except ImportError as exc:
        raise ProviderConfigurationError(
            f"Celesto SDK is not installed or cannot be loaded: {exc}. "
            "Ensure 'celesto' is installed."
        ) from exc


class CelestoSafetyCallback:
    """Attached to Celesto to intercept and audit every guest command before dispatch."""

    def __init__(self, sandbox_name: str, policy: CommandPolicy | None = None) -> None:
        self.sandbox_name = sandbox_name
        self.policy = policy or default_policy

    def on_pre_run(self, ctx: Any) -> None:
        command = getattr(ctx, "command", "")
        decision = self.policy.evaluate(command)

        # Log every attempted command (Requirement 8 & 9)
        record_command_audit(
            sandbox_name=self.sandbox_name,
            command=command,
            decision="allowed" if decision.allowed else "blocked",
            execution_target="celesto_sandbox",
            extra={"hook": "on_pre_run", "reason": decision.reason},
        )

        if not decision.allowed:
            _, _, CelestoCommandBlockedError = _get_celesto_sdk()
            raise CelestoCommandBlockedError(
                message=decision.reason or "Command blocked by security policy",
                vm_id=getattr(ctx, "vm_id", None),
                command=command,
            )


class CelestoSandbox(Sandbox):
    """Real Celesto guest sandbox adapter wrapping the Celesto SDK runtime."""

    def __init__(
        self,
        sandbox_name: str,
        provider: str = "cloud",  # "local" or "cloud"
        template_id: str = "scratch",
        api_key: str | None = None,
        policy: CommandPolicy | None = None,
    ) -> None:
        self._sandbox_name = sandbox_name
        self._execution_target = "celesto_sandbox"
        self._provider = provider.lower()
        self._template_id = template_id
        self._api_key = api_key
        self._policy = policy or default_policy
        self._state = "provisioning"
        self._vm: Any = None
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

    def _initialize_vm(self) -> Any:
        # Validate provider and credentials prior to attempting SDK import
        if self._provider not in ("cloud", "local"):
            raise ProviderConfigurationError(
                f"Unsupported CELESTO_PROVIDER '{self._provider}'. Must be 'local' or 'cloud'."
            )

        if self._provider == "cloud" and not self._api_key:
            raise ProviderConfigurationError(
                "CELESTO_API_KEY environment variable is required for provider='cloud'."
            )

        celesto, Callback, _ = _get_celesto_sdk()

        class DynamicGuard(Callback):
            def __init__(self, guard_impl: CelestoSafetyCallback):
                self.guard = guard_impl

            def on_pre_run(self, ctx: Any) -> None:
                self.guard.on_pre_run(ctx)

        safety_guard = CelestoSafetyCallback(self.sandbox_name, self._policy)
        callback_instance = DynamicGuard(safety_guard)

        kwargs: dict[str, Any] = {
            "template_id": self._template_id,
            "callbacks": [callback_instance],
            "provider": self._provider,
        }

        if self._provider == "cloud":
            kwargs["api_key"] = self._api_key

        logger.info(
            "Creating Celesto sandbox '%s' (provider=%s, template=%s)",
            self.sandbox_name,
            self._provider,
            self._template_id,
        )
        return celesto.Celesto(**kwargs)

    async def wait_until_ready(self, timeout_seconds: float = 30.0) -> bool:
        """Probe guest environment until ready with bounded timeout."""
        if self._vm is None:
            self._vm = self._initialize_vm()

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds

        logger.info("Probing Celesto sandbox '%s' readiness (timeout=%.1fs)...", self.sandbox_name, timeout_seconds)

        while loop.time() < deadline:
            try:
                # Probe readiness using SDK's can_run_commands or non-destructive probe
                if hasattr(self._vm, "can_run_commands") and self._vm.can_run_commands():
                    self._state = "ready"
                    return True
                # Fallback: run a fast no-op via guest API
                result = await loop.run_in_executor(None, lambda: self._vm.run("true", timeout=5))
                if getattr(result, "ok", False) or getattr(result, "exit_code", -1) == 0:
                    self._state = "ready"
                    return True
            except Exception as probe_err:
                logger.debug("Readiness probe attempt failed for %s: %s", self.sandbox_name, probe_err)

            await asyncio.sleep(1.0)

        self._state = "failed"
        raise GuestTimeoutError(
            f"Celesto sandbox '{self.sandbox_name}' failed readiness probe within {timeout_seconds}s."
        )

    async def run_command(self, command: str, timeout_seconds: float = 60.0) -> CommandResult:
        """Run command strictly inside the Celesto guest environment."""
        if self._is_deleted:
            raise RuntimeError(f"Cannot run command on deleted sandbox '{self.sandbox_name}'.")

        # Explicit policy evaluation & audit logging before reaching SDK
        decision = self._policy.evaluate(command)
        record_command_audit(
            sandbox_name=self.sandbox_name,
            command=command,
            decision="allowed" if decision.allowed else "blocked",
            execution_target=self.execution_target,
            extra={"policy_reason": decision.reason},
        )

        if not decision.allowed:
            raise CommandBlockedError(
                message=decision.reason or "Command blocked by security policy",
                command=command,
                sandbox_name=self.sandbox_name,
            )

        if self._vm is None:
            self._vm = self._initialize_vm()

        loop = asyncio.get_running_loop()
        try:
            sdk_result = await loop.run_in_executor(
                None,
                lambda: self._vm.run(command, timeout=int(timeout_seconds)),
            )
            return CommandResult(
                stdout=getattr(sdk_result, "stdout", "") or "",
                stderr=getattr(sdk_result, "stderr", "") or "",
                exit_code=getattr(sdk_result, "exit_code", 0),
            )
        except Exception as exc:
            # Check if this was a veto exception from Celesto callback
            if "CommandBlockedError" in type(exc).__name__:
                raise CommandBlockedError(str(exc), command=command, sandbox_name=self.sandbox_name) from exc
            logger.error("Error executing command in guest '%s': %s", self.sandbox_name, exc)
            raise

    async def write_file(self, path: str, content: str | bytes) -> None:
        """Write file into guest filesystem using Celesto upload_file."""
        if self._is_deleted:
            raise RuntimeError(f"Cannot write file to deleted sandbox '{self.sandbox_name}'.")

        if self._vm is None:
            self._vm = self._initialize_vm()

        data = content.encode("utf-8") if isinstance(content, str) else content

        with tempfile.NamedTemporaryFile(prefix="celesto-stage-", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._vm.upload_file(tmp_path, path),
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    async def read_file(self, path: str) -> bytes:
        """Read file from guest filesystem using Celesto download_file."""
        if self._is_deleted:
            raise RuntimeError(f"Cannot read file from deleted sandbox '{self.sandbox_name}'.")

        if self._vm is None:
            self._vm = self._initialize_vm()

        with tempfile.NamedTemporaryFile(prefix="celesto-read-", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._vm.download_file(path, tmp_path),
            )
            return tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

    async def delete(self) -> None:
        """Clean up Celesto guest sandbox. Records failures visibly."""
        self._state = "terminating"
        if self._vm is not None and not self._is_deleted:
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, self._vm.delete)
                logger.info("Successfully cleaned up Celesto sandbox '%s'.", self.sandbox_name)
            except Exception as exc:
                self._state = "failed"
                logger.error("Teardown failed for Celesto sandbox '%s': %s", self.sandbox_name, exc, exc_info=True)
                raise CleanupFailedError(
                    f"Teardown failed for Celesto sandbox '{self.sandbox_name}': {exc}"
                ) from exc
            finally:
                self._is_deleted = True
                self._state = "deleted"
        else:
            self._is_deleted = True
            self._state = "deleted"

    async def __aenter__(self) -> "CelestoSandbox":
        await self.wait_until_ready()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.delete()


class CelestoProvider(SandboxProvider):
    """Provider provisioning real Celesto microVM sandboxes."""

    def __init__(self, provider: str = "cloud", template_id: str = "scratch") -> None:
        self._provider = provider.lower()
        self._template_id = template_id

    @property
    def provider_name(self) -> str:
        return f"celesto-{self._provider}"

    async def create_sandbox(self, sandbox_name: str, **kwargs: Any) -> CelestoSandbox:
        api_key = os.environ.get("CELESTO_API_KEY")
        return CelestoSandbox(
            sandbox_name=sandbox_name,
            provider=self._provider,
            template_id=self._template_id,
            api_key=api_key,
            **kwargs,
        )
