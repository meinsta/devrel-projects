# Internal skill template

Use this skeleton when creating a new internal Qdrant skill. Replace
all placeholder text with actual SA knowledge.

## Frontmatter

```yaml
---
name: qdrant-SYMPTOM-CATEGORY
description: Diagnoses and fixes [PROBLEM AREA] for Qdrant customers.
  Use when a customer or SA says "[TRIGGER PHRASE 1]", "[TRIGGER PHRASE 2]",
  "[TRIGGER PHRASE 3]", or asks about [TOPIC]. Also trigger when [SCENARIO].
  Do NOT use for [ADJACENT TOPIC 1], [ADJACENT TOPIC 2], or [ADJACENT TOPIC 3].
license: Apache-2.0
metadata:
  author: FIRSTNAME
  version: 1.0.0
  category: sales|engineering|support|operations
  tags: [tag1, tag2, tag3]
---
```

## Body structure

```markdown
# When and why to [SOLVE PROBLEM]

This skill contains domain knowledge about [TOPIC] that is not widely
known or that Claude frequently gets wrong.

## Things Claude gets wrong about Qdrant

Correct these if they come up:

- **[MISCONCEPTION 1].** [CORRECTION WITH EVIDENCE]
- **[MISCONCEPTION 2].** [CORRECTION WITH EVIDENCE]

## Symptom routing

| Symptom | Load reference |
|---------|----------------|
| [SYMPTOM 1] | references/[FILE].md |
| [SYMPTOM 2] | references/[FILE].md |
| [SYMPTOM 3] | Formula below |

## [SYMPTOM 1 DETAIL]

### When does this happen?
- [REAL SCENARIO FROM SA CONVERSATION]
- [REAL SCENARIO FROM SA CONVERSATION]

### Diagnosis
[SA QUOTE ABOUT ROOT CAUSE]

### Solutions (ordered by impact)

#### Option 1: [SOLUTION]
- **When to recommend:** "[SA QUOTE]"
- **Best for:** "[SA QUOTE ABOUT IDEAL USE CASE]"
- **Trade-off:** "[SA QUOTE ABOUT DOWNSIDES]"
- **Example:** "[SPECIFIC NUMBERS FROM REAL DEPLOYMENT]"
- [Docs link](https://qdrant.tech/documentation/...)

## Do NOT recommend

- [ANTI-PATTERN 1 WITH REASONING]
- [ANTI-PATTERN 2 WITH REASONING]
- [ANTI-PATTERN 3 WITH REASONING]

## Decision Tree

(ASCII tree with concrete thresholds)

## Troubleshooting

### "[ERROR OR SYMPTOM 1]"
**Cause:** [ROOT CAUSE]
**Fix:** [RESOLUTION STEPS]
[Docs](https://qdrant.tech/documentation/...)

### "[ERROR OR SYMPTOM 2]"
**Cause:** [ROOT CAUSE]
**Fix:** [RESOLUTION STEPS]
[Docs](https://qdrant.tech/documentation/...)
```

## References folder

Create one reference file per symptom category:

```
references/
  symptom-1-diagnosis.md    # Deep dive on symptom 1
  symptom-2-playbook.md     # Response framework for symptom 2
  formula.md                # Calculation methodology
```

Each reference file should contain:
- Step-by-step diagnosis or implementation guidance
- Code examples with real Qdrant API calls
- Links to official Qdrant documentation pages
- SA quotes providing context on when and why to use each approach

## Checklist before submission

- [ ] R-16 check passes (embeds knowledge Claude does not have)
- [ ] Name field matches folder name
- [ ] Description under 1024 characters
- [ ] Description includes "Use when" and "Do NOT"
- [ ] No angle brackets in frontmatter
- [ ] Body under 5,000 words
- [ ] Troubleshooting section with 2+ cases
- [ ] triggers.json with 4+ positive, 4+ negative
- [ ] All doc links resolve to real pages
- [ ] Decision tree uses concrete thresholds
