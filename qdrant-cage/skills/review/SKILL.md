# /cage-review - code review with implementation context

you are a senior engineer reviewing a feature implementation.

## trigger

user runs `/cage-review <feature-name>`

## pre-check: pipeline gating

```bash
cage pipeline get <feature-name>
```

only proceed if state is `tests-passing`. if not:
- if `implemented`: "checks haven't passed yet. run cage check first"
- if earlier: "feature isn't ready for review"

## workflow

### 1. gather context

read these files:
- `docs/features/<feature-name>.md` (the spec: what was intended)
- `docs/features/implementation-decisions/<feature-name>.md` (WHY choices were made)
- `shared/` contracts (what changed)

### 2. understand the diff

```bash
git diff main..feat/<feature-name> --stat
git diff main..feat/<feature-name>
```

### 3. run semantic checks

use cage search to verify the implementation matches the spec:

```bash
cage search "<key concept from spec>"
cage check run .
```

### 4. review checklist

evaluate the implementation against:

**contract integrity**
- [ ] are all shared values used from shared/, not hardcoded?
- [ ] are API response shapes captured in api-field-snapshots.json?
- [ ] are domain values in domain-values.json?

**boundary integrity**
- [ ] no cross-service imports?
- [ ] HTTP calls go through centralized client?
- [ ] no duplicated logic across services?

**code quality**
- [ ] implementation matches the spec?
- [ ] edge cases handled?
- [ ] error handling present?
- [ ] no debug code left behind?

**tests**
- [ ] new code has tests?
- [ ] existing tests still pass?

**docs**
- [ ] implementation-decisions doc explains WHY?
- [ ] CLAUDE.md updated if new patterns introduced?

### 5. decision

if the review passes:
```bash
cage pipeline transition <feature-name> reviewed
```

tell the user: "review passed. run `cage merge feat/<feature-name>` to merge."

if the review has issues:
```bash
cage pipeline transition <feature-name> implemented
```

tell the user what needs to change. the feature goes back to `implemented` for fixes.
