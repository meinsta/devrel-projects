"""CLI commands for Cortex.

Provides:
- start-mcp-server: Run MCP server (Serena-style entrypoint)
- init: Initialize a project
- index: Index a project for code search
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path


def main():
    """Main CLI entrypoint with subcommands."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Cortex - Long-term memory for coding agents",
        prog="cortex",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # start-mcp-server (Serena-style)
    server_parser = subparsers.add_parser(
        "start-mcp-server",
        help="Start MCP server (use with claude mcp add)",
    )
    server_parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Project directory to target (sets working directory and repo_id)",
    )
    server_parser.add_argument(
        "--context",
        type=str,
        choices=["claude-code", "cursor", "generic"],
        default="claude-code",
        help="Client context (adjusts tool availability)",
    )
    server_parser.add_argument(
        "--auto-bootstrap",
        action="store_true",
        help="Automatically bootstrap (LSP + index) on startup",
    )

    # init command (Initializer)
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a project for code intelligence",
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project directory to initialize (default: current directory)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    init_parser.add_argument(
        "--no-claude-md",
        action="store_true",
        help="Skip creating CLAUDE.md",
    )
    init_parser.add_argument(
        "--no-mcp-json",
        action="store_true",
        help="Skip creating .mcp.json",
    )

    # index command
    index_parser = subparsers.add_parser(
        "index",
        help="Index a project for code search",
    )
    index_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project directory to index (default: current directory)",
    )
    index_parser.add_argument(
        "--repo-id",
        help="Repository identifier (auto-detected from git if not provided)",
    )
    index_parser.add_argument(
        "--url",
        default=os.environ.get("QDRANT_URL"),
        help="Qdrant URL (or set QDRANT_URL env var)",
    )
    index_parser.add_argument(
        "--api-key",
        default=os.environ.get("QDRANT_API_KEY"),
        help="Qdrant API key (or set QDRANT_API_KEY env var)",
    )
    index_parser.add_argument(
        "--collection",
        default=os.environ.get("CODE_COLLECTION", "code_index"),
        help="Collection name (default: code_index)",
    )
    index_parser.add_argument(
        "--max-file-size",
        type=int,
        default=100_000,
        help="Skip files larger than this (default: 100KB)",
    )

    args = parser.parse_args()

    if args.command == "start-mcp-server":
        start_mcp_server(args)
    elif args.command == "init":
        init_project(args)
    elif args.command == "index":
        index_command(args)
    else:
        parser.print_help()
        sys.exit(1)


def init_project(args):
    """Initialize a project for code intelligence."""
    from .initializer import init_command

    result = init_command(
        project_path=args.path,
        force=args.force,
        no_claude_md=args.no_claude_md,
        no_mcp_json=args.no_mcp_json,
    )

    print(f"Initialized: {Path(args.path).resolve()}")
    print(f"Language: {result['info']['language']}")
    print()

    if result["files_created"]:
        print("Created:")
        for f in result["files_created"]:
            print(f"  + {f}")

    if result["files_skipped"]:
        print("Skipped:")
        for f in result["files_skipped"]:
            print(f"  - {f}")

    print()
    print("Next steps:")
    print("  1. Set QDRANT_URL (and QDRANT_API_KEY if using Qdrant Cloud)")
    print("  2. Run: claude mcp add cortex -- uvx cortex-mcp start-mcp-server --project .")
    print("  3. In Claude Code: bootstrap()")


def start_mcp_server(args):
    """Start the MCP server (Serena-style entrypoint).

    This is designed to be called via:
    claude mcp add cortex -- uvx cortex-mcp start-mcp-server --project "$(pwd)"
    """
    # Set project directory
    if args.project:
        project_path = Path(args.project).resolve()
        if not project_path.is_dir():
            print(f"Error: Not a directory: {project_path}", file=sys.stderr)
            sys.exit(1)

        # Change to project directory so all relative paths work
        os.chdir(project_path)

        # Set environment variable for server to use
        os.environ["QDRANT_PROJECT_PATH"] = str(project_path)

        # Auto-detect and set repo_id
        repo_id = _detect_repo_id(project_path)
        os.environ["QDRANT_REPO_ID"] = repo_id

    # Set context for tool filtering
    os.environ["MCP_CONTEXT"] = args.context

    # Set auto-bootstrap flag
    if args.auto_bootstrap:
        os.environ["AUTO_BOOTSTRAP"] = "true"

    # Import and run server
    from .server import main as server_main
    server_main()


def index_command(args):
    """Index a project for code search."""
    from .code_store import QdrantCodeStore
    from .indexer import CodeIndexer

    if not args.url:
        print("Error: QDRANT_URL not set. Use --url or set QDRANT_URL env var.", file=sys.stderr)
        sys.exit(1)

    project_path = Path(args.path).resolve()
    if not project_path.is_dir():
        print(f"Error: Not a directory: {project_path}", file=sys.stderr)
        sys.exit(1)

    # Auto-detect repo_id
    repo_id = args.repo_id
    if not repo_id:
        repo_id = _detect_repo_id(project_path)

    print(f"Indexing: {project_path}")
    print(f"Repo ID: {repo_id}")
    print(f"Qdrant: {args.url}")
    print(f"Collection: {args.collection}")
    print()

    # Create store and indexer
    store = QdrantCodeStore(
        url=args.url,
        api_key=args.api_key,
        collection=args.collection,
    )
    indexer = CodeIndexer(store=store)

    # Progress callback
    def progress(file_path: str, current: int, total: int):
        pct = (current / total) * 100 if total > 0 else 0
        print(f"\r[{pct:5.1f}%] {current}/{total} files - {Path(file_path).name[:40]:<40}", end="", flush=True)

    # Run indexing
    stats = indexer.index_project(
        str(project_path),
        repo_id,
        progress_callback=progress,
        max_file_size=args.max_file_size,
    )

    print()  # New line after progress
    print()
    print("=" * 50)
    print("Indexing Complete")
    print("=" * 50)
    print(f"Files indexed: {stats['files_indexed']}")
    print(f"Chunks indexed: {stats['chunks_indexed']}")
    print(f"Files skipped: {stats['files_skipped']}")

    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats["errors"][:10]:
            print(f"  - {err}")
        if len(stats["errors"]) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")


def _detect_repo_id(project_path: Path) -> str:
    """Detect repo_id from git or folder name."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            remote_url = result.stdout.strip()
            url_hash = hashlib.sha256(remote_url.encode()).hexdigest()[:12]
            repo_name = remote_url.rstrip("/").split("/")[-1].replace(".git", "")
            return f"{repo_name}-{url_hash}"
    except Exception:
        pass

    return project_path.name


if __name__ == "__main__":
    main()
