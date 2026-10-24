"""Sandbox package providing adapters, policies, and audit logging."""

from src.sandbox.audit import record_command_audit, read_command_audit_records
from src.sandbox.exceptions import (
    CleanupFailedError,
    CommandBlockedError,
    GuestTimeoutError,
    HostEscapeAttemptError,
    ProviderConfigurationError,
    SandboxError,
)
from src.sandbox.factory import get_sandbox_provider
from src.sandbox.fake_adapter import FakeCelestoProvider, FakeSandbox
from src.sandbox.interface import CommandResult, Sandbox, SandboxProvider
from src.sandbox.naming import generate_sandbox_name, is_valid_sandbox_name
from src.sandbox.policy import CommandPolicy, PolicyDecision, default_policy

__all__ = [
    "Sandbox",
    "SandboxProvider",
    "CommandResult",
    "FakeSandbox",
    "FakeCelestoProvider",
    "get_sandbox_provider",
    "generate_sandbox_name",
    "is_valid_sandbox_name",
    "CommandPolicy",
    "PolicyDecision",
    "default_policy",
    "record_command_audit",
    "read_command_audit_records",
    "SandboxError",
    "CommandBlockedError",
    "GuestTimeoutError",
    "CleanupFailedError",
    "ProviderConfigurationError",
    "HostEscapeAttemptError",
]
