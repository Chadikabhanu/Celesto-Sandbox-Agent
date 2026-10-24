from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any

AUDIT_LOG_FILE = Path("logs/commands.jsonl")
_audit_lock = threading.Lock()


def get_audit_log_path() -> Path:
    """Return the resolved audit log file path, ensuring parent dir exists."""
    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    return AUDIT_LOG_FILE


def record_command_audit(
    sandbox_name: str,
    command: str,
    decision: str,  # "allowed" or "blocked"
    execution_target: str = "celesto_sandbox",
    extra: dict[str, Any] | None = None,
    log_file: Path | None = None,
) -> dict[str, Any]:
    """Append a command execution attempt to the command audit log.

    Guarantees requirement 9: Each record contains:
    - ts: ISO8601 timestamp string
    - sandbox_name: name of the targeted sandbox
    - command: full command string attempted
    - decision: 'allowed' or 'blocked'
    - execution_target: 'celesto_sandbox'
    """
    ts = datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "ts": ts,
        "sandbox_name": sandbox_name,
        "command": command,
        "decision": decision,
        "execution_target": execution_target,
    }
    if extra:
        record["details"] = extra

    target_path = log_file or get_audit_log_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(record, separators=(",", ":")) + "\n"
    with _audit_lock:
        with open(target_path, "a", encoding="utf-8") as f:
            f.write(line)

    return record


def read_command_audit_records(log_file: Path | None = None) -> list[dict[str, Any]]:
    """Read all records from the audit log."""
    path = log_file or AUDIT_LOG_FILE
    if not path.exists():
        return []

    records = []
    with _audit_lock:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        records.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        pass
    return records
