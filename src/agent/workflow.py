import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

from src.db import check_db_health, insert_run, update_run_state
from src.sandbox.exceptions import (
    CleanupFailedError,
    CommandBlockedError,
    GuestTimeoutError,
    SandboxError,
)
from src.sandbox.factory import get_sandbox_provider
from src.sandbox.interface import CommandResult, Sandbox, SandboxProvider
from src.sandbox.naming import generate_sandbox_name

logger = logging.getLogger(__name__)


@dataclass
class ExecutionSummary:
    sandbox_name: str
    task_id: str
    success: bool
    results: list[CommandResult] = field(default_factory=list)
    error_message: str | None = None
    cleaned_up: bool = False
    duration_seconds: float = 0.0


class AgentExecutionWorkflow:
    """Agent execution workflow coordinating sandbox lifecycle and verification.

    Enforces:
    - Unique sandbox naming (^sbx-[a-z0-9]{8,}$)
    - Bounded guest readiness probing
    - Strict guest execution (no host subprocess fallback)
    - Full command audit logging
    - Ledger transition tracking
    - Guaranteed cleanup on success, exceptions, timeouts, and cancellation
    """

    def __init__(
        self,
        provider: SandboxProvider | None = None,
        record_ledger: bool = True,
        ready_timeout_seconds: float = 30.0,
    ) -> None:
        self.provider = provider
        self.record_ledger = record_ledger
        self.ready_timeout_seconds = ready_timeout_seconds

    async def _safe_record_run(self, sandbox_name: str, task_id: str) -> None:
        if not self.record_ledger:
            return
        try:
            if await check_db_health():
                await insert_run(
                    sandbox_name=sandbox_name,
                    state="provisioning",
                    execution_target="celesto_sandbox",
                    task_id=task_id,
                )
        except Exception as exc:
            logger.warning("Could not record initial run in ledger: %s", exc)

    async def _safe_update_state(
        self,
        sandbox_name: str,
        state: str,
        metadata_patch: dict[str, Any] | None = None,
    ) -> None:
        if not self.record_ledger:
            return
        try:
            if await check_db_health():
                await update_run_state(sandbox_name, state, metadata_patch)
        except Exception as exc:
            logger.warning("Could not update state '%s' in ledger for %s: %s", state, sandbox_name, exc)

    async def execute_task(
        self,
        task_id: str,
        commands: list[str],
        files: dict[str, str | bytes] | None = None,
        sandbox_name: str | None = None,
    ) -> ExecutionSummary:
        """Run a task inside an isolated sandbox with complete lifecycle tracking."""
        start_time = datetime.now(timezone.utc)
        target_sandbox_name = sandbox_name or generate_sandbox_name()

        logger.info("Starting execution workflow for task '%s' in sandbox '%s'", task_id, target_sandbox_name)
        await self._safe_record_run(target_sandbox_name, task_id)

        # Lazy provider resolution
        provider = self.provider or get_sandbox_provider()
        sandbox: Sandbox = await provider.create_sandbox(target_sandbox_name)

        results: list[CommandResult] = []
        error_message: str | None = None
        success = False
        final_ledger_state = "failed"
        cleaned_up = False

        try:
            # 1. Probe guest until ready with bounded timeout
            await self._safe_update_state(target_sandbox_name, "provisioning")
            await sandbox.wait_until_ready(timeout_seconds=self.ready_timeout_seconds)
            await self._safe_update_state(target_sandbox_name, "ready")

            # 2. Transition to running
            await self._safe_update_state(target_sandbox_name, "running")

            # 3. Seed files into guest filesystem
            if files:
                for path, content in files.items():
                    logger.debug("Writing guest file '%s' in sandbox '%s'", path, target_sandbox_name)
                    await sandbox.write_file(path, content)

            # 4. Execute commands strictly through guest API
            for cmd in commands:
                logger.debug("Executing guest command '%s' in sandbox '%s'", cmd, target_sandbox_name)
                res = await sandbox.run_command(cmd)
                results.append(res)
                if not res.ok:
                    error_message = f"Command failed with exit code {res.exit_code}: {cmd}"
                    logger.warning(error_message)
                    final_ledger_state = "failed"
                    break
            else:
                success = True
                final_ledger_state = "completed"

        except (CommandBlockedError, GuestTimeoutError, SandboxError) as exc:
            error_message = str(exc)
            final_ledger_state = "failed"
            logger.error("Sandbox error during task execution for %s: %s", target_sandbox_name, exc)
            raise
        except (Exception, asyncio.CancelledError, KeyboardInterrupt) as exc:
            error_message = f"Unexpected failure ({type(exc).__name__}): {exc}"
            final_ledger_state = "failed"
            logger.error("Unexpected error during task execution for %s: %s", target_sandbox_name, exc, exc_info=True)
            raise
        finally:
            # 5. Guaranteed cleanup on success, exceptions, timeouts, and interrupts
            logger.info("Executing teardown for sandbox '%s'", target_sandbox_name)
            await self._safe_update_state(target_sandbox_name, "terminating")
            try:
                await sandbox.delete()
                cleaned_up = True
                await self._safe_update_state(
                    target_sandbox_name,
                    final_ledger_state if final_ledger_state == "completed" else "deleted",
                    metadata_patch={"success": success, "error": error_message},
                )
            except Exception as cleanup_err:
                logger.error("Teardown failed for sandbox '%s': %s", target_sandbox_name, cleanup_err, exc_info=True)
                await self._safe_update_state(
                    target_sandbox_name,
                    "failed",
                    metadata_patch={"cleanup_error": str(cleanup_err)},
                )
                raise CleanupFailedError(
                    f"Teardown failed for sandbox '{target_sandbox_name}': {cleanup_err}"
                ) from cleanup_err

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        return ExecutionSummary(
            sandbox_name=target_sandbox_name,
            task_id=task_id,
            success=success,
            results=results,
            error_message=error_message,
            cleaned_up=cleaned_up,
            duration_seconds=duration,
        )
