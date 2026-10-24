import re
import secrets

SANDBOX_NAME_PATTERN = r"^sbx-[a-z0-9]{8,}$"
SANDBOX_NAME_REGEX = re.compile(SANDBOX_NAME_PATTERN)


def generate_sandbox_name(prefix: str = "sbx") -> str:
    """Generate a unique sandbox name matching ^sbx-[a-z0-9]{8,}$.

    Generates 12 cryptographically random lowercase hexadecimal characters,
    guaranteeing uniqueness and conformity to the required pattern.
    """
    token = secrets.token_hex(6)  # 12 hex chars: [a-f0-9]
    return f"{prefix}-{token}"


def is_valid_sandbox_name(name: str) -> bool:
    """Check if sandbox name matches the required regex pattern."""
    if not isinstance(name, str):
        return False
    return bool(SANDBOX_NAME_REGEX.match(name))
