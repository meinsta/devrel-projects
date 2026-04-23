"""Policy module for validating memory content before storage."""

import re

# Maximum memory size in characters (8KB should be plenty for useful memories)
MAX_MEMORY_SIZE = 8192

_SECRET_PATTERNS = [
    # Private keys
    r"-----BEGIN (RSA|EC|OPENSSH|PGP|DSA|PRIVATE) PRIVATE KEY-----",
    r"-----BEGIN ENCRYPTED PRIVATE KEY-----",
    r"-----BEGIN CERTIFICATE-----",
    # AWS credentials
    r"AKIA[0-9A-Z]{16}",  # AWS access key ID
    r"(?i)aws[_-]?secret[_-]?access[_-]?key",
    # Generic secrets/tokens
    r"(?i)\b(api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|bearer[_-]?token|password|passwd|pwd)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    # GitHub tokens
    r"gh[pousr]_[A-Za-z0-9_]{36,}",
    r"github_pat_[A-Za-z0-9_]{22,}",
    # Anthropic API keys
    r"sk-ant-[A-Za-z0-9-_]{32,}",
    # OpenAI API keys
    r"sk-[A-Za-z0-9]{32,}",
    # Slack tokens
    r"xox[baprs]-[0-9]{10,}-[A-Za-z0-9-]+",
    # Database connection strings with passwords
    r"(?i)(mongodb|postgres|mysql|redis)://[^:]+:[^@]+@",
    # JWT tokens (3 base64 parts separated by dots)
    r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    # Google API keys
    r"AIza[0-9A-Za-z_-]{35}",
    # Stripe keys
    r"sk_live_[0-9a-zA-Z]{24,}",
    r"pk_live_[0-9a-zA-Z]{24,}",
    # Azure connection strings
    r"(?i)DefaultEndpointsProtocol=https;AccountName=",
]

# Patterns that indicate config file dumps (not useful as memories)
_CONFIG_DUMP_PATTERNS = [
    # Env file content (multiple KEY=value lines)
    r"(?m)^[A-Z_]{3,}=.+\n[A-Z_]{3,}=.+\n[A-Z_]{3,}=",
    # npmrc content
    r"(?i)//registry\.npmjs\.org/:_authToken",
    r"(?i)_auth\s*=\s*[A-Za-z0-9+/=]{20,}",
    # AWS config blocks
    r"(?i)\[default\]\s*\n\s*aws_access_key_id",
    r"(?i)\[profile\s+\w+\]",
    # Docker config
    r'"auths"\s*:\s*\{[^}]*"auth"\s*:',
    # SSH config blocks
    r"(?m)^Host\s+\S+\s*\n\s*(HostName|User|IdentityFile)",
    # gitconfig with credentials
    r"(?i)\[credential\]",
    # kubeconfig
    r"(?i)apiVersion:\s*v1\s*\nkind:\s*Config",
]

_COMPILED_PATTERNS = [re.compile(p) for p in _SECRET_PATTERNS]
_COMPILED_CONFIG_PATTERNS = [re.compile(p) for p in _CONFIG_DUMP_PATTERNS]


def validate_memory_text(text: str) -> None:
    """
    Validate memory text before storage.

    Raises:
        ValueError: If the text contains potential secrets, is too short,
                    too large, or looks like a config dump.
    """
    # Check maximum size first (fast rejection)
    if len(text) > MAX_MEMORY_SIZE:
        raise ValueError(
            f"Memory text too large ({len(text)} chars). "
            f"Maximum size is {MAX_MEMORY_SIZE} characters. "
            "Store a concise summary instead."
        )

    # Check for secrets
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                "Refusing to store potential secret. "
                "Memory text appears to contain sensitive credentials."
            )

    # Check for config file dumps
    for pattern in _COMPILED_CONFIG_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                "Refusing to store config dump. "
                "Memory should contain insights, not raw configuration files."
            )

    # Check minimum length
    stripped = text.strip()
    if len(stripped) < 20:
        raise ValueError(
            "Memory text too short to be useful. "
            "Please provide at least 20 characters of meaningful content."
        )

    # Check for excessive whitespace/empty content
    words = stripped.split()
    if len(words) < 3:
        raise ValueError(
            "Memory text should contain at least 3 words "
            "to be semantically meaningful for retrieval."
        )
