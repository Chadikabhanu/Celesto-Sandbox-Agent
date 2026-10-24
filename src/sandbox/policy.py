from dataclasses import dataclass
import re
from src.sandbox.exceptions import CommandBlockedError


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None


class CommandPolicy:
    """Deterministic security command policy enforced in code.

    A system prompt telling the agent to be safe is not a security boundary.
    This policy engine inspects raw commands prior to guest dispatch and blocks
    prohibited or destructive operations.
    """

    # Prohibited regex patterns (destructive, host escape, tampering)
    PROHIBITED_PATTERNS: tuple[re.Pattern, ...] = (
        # Root filesystem destruction
        re.compile(r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+(/|/\*|/bin|/usr|/etc|/boot)\b"),
        re.compile(r"\brm\s+--no-preserve-root\b"),
        # Block device & filesystem corruption
        re.compile(r"\bmkfs(\.[a-zA-Z0-9]+)?\b"),
        re.compile(r"\bdd\s+if=/dev/(zero|urandom|random)\s+of=/dev/([a-z0-9]+)\b"),
        re.compile(r"\b(fdisk|parted|sfdisk|cfdisk)\b"),
        # Fork bombs and process starvation
        re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"),
        re.compile(r"\bwhile\s+true;\s*do\s+.*&\s*done\b"),
        # System shutdown / reboot inside sandbox
        re.compile(r"\b(shutdown|reboot|poweroff|init\s+0|halt|telinit\s+0)\b"),
        # Direct raw memory/kernel device tampering
        re.compile(r"/dev/(mem|kmem|port)"),
        # Host socket access / container breakout
        re.compile(r"/var/run/docker\.sock"),
        re.compile(r"/run/containerd/containerd\.sock"),
        # Audit log tampering
        re.compile(r"\bcommands\.jsonl\b"),
        # Canary disclosure and unauthorized egress exfiltration
        re.compile(r"\b(curl|wget|nc|ncat|netcat|socat|telnet)\b.*(evil|exfil|malicious|attacker|canary=)", re.IGNORECASE),
        re.compile(r"\bCANARY_TOKEN_SAFE_TEST_\w+\b"),
        # Host fixture tampering
        re.compile(r"\bhost_fixture\.txt\b"),
    )

    # Literal prohibited commands or tokens
    EXACT_DENY_SUBSTRINGS: tuple[str, ...] = (
        ":(){ :|:& };:",
        "rm -rf /",
        "rm -rf /*",
        "mkfs.ext4",
        "mkfs",
        "dd if=/dev/zero of=/dev/sda",
    )

    def evaluate(self, command: str) -> PolicyDecision:
        """Evaluate a shell command against the security policy."""
        if not command or not command.strip():
            return PolicyDecision(allowed=False, reason="Empty or whitespace-only command")

        stripped = command.strip()

        # Check exact substring matches
        for bad in self.EXACT_DENY_SUBSTRINGS:
            if bad in stripped:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Prohibited destructive command pattern detected: '{bad}'",
                )

        # Check regex rules
        for pattern in self.PROHIBITED_PATTERNS:
            if pattern.search(stripped):
                return PolicyDecision(
                    allowed=False,
                    reason=f"Command matches prohibited security rule pattern: {pattern.pattern}",
                )

        return PolicyDecision(allowed=True, reason=None)

    def enforce(self, command: str, sandbox_name: str | None = None) -> None:
        """Evaluate command and raise CommandBlockedError if blocked."""
        decision = self.evaluate(command)
        if not decision.allowed:
            raise CommandBlockedError(
                message=decision.reason or "Command blocked by security policy",
                command=command,
                sandbox_name=sandbox_name,
            )


default_policy = CommandPolicy()
