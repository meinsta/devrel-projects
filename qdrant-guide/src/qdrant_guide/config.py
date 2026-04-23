"""Configuration and constants for qdrant-guide."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Qdrant documentation sources
LLMS_TXT_URL = "https://qdrant.tech/llms.txt"
QDRANT_DOCS_BASE = "https://qdrant.tech/documentation/"
PYTHON_CLIENT_DOCS = "https://python-client.qdrant.tech/"
RUST_CLIENT_DOCS = "https://docs.rs/qdrant-client"

# Allowed URL prefixes for the fetch tool
ALLOWED_DOC_PREFIXES = (
    "https://qdrant.tech/",
    "https://python-client.qdrant.tech/",
    "https://docs.rs/qdrant-client",
    "https://pkg.go.dev/github.com/qdrant/",
    "https://qdrant.github.io/java-client",
    "https://github.com/qdrant/qdrant-js",
    "https://github.com/qdrant/qdrant-dotnet",
)

# Map URL patterns to language labels for payload filtering
LANGUAGE_URL_MAP = (
    ("python-client.qdrant.tech", "python"),
    ("docs.rs/qdrant-client", "rust"),
    ("pkg.go.dev/github.com/qdrant", "go"),
    ("qdrant.github.io/java-client", "java"),
    ("github.com/qdrant/qdrant-js", "typescript"),
    ("github.com/qdrant/qdrant-dotnet", "dotnet"),
)


def detect_language(url: str) -> str:
    """Return the client language for a URL, or 'general' for core docs."""
    for pattern, lang in LANGUAGE_URL_MAP:
        if pattern in url:
            return lang
    return "general"

# Local skill files from qdrant/skills repo
SKILLS_DIR = Path(os.getenv("QDRANT_SKILLS_DIR", Path.home() / "qdrant-skills"))
PYTHON_SKILL_PATH = SKILLS_DIR / "skills" / "qdrant-python" / "SKILL.md"
RUST_SKILL_PATH = SKILLS_DIR / "skills" / "qdrant-rust" / "SKILL.md"

# Skill and command file map
SKILL_FILE_MAP: dict[str, Path] = {
    "qdrant-python": SKILLS_DIR / "skills" / "qdrant-python" / "SKILL.md",
    "qdrant-rust": SKILLS_DIR / "skills" / "qdrant-rust" / "SKILL.md",
    "connect": SKILLS_DIR / "commands" / "connect.md",
    "setup-collection": SKILLS_DIR / "commands" / "setup-collection.md",
    "hybrid-search": SKILLS_DIR / "commands" / "hybrid-search.md",
    "add-multitenancy": SKILLS_DIR / "commands" / "add-multitenancy.md",
    "migrate-search": SKILLS_DIR / "commands" / "migrate-search.md",
}

# Cache settings
DOC_CACHE_TTL_SECONDS = 1800  # 30 minutes
DOC_MAX_CHARS = 50_000  # truncate fetched pages beyond this

# Local edge shard for offline search
SHARD_DIR = Path(os.getenv("QDRANT_GUIDE_SHARD_DIR", Path.home() / ".qdrant-guide" / "shard"))
BUNDLED_SHARD_ARCHIVE = Path(__file__).parent / "data" / "shard.tar.gz"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHUNK_MAX_CHARS = 1500
