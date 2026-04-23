# External/community skill template

Use this skeleton when creating a community Qdrant skill. Community skills
reference only public Qdrant documentation. No internal customer data.

## Frontmatter

```yaml
---
name: qdrant-TOPIC-NAME
description: Diagnoses and fixes [PROBLEM AREA] for Qdrant deployments.
  Use when a developer reports "[TRIGGER PHRASE 1]", "[TRIGGER PHRASE 2]",
  "[TRIGGER PHRASE 3]", or asks about [TOPIC]. Also trigger when someone
  asks "[PARAPHRASED TRIGGER]". Do NOT use for [ADJACENT TOPIC 1],
  [ADJACENT TOPIC 2], or [ADJACENT TOPIC 3].
license: Apache-2.0
metadata:
  author: GITHUB-USERNAME
  version: 1.0.0
  category: operations|development
  tags: [tag1, tag2, tag3]
---
```

## Body structure

```markdown
# When and why to [SOLVE PROBLEM]

This skill contains domain knowledge about [TOPIC] that Claude
frequently gets wrong or is missing entirely.

## Things Claude gets wrong about Qdrant

Correct these if they come up:

- **[MISCONCEPTION 1].** [CORRECTION WITH EVIDENCE]
- **[MISCONCEPTION 2].** [CORRECTION WITH EVIDENCE]
- **[MISCONCEPTION 3].** [CORRECTION WITH EVIDENCE]

## Step 1: Identify the symptom

| Symptom | Load reference |
|---------|----------------|
| [SYMPTOM 1 IN DEVELOPER LANGUAGE] | references/[FILE].md |
| [SYMPTOM 2 IN DEVELOPER LANGUAGE] | references/[FILE].md |
| [SYMPTOM 3 IN DEVELOPER LANGUAGE] | Formula below |

## Step 2: [APPLY CORE KNOWLEDGE]

[FORMULA, DECISION MATRIX, OR DIAGNOSTIC STEPS]

Keep this section focused on WHEN and WHY.
Link to Qdrant docs for HOW.

## Do NOT recommend

- [ANTI-PATTERN 1 WITH REASONING]
- [ANTI-PATTERN 2 WITH REASONING]
- [ANTI-PATTERN 3 WITH REASONING]

## Decision tree

(ASCII tree with concrete thresholds, not vague guidance)

```
[PROBLEM]
  |
  +-- [CONDITION 1] (concrete threshold)
  |   -> [RECOMMENDATION]
  |   -> [DOC LINK]
  |
  +-- [CONDITION 2] (concrete threshold)
      -> [RECOMMENDATION]
      -> [DOC LINK]
```

## Troubleshooting

### "[ERROR MESSAGE OR SYMPTOM 1]"
**Cause:** [ROOT CAUSE]
**Fix:** [RESOLUTION STEPS]
[Docs](https://qdrant.tech/documentation/...)

### "[ERROR MESSAGE OR SYMPTOM 2]"
**Cause:** [ROOT CAUSE]
**Fix:** [RESOLUTION STEPS]
[Docs](https://qdrant.tech/documentation/...)
```

## References folder

Create one reference file per symptom or topic:

```
references/
  symptom-1-diagnosis.md
  symptom-2-guide.md
  configuration-reference.md
```

Each reference file should:
- Focus on "when and why", not full API documentation
- Include code examples with real Qdrant API calls
- Link to official Qdrant documentation for implementation
- Stay under 1,000 words

## Doc link patterns

Always use these URL patterns for Qdrant documentation links:

```
Concepts:
  https://qdrant.tech/documentation/concepts/collections/
  https://qdrant.tech/documentation/concepts/vectors/
  https://qdrant.tech/documentation/concepts/storage/
  https://qdrant.tech/documentation/concepts/indexing/
  https://qdrant.tech/documentation/concepts/search/

Guides:
  https://qdrant.tech/documentation/guides/quantization/
  https://qdrant.tech/documentation/guides/monitoring/
  https://qdrant.tech/documentation/guides/capacity-planning/
  https://qdrant.tech/documentation/guides/distributed_deployment/

Tutorials:
  https://qdrant.tech/documentation/tutorials/
```

## Checklist before submission

- [ ] R-16 check passes (teaches Claude something it gets wrong)
- [ ] No internal customer data or SA conversations
- [ ] All links point to public qdrant.tech documentation
- [ ] Name field matches folder name
- [ ] Description under 1024 characters
- [ ] Description includes "Use when" and "Do NOT"
- [ ] No angle brackets in frontmatter
- [ ] Body under 5,000 words
- [ ] Troubleshooting section with 2+ cases
- [ ] triggers.json with 4+ positive, 4+ negative
- [ ] Decision tree uses concrete thresholds
