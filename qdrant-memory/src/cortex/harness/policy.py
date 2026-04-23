"""Policy - Safety and access control.

Enforces:
- Read-only mode
- Path allowlist/denylist
- Secret detection (API keys, tokens, private keys)
- Payload size limits
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional


class PolicyViolation(Exception):
    """Raised when a policy is violated."""
    pass


# ============================================================================
# Secret Detection Patterns
# ============================================================================

SECRET_PATTERNS = [
    # API keys
    (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[\w-]{20,}", "API key detected"),
    (r"(?i)(secret[_-]?key|secretkey)\s*[=:]\s*['\"]?[\w-]{20,}", "Secret key detected"),

    # AWS
    (r"AKIA[0-9A-Z]{16}", "AWS access key detected"),
    (r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*['\"]?[\w/+=]{40}", "AWS secret key detected"),

    # GitHub/GitLab tokens
    (r"gh[pous]_[A-Za-z0-9_]{36,}", "GitHub token detected"),
    (r"glpat-[\w-]{20,}", "GitLab token detected"),

    # Private keys
    (r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----", "Private key detected"),

    # Database connection strings
    (r"(?i)(postgres|mysql|mongodb)://\S+:\S+@", "Database credentials detected"),

    # Bearer tokens
    (r"(?i)bearer\s+[a-zA-Z0-9._-]{20,}", "Bearer token detected"),

    # Password patterns
    (r"(?i)password\s*[=:]\s*['\"][^'\"]{8,}['\"]", "Password detected"),

    # Anthropic/OpenAI keys
    (r"sk-ant-[a-zA-Z0-9-]{40,}", "Anthropic API key detected"),
    (r"sk-[a-zA-Z0-9]{48}", "OpenAI API key detected"),
]

# Config dump indicators
CONFIG_DUMP_PATTERNS = [
    (r"(?m)^[A-Z_]{3,}=.{20,}$[\s\S]*^[A-Z_]{3,}=", "Config dump detected (multiple env vars)"),
    (r"(?i)kubeconfig:", "Kubernetes config detected"),
    (r'(?i)"credentials":\s*\{', "Credentials object detected"),
]


def detect_secrets(text: str) -> list[str]:
    """Detect secrets in text.

    Args:
        text: Text to scan

    Returns:
        List of detected secret descriptions
    """
    detected = []

    for pattern, description in SECRET_PATTERNS:
        if re.search(pattern, text):
            detected.append(description)

    for pattern, description in CONFIG_DUMP_PATTERNS:
        if re.search(pattern, text):
            detected.append(description)

    return detected


def enforce_remember_policy(text: str, kind: str, policy: Dict[str, Any]) -> None:
    """
    Enforce policy rules for remember operation.

    Raises PolicyViolation if:
    - Secret detected (API keys, tokens, private keys)
    - Config dump detected (.env, kubeconfig, etc.)
    - Payload > max_payload_bytes
    - Invalid kind

    Args:
        text: Memory text to validate
        kind: Memory kind (episode, fact, recipe)
        policy: Policy dict from cortex.toml
    """
    from ..skills.store.schema import VALID_KINDS

    # Validate kind
    if kind not in VALID_KINDS:
        raise PolicyViolation(f"Invalid kind '{kind}'. Must be one of: {', '.join(VALID_KINDS)}")

    security = policy.get("security", {})

    # Check payload size
    max_bytes = security.get("max_payload_bytes", 8192)
    if len(text.encode("utf-8")) > max_bytes:
        raise PolicyViolation(
            f"Memory text exceeds maximum size ({max_bytes} bytes). "
            "Consider splitting into multiple memories."
        )

    # Check for secrets
    if security.get("block_secrets", True):
        secrets = detect_secrets(text)
        if secrets:
            raise PolicyViolation(
                f"Blocked: {secrets[0]}. "
                "Memories should not contain secrets, credentials, or sensitive config. "
                "Set security.block_secrets=false in cortex.toml to override."
            )


class Policy:
    """
    Policy enforcement for the harness.

    Configured via environment variables:
    - READ_ONLY_MODE: Block all writes
    - PATH_ALLOWLIST: Only allow these paths
    - PATH_DENYLIST: Block these paths
    """

    def __init__(self):
        pass

    def is_read_only(self) -> bool:
        """Check if server is in read-only mode."""
        return os.environ.get("READ_ONLY_MODE", "").lower() in ("1", "true", "yes")

    def get_path_allowlist(self) -> list[str]:
        """Get allowed paths (empty = allow all)."""
        paths = os.environ.get("PATH_ALLOWLIST", "")
        return [p.strip() for p in paths.split(",") if p.strip()]

    def get_path_denylist(self) -> list[str]:
        """Get denied paths."""
        paths = os.environ.get("PATH_DENYLIST", "")
        return [p.strip() for p in paths.split(",") if p.strip()]

    def check_write_allowed(self) -> None:
        """Raise error if writes are not allowed."""
        if self.is_read_only():
            raise PolicyViolation(
                "Operation blocked: READ_ONLY_MODE is enabled. "
                "Set READ_ONLY_MODE=false to allow writes."
            )

    def check_path_allowed(self, path: str) -> None:
        """Raise error if path is not allowed."""
        resolved = str(Path(path).resolve())

        # Check denylist first
        for denied in self.get_path_denylist():
            denied_resolved = str(Path(denied).resolve())
            if resolved.startswith(denied_resolved):
                raise PolicyViolation(f"Path denied by PATH_DENYLIST: {path}")

        # Check allowlist (if set)
        allowlist = self.get_path_allowlist()
        if allowlist:
            allowed = False
            for allowed_path in allowlist:
                allowed_resolved = str(Path(allowed_path).resolve())
                if resolved.startswith(allowed_resolved):
                    allowed = True
                    break
            if not allowed:
                raise PolicyViolation(f"Path not in PATH_ALLOWLIST: {path}")

    def check_memory_text(self, text: str) -> None:
        """
        Validate memory text against policy.

        Delegates to policy.py for secret detection.
        """
        from ..policy import validate_memory_text
        validate_memory_text(text)
