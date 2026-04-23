#!/usr/bin/env python3
"""Validate a Qdrant skill by running lint checks and printing a summary.

Wraps the project-level lint-skills.py with additional reporting:
- R-16 check reminder (prints the question for manual evaluation)
- Word count summary
- Description length summary
- Reference file listing

Usage:
    python scripts/validate.py [skill-folder-name]

If no skill name is given, validates the skill that contains this script
(detected from the script's own path).
"""

import json
import re
import sys
from pathlib import Path


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Parse YAML frontmatter from SKILL.md content."""
    if not content.startswith("---"):
        return None, content

    end = content.find("---", 3)
    if end == -1:
        return None, content

    frontmatter_text = content[3:end].strip()
    body = content[end + 3:].strip()

    fm = {}
    current_key = None
    current_value = []

    for line in frontmatter_text.split("\n"):
        match = re.match(r"^(\w[\w-]*)\s*:\s*(.*)", line)
        if match:
            if current_key:
                fm[current_key] = "\n".join(current_value).strip()
            current_key = match.group(1)
            current_value = [match.group(2)]
        elif current_key and line.startswith("  "):
            current_value.append(line.strip())

    if current_key:
        fm[current_key] = "\n".join(current_value).strip()

    return fm, body


def count_words(text: str) -> int:
    return len(text.split())


def find_skill_dir(skill_name: str | None) -> Path:
    """Find the skill directory to validate."""
    # If a name is given, look it up in skills/
    if skill_name:
        skills_root = Path(__file__).resolve().parent.parent.parent
        candidate = skills_root / skill_name
        if candidate.is_dir():
            return candidate
        # Also try under skills/
        candidate = skills_root / "skills" / skill_name
        if candidate.is_dir():
            return candidate
        print(f"error: skill directory not found: {skill_name}")
        sys.exit(1)

    # Default: the skill that contains this script
    return Path(__file__).resolve().parent.parent


def run_lint(skill_dir: Path) -> list[str]:
    """Run the project-level linter on a single skill directory."""
    # Import lint logic inline to avoid path gymnastics
    lint_script = skill_dir.parent.parent / "scripts" / "lint-skills.py"
    if not lint_script.exists():
        # Try relative to this script
        lint_script = Path(__file__).resolve().parent.parent.parent / "scripts" / "lint-skills.py"

    if not lint_script.exists():
        return ["could not find scripts/lint-skills.py"]

    # Re-implement the core lint checks here (avoid exec/import complexity)
    errors = []
    skill_name = skill_dir.name

    # R-23: kebab-case
    if not re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", skill_name):
        errors.append(f"R-23: folder name '{skill_name}' is not kebab-case")

    # R-22: SKILL.md exists
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append("R-22: SKILL.md file not found")
        return errors

    content = skill_md.read_text()
    if not content.startswith("---"):
        errors.append("R-25: missing YAML frontmatter")
        return errors

    fm, body = parse_frontmatter(content)
    if fm is None:
        errors.append("R-25: could not parse YAML frontmatter")
        return errors

    name = fm.get("name", "")
    if not name:
        errors.append("R-26: missing 'name' field")
    elif name != skill_name:
        errors.append(f"R-26: name '{name}' does not match folder '{skill_name}'")

    desc = fm.get("description", "")
    if not desc:
        errors.append("R-26: missing 'description' field")
    else:
        if len(desc) > 1024:
            errors.append(f"R-91: description is {len(desc)} chars (max 1024)")
        if "<" in desc or ">" in desc:
            errors.append("R-31: description contains angle brackets")
        has_when = any(kw in desc.lower() for kw in ["use when", "trigger", "use for"])
        has_not = "do not" in desc.lower() or "don't" in desc.lower()
        if not has_when:
            errors.append("R-28: description missing trigger phrases")
        if not has_not:
            errors.append("R-51: description missing negative triggers")

    word_count = count_words(body)
    if word_count > 5000:
        errors.append(f"R-77: body is {word_count} words (max 5,000)")

    if "## troubleshooting" not in body.lower() and "## common issues" not in body.lower() and "## common patterns" not in body.lower():
        errors.append("R-35: missing Troubleshooting section")

    if (skill_dir / "README.md").exists():
        errors.append("R-24: README.md found inside skill folder")

    triggers_file = skill_dir / "triggers.json"
    if not triggers_file.exists():
        errors.append("R-44: triggers.json not found")
    else:
        try:
            triggers = json.loads(triggers_file.read_text())
            pos = triggers.get("should_trigger", [])
            neg = triggers.get("should_not_trigger", [])
            if len(pos) < 4:
                errors.append(f"R-44: {len(pos)} positive triggers (min 4)")
            if len(neg) < 4:
                errors.append(f"R-44: {len(neg)} negative triggers (min 4)")
        except json.JSONDecodeError as e:
            errors.append(f"R-44: invalid triggers.json: {e}")

    return errors


def print_summary(skill_dir: Path) -> None:
    """Print extended validation summary."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return

    content = skill_md.read_text()
    fm, body = parse_frontmatter(content)

    print(f"\n{'=' * 60}")
    print(f"  Skill Summary: {skill_dir.name}")
    print(f"{'=' * 60}")

    # Word count
    word_count = count_words(body)
    print(f"  body word count:    {word_count} / 5,000")

    # Description length
    desc = fm.get("description", "") if fm else ""
    print(f"  description length: {len(desc)} / 1,024 chars")

    # Reference files
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        ref_files = sorted(f.name for f in refs_dir.iterdir() if f.is_file())
        print(f"  reference files:    {len(ref_files)}")
        for rf in ref_files:
            rf_path = refs_dir / rf
            rf_words = count_words(rf_path.read_text()) if rf_path.suffix == ".md" else 0
            suffix = f" ({rf_words} words)" if rf_words else ""
            print(f"    - {rf}{suffix}")
    else:
        print("  reference files:    0 (no references/ directory)")

    # Agents
    agents_dir = skill_dir / "agents"
    if agents_dir.is_dir():
        agent_files = sorted(f.name for f in agents_dir.iterdir() if f.is_file())
        print(f"  agent files:        {len(agent_files)}")
        for af in agent_files:
            print(f"    - {af}")

    # Triggers count
    triggers_file = skill_dir / "triggers.json"
    if triggers_file.exists():
        try:
            triggers = json.loads(triggers_file.read_text())
            pos = len(triggers.get("should_trigger", []))
            neg = len(triggers.get("should_not_trigger", []))
            print(f"  triggers:           {pos} positive, {neg} negative")
        except json.JSONDecodeError:
            print("  triggers:           (invalid JSON)")


def print_r16_reminder(skill_dir: Path) -> None:
    """Print the R-16 check as a reminder for manual evaluation."""
    print(f"\n{'=' * 60}")
    print("  R-16 Manual Check")
    print(f"{'=' * 60}")
    print("  Answer this question before proceeding:")
    print()
    print("  \"What domain knowledge does this skill embed that")
    print("   Claude does not already know?\"")
    print()
    print("  If the answer is 'nothing', this skill should not exist.")
    print("  Good answers reference SA experience, internal data,")
    print("  customer patterns, or corrections to Claude's mistakes.")
    print(f"{'=' * 60}")


def main():
    skill_name = sys.argv[1] if len(sys.argv) > 1 else None
    skill_dir = find_skill_dir(skill_name)

    print(f"\nValidating: {skill_dir.name}")
    print(f"Path: {skill_dir}")

    # Run lint checks
    errors = run_lint(skill_dir)

    print(f"\n{'=' * 60}")
    print(f"  Lint Results: {'PASS' if not errors else 'FAIL'}")
    print(f"{'=' * 60}")

    if errors:
        for err in errors:
            print(f"  {err}")
    else:
        print("  all checks passed")

    # Print summary
    print_summary(skill_dir)

    # Print R-16 reminder
    print_r16_reminder(skill_dir)

    print()
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
