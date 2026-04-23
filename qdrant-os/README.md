# qdrant-os

Skills for Qdrant. Diagnose memory problems, reduce costs, and unblock deals
without re-explaining the same things every conversation.

## What these skills do

Skills teach Claude *when* and *why* to recommend specific Qdrant
optimizations. They navigate to the right documentation based on symptoms.
They do not replace the docs or implement solutions directly.

| Skill | For | What it solves |
|-------|-----|---------------|
| `qdrant-memory-optimization` | Developers | OOM crashes, disk latency, quantization selection, memory estimation |
| `qdrant-cost-reduction-advisor` | SAs (internal) | Sticker shock, scaling cost projections, competitor pricing |
| `qdrant-deal-unblocker` | SAs (internal) | Deals stalled by cost, missing features, performance, or competition |

## Install

### Claude Code

Clone into your skills directory:

```bash
git clone https://github.com/qdrant/qdrant-os
```

Skills are detected automatically from the `skills/` directory.

### Claude.ai

1. Download the skill folder (or zip it)
2. Go to Settings > Capabilities > Skills
3. Upload the skill folder

## How skills are structured

Each skill follows a three-level progressive disclosure pattern:

```
skill-name/
  SKILL.md           # Router: identifies symptom, routes to reference
  references/        # Detail: diagnosis, fixes, formulas
  triggers.json      # Test cases for trigger accuracy
```

- **Frontmatter** (always loaded): tells Claude *when* to activate
- **SKILL.md body** (loaded on activation): symptom routing table, decision tree, anti-patterns
- **references/** (loaded on demand): detailed diagnosis and fix for each symptom

## Validate

```bash
python3 scripts/lint-skills.py
```

Checks naming, description quality, word count, triggers.json presence,
and troubleshooting sections.

## Contributing

See `rules/INDEX.md` for the full rulebook (95 rules). Key points:

- Skills answer "when?" and "why?", not "how?"
- SKILL.md is a router, not an encyclopedia (under 200 lines)
- The "how" lives in references/ and links to Qdrant docs
- Every skill needs triggers.json with 4+ positive and 4+ negative cases
- Every skill needs a Troubleshooting section with 2+ error cases
