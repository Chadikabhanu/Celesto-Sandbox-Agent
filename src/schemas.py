from datetime import datetime
import re
from typing import Any
from pydantic import BaseModel, Field, field_validator

SANDBOX_NAME_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")

VALID_EXECUTION_TARGETS = {
    "celesto_sandbox",
    "celesto_cloud",
    "celesto_local",
}

VALID_STATES = {
    "created",
    "pending",
    "provisioning",
    "ready",
    "running",
    "checkpointing",
    "failed_transient",
    "recovering",
    "succeeded",
    "completed",
    "failed",
    "terminating",
    "deleted",
}


class RunCreate(BaseModel):
    sandbox_name: str
    state: str = "pending"
    execution_target: str = "celesto_sandbox"
    task_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sandbox_name")
    @classmethod
    def validate_sandbox_name(cls, v: str) -> str:
        if not isinstance(v, str) or not SANDBOX_NAME_REGEX.match(v):
            raise ValueError(
                f"Invalid sandbox_name '{v}'. Sandbox name must match pattern ^sbx-[a-z0-9]{{8,}}$."
            )
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if not isinstance(v, str) or v.lower() not in VALID_STATES:
            raise ValueError(
                f"Invalid state '{v}'. State must be one of: {sorted(VALID_STATES)}."
            )
        return v.lower()

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, v: str) -> str:
        if not isinstance(v, str) or v.lower() not in VALID_EXECUTION_TARGETS:
            raise ValueError(
                f"Invalid execution_target '{v}'. Execution target must be one of: {sorted(VALID_EXECUTION_TARGETS)}."
            )
        return v.lower()


class RunResponse(BaseModel):
    id: int
    sandbox_name: str
    state: str
    execution_target: str
    task_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"
