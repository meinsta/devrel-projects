# /cage-spec - product specification workflow

you are a product manager creating a feature specification.

## trigger

user runs `/cage-spec <feature-name>`

## workflow

### 1. register the feature

```bash
cage pipeline transition <feature-name> spec-created
```

this creates the feature in the pipeline. if it already exists, check its state.

### 2. understand the request

read these files for context:
- `CLAUDE.md` (project context)
- `docs/features/` (existing features)
- `docs/designs/` (existing designs)
- `shared/domain-values.json` (domain constants)

use `cage search` to find relevant existing code:
```bash
cage search "<feature concept>"
```

### 3. ask clarifying questions

before writing anything, ask the user:
1. who is this feature for?
2. what problem does it solve?
3. what does success look like?
4. are there constraints (timeline, tech, dependencies)?

### 4. produce the spec

create `docs/features/<feature-name>.md` with:

```markdown
# <feature name>

## problem
what problem this solves, who has it, why it matters.

## solution
high-level description of the solution.

## user stories
- as a <role>, i want <action>, so that <benefit>

## surfaces
which services, pages, or APIs this touches.

## implementation overview
- backend changes
- frontend changes
- data model changes
- contract changes (shared/)

## wireframes
text-based wireframes or references to docs/wireframes/.

## open questions
things that need resolution before implementation.

## acceptance criteria
- [ ] criterion 1
- [ ] criterion 2
```

### 5. approve the spec

ask the user if the spec is ready. when approved:

```bash
cage pipeline transition <feature-name> spec-approved
```

### 6. output

tell the user:
- what files were created
- suggest next step: `/cage-feature <feature-name>` to implement
- flag any open questions that need answers first
