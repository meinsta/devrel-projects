# CAGE

Contract-enforced Agent-Guided Engineering.

The agent is powerful. The cage is the product.

## what is this

CAGE is an agent-native development infrastructure framework. it provides the
contracts, guardrails, skills, execution policies, and worktree isolation that
make AI coding agents produce production-quality code instead of slop.

the agent is interchangeable (Claude Code, Codex, Gemini). the cage is what
makes it work.

## core ideas

1. **contracts over conventions**: cross-service truth lives in `shared/`.
   pre-commit hooks enforce sync. agents can't break contracts.

2. **skills over improvisation**: agents follow documented procedures (`/spec`,
   `/feature`, `/audit`, `/review`), not freeform prompting.

3. **scripted lifecycle**: agents use `cage infra start`, not raw commands.
   `cage merge`, not `git merge`. sanctioned scripts, not freehanding.

4. **execution policy**: `cage.rules` blocks dangerous commands and points to
   safe alternatives. enforced via hooks, not trust.

5. **worktree isolation**: each feature gets its own worktree. agents never
   merge. a sanctioned script handles integration.

6. **audit tracking**: git tags record when each surface was last audited.
   `cage status` shows staleness.

7. **docs as context**: agents read feature specs, design docs, and bug
   trackers. agents write back what they learn.

## install

```bash
git clone <repo-url> ~/.cage/cage
cd ~/.cage/cage
./setup
# add to PATH:
echo 'export PATH="$HOME/.cage/cage/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## usage

### initialize a project

```bash
cd your-project
cage init
pre-commit install
```

this creates:
- `shared/` with contract templates
- `docs/` with feature/design/bug structure
- `cage.rules` execution policy
- `.pre-commit-config.yaml` with architectural checks
- `CLAUDE.md` with agent context

### feature lifecycle

```bash
# 1. create a spec (product manager workflow)
/spec user-profiles

# 2. implement on a worktree (engineering workflow)
/feature user-profiles

# 3. review the implementation
/review

# 4. safe merge back
cage merge feat/user-profiles

# 5. ship
/ship
```

### infrastructure

```bash
# define services in cage-infra.yaml
cage infra start    # start all services
cage infra stop     # safe teardown
cage infra status   # show running services
```

### audits

```bash
/audit frontend     # audit frontend, tag with date
/audit backend      # audit backend
/audit contracts    # audit shared contracts
cage status         # see time since last audit
```

### execution policy

```bash
cage policy         # view current rules
/cage-policy        # add/modify rules
cage check policy   # validate syntax
```

### worktrees

```bash
cage worktree prepare my-feature   # create + bootstrap
cage worktree list                 # show active worktrees
cage worktree clean                # remove merged worktrees
cage merge feat/my-feature         # safe squash merge
```

### checks

```bash
cage check              # run all checks
cage check contracts    # validate contract sync
cage check architecture # run architectural invariants
cage check policy       # validate cage.rules
```

## project structure (after cage init)

```
your-project/
  shared/
    domain-values.json       # centralized domain constants
    api-field-snapshots.json  # API response shapes
    schemas.json              # data schemas
  docs/
    features/                # permanent implementation knowledge
    designs/                 # temporary technical plans
    bugs.md                  # active issues
    bugs-archive/            # resolved issues
    wireframes/              # UI references
  checks/                   # project-specific architectural checks
    contract-*.sh            # contract sync checks
    arch-*.sh                # architectural invariant checks
  cage.rules                # execution policy
  cage-infra.yaml           # service definitions
  .pre-commit-config.yaml   # hooks
  CLAUDE.md                 # agent context
  .cage/                    # local state (gitignored)
```

## skills

| skill | what it does |
|-------|-------------|
| `/spec` | product manager workflow: feature spec, user stories, wireframes |
| `/feature` | engineering workflow: read spec, reassess, implement on worktree, test |
| `/audit` | codebase audit with git tag tracking for staleness |
| `/cage-policy` | manage execution policy (cage.rules) |

CAGE also works with gstack skills (`/review`, `/qa`, `/ship`, `/design-review`)
or any other skill system.

## writing architectural checks

add executable scripts to your project's `checks/` directory:

- `checks/contract-*.sh` runs during `cage check contracts`
- `checks/arch-*.sh` runs during `cage check architecture`

each check should exit 0 on success, non-zero on failure, and print
human-readable output.

example:

```bash
#!/usr/bin/env bash
# checks/arch-no-hardcoded-ports.sh
if grep -rn "localhost:[0-9]" src/ --include="*.ts" | grep -v "cage-infra"; then
  echo "FAIL: hardcoded ports found. use cage-infra.yaml port slots."
  exit 1
fi
echo "ok: no hardcoded ports"
```

## philosophy

agents are good at writing code. agents are bad at:
- knowing which commands are safe to run
- resolving merge conflicts
- maintaining cross-service consistency
- knowing when to stop and ask
- auditing their own work over time

CAGE solves these by making the boundaries explicit, automated, and enforced.
the agent operates freely inside the cage. the cage is what makes that freedom
productive instead of destructive.

## license

MIT
