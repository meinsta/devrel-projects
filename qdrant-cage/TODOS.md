# TODOS

## v0.2

### agent session history
Log which skill ran, what files changed, what contracts were modified, timestamp, branch.
`cage history` shows the trail. Useful for auditing what agents did to your codebase
and for catching cases where a contract was modified without checks running.

**Why:** Multi-agent workflows need observability. Git log shows file changes but not
which skill triggered them or whether the right checks ran.

**Effort:** M (CC: ~30 min) | **Priority:** P2
**Depends on:** cage-core binary (v0.1)

### /cage-setup-tests skill
Dedicated skill that reads what changed during feature implementation, determines the
right test strategy (integration for backend, playwright for frontend, contract sync
for shared/), and scaffolds test files with appropriate fixtures.

**Why:** /cage-feature currently handles test setup inline, but a dedicated skill can
be smarter about test patterns once we see how users structure their projects.

**Effort:** S (CC: ~15 min) | **Priority:** P3
**Depends on:** /cage-feature being stable, user feedback on test patterns

## v0.3+

### declarative check DSL
Instead of writing TypeScript check modules, users define rules in a config:
```yaml
checks:
  no-cross-import:
    rule: no-import
    from: "services/*/internal/**"
    to: "services/*/"
  no-hardcoded-ports:
    rule: no-literal
    pattern: "localhost:[0-9]+"
    exclude: "cage-infra.yaml"
```
CAGE compiles these to AST checks at pre-commit time.

**Why:** Peyton built 12+ checks as custom scripts. Most follow a few patterns
(import boundary, literal detection, schema sync). A DSL captures those patterns
without requiring users to write TypeScript.

**Effort:** L (CC: ~1 hour) | **Priority:** P2
**Depends on:** v0.1 check system proving which patterns are common
