# /cage-audit - codebase audit with git tag tracking

you are an engineering agent performing a codebase audit.

## trigger

user runs `/cage-audit <surface>` where surface is: frontend, backend, contracts, all

## workflow

### 1. check audit history

```bash
cage status
```

### 2. run semantic analysis

use cage search to find problem areas:

```bash
cage search "error handling"
cage search "TODO FIXME HACK"
cage search "hardcoded configuration values"
```

### 3. run automated checks

```bash
cage check run .
```

### 4. surface-specific audit

#### frontend audit
- check for unused components and dead code
- verify all routes are reachable
- verify shared contract consumption
- check for hardcoded values that should be in shared/
- verify error handling on all API calls
- run: `cage search "fetch error catch" `

#### backend audit
- check for unused endpoints
- verify all endpoints have tests
- verify shared contract production
- check for hardcoded values
- verify logging coverage
- run: `cage search "endpoint handler route"`

#### contract audit
- verify all shared/ files are consumed by at least one service
- check for stale entries
- verify api-field-snapshots match actual API responses
- run: `cage check contracts`

### 5. produce report

create `.cage/audits/<surface>-<date>.md` with findings.

### 6. tag the audit

```bash
git tag "audit/<surface>/$(date +%Y-%m-%d)"
```

### 7. re-index after fixes

if any fixes were made:
```bash
cage index
```

### 8. output

tell the user:
- how many issues found by severity
- top 3 most important fixes
- time since last audit
