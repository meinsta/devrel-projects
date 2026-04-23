#!/usr/bin/env python3
"""Lint all skills in the qdrant-os skills/ directory.

Validates rules from the skill-building guide:
- R-06: Required folder contents (SKILL.md exists)
- R-22: SKILL.md naming is exact
- R-23: Skill folder naming (kebab-case)
- R-25/R-26: YAML frontmatter with name and description
- R-28: Description includes trigger phrases
- R-31: No XML angle brackets in frontmatter
- R-35: Troubleshooting section present
- R-40: Body contains when/why, not how
- R-44: triggers.json with 4+ positive and 4+ negative
- R-77: SKILL.md under 5,000 words
- R-91: Description under 1024 characters
"""

import json
import os
import re
import sys
from pathlib import Path


def count_words(text: str) -> int:
    return len(text.split())


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Parse YAML frontmatter from SKILL.md content."""
    if not content.startswith("---"):
        return None, content

    end = content.find("---", 3)
    if end == -1:
        return None, content

    frontmatter_text = content[3:end].strip()
    body = content[end + 3:].strip()

    # Simple YAML parsing (name and description only)
    fm = {}
    current_key = None
    current_value = []

    for line in frontmatter_text.split("\n"):
        # Check for top-level key
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


def lint_skill(skill_dir: Path) -> list[str]:
    """Lint a single skill directory. Returns list of error messages."""
    errors = []
    skill_name = skill_dir.name

    # R-23: kebab-case folder name
    if not re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", skill_name):
        errors.append(f"R-23: folder name '{skill_name}' is not kebab-case")

    # R-22: SKILL.md must exist with exact case
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append("R-22: SKILL.md file not found (case-sensitive)")
        return errors

    content = skill_md.read_text()

    # R-25: YAML frontmatter
    if not content.startswith("---"):
        errors.append("R-25: missing YAML frontmatter (no --- delimiter)")
        return errors

    fm, body = parse_frontmatter(content)
    if fm is None:
        errors.append("R-25: could not parse YAML frontmatter")
        return errors

    # R-26: name field
    name = fm.get("name", "")
    if not name:
        errors.append("R-26: missing 'name' field in frontmatter")
    elif name != skill_name:
        errors.append(f"R-26: name '{name}' does not match folder '{skill_name}'")

    # R-26: description field
    desc = fm.get("description", "")
    if not desc:
        errors.append("R-26: missing 'description' field in frontmatter")
    else:
        # R-91: description under 1024 chars
        if len(desc) > 1024:
            errors.append(f"R-91: description is {len(desc)} chars (max 1024)")

        # R-31: no XML angle brackets
        if "<" in desc or ">" in desc:
            errors.append("R-31: description contains XML angle brackets (< or >)")

        # R-28: description should include trigger phrases
        has_when = any(kw in desc.lower() for kw in ["use when", "trigger", "use for"])
        has_not = "do not" in desc.lower() or "don't" in desc.lower()
        if not has_when:
            errors.append("R-28: description missing trigger phrases (no 'Use when' or 'trigger')")
        if not has_not:
            errors.append("R-51: description missing negative triggers (no 'Do NOT use for')")

    # R-77: body under 5,000 words
    word_count = count_words(body)
    if word_count > 5000:
        errors.append(f"R-77: SKILL.md body is {word_count} words (max 5,000)")

    # R-35: troubleshooting section
    if "## troubleshooting" not in body.lower() and "## common issues" not in body.lower() and "## common patterns" not in body.lower():
        errors.append("R-35: missing Troubleshooting/Common Issues section")

    # R-24: no README.md inside skill folder
    if (skill_dir / "README.md").exists():
        errors.append("R-24: README.md found inside skill folder (not allowed)")

    # R-44: triggers.json
    triggers_file = skill_dir / "triggers.json"
    if not triggers_file.exists():
        errors.append("R-44: triggers.json not found")
    else:
        try:
            triggers = json.loads(triggers_file.read_text())
            pos = triggers.get("should_trigger", [])
            neg = triggers.get("should_not_trigger", [])
            if len(pos) < 4:
                errors.append(f"R-44: triggers.json has {len(pos)} positive cases (min 4)")
            if len(neg) < 4:
                errors.append(f"R-44: triggers.json has {len(neg)} negative cases (min 4)")
        except json.JSONDecodeError as e:
            errors.append(f"R-44: triggers.json is invalid JSON: {e}")

    return errors


def main():
    skills_dir = Path(__file__).parent.parent / "skills"
    if not skills_dir.exists():
        print(f"error: skills directory not found at {skills_dir}")
        sys.exit(1)

    # Find all skill directories (skip workspaces)
    skill_dirs = [
        d for d in sorted(skills_dir.iterdir())
        if d.is_dir()
        and not d.name.endswith("-workspace")
        and not d.name.startswith(".")
    ]

    if not skill_dirs:
        print("no skill directories found")
        sys.exit(1)

    total_errors = 0
    total_warnings = 0

    for skill_dir in skill_dirs:
        errors = lint_skill(skill_dir)
        status = "PASS" if not errors else "FAIL"
        print(f"\n{'=' * 60}")
        print(f"  {skill_dir.name}: {status}")
        print(f"{'=' * 60}")

        if errors:
            for err in errors:
                print(f"  {err}")
            total_errors += len(errors)
        else:
            print("  all checks passed")

    print(f"\n{'=' * 60}")
    print(f"  summary: {len(skill_dirs)} skills, {total_errors} errors")
    print(f"{'=' * 60}")

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
