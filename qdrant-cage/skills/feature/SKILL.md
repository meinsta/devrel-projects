# /cage-feature - feature implementation workflow

you are an engineering agent implementing a feature from a spec.

## trigger

user runs `/cage-feature <feature-name>`

## pre-check: pipeline gating

before doing anything, verify the feature is ready for implementation:

```bash
cage pipeline get <feature-name>
```

if the state is NOT `spec-approved`, stop and tell the user:
- if `spec-created`: "spec needs approval. review docs/features/<feature-name>.md and run cage pipeline transition <feature-name> spec-approved"
- if not found: "no spec exists. run /cage-spec <feature-name> first"
- if `implemented` or later: "feature already implemented. check cage status"

only proceed if state is `spec-approved`.

## workflow

### 1. read the spec

- `docs/features/<feature-name>.md`
- `docs/designs/<feature-name>.md` (if exists)
- `shared/` contracts that will be affected

### 2. deep dive with semantic search

use cage search to understand the codebase before writing code:

```bash
cage search "<relevant concept from the spec>"
cage search "existing patterns for <similar feature>"
```

study:
- the surfaces this feature touches (read existing code)
- expected usage patterns and volume
- existing patterns for similar features
- shared contracts that need updating

### 3. reassess

compare the proposed implementation against what you found.
if the feature needs significant redesign:
- **stop and await input from the user**
- explain what you found and what needs to change
- do not proceed until the user confirms

### 4. prepare worktree

```bash
cage worktree prepare <feature-name>
cage pipeline transition <feature-name> worktree-prepared
```

### 5. implement

work in the worktree. follow these rules:
- update shared contracts first (shared/*.json)
- implement backend changes
- implement frontend changes
- update CLAUDE.md if new patterns are introduced
- write implementation decisions to `docs/features/implementation-decisions/<feature-name>.md`

after implementation:
```bash
cage pipeline transition <feature-name> implemented
```

### 6. validate

run checks and tests:
```bash
cage check
```

if checks pass and project tests pass:
```bash
cage pipeline transition <feature-name> tests-passing
```

### 7. output

tell the user:
- what was implemented (files changed)
- what contracts were updated
- what tests were added
- what decisions were made (reference the implementation-decisions doc)
- suggest next step: `/cage-review <feature-name>`

do NOT merge. the worktree stays open for review.
