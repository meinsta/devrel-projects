# Jobs-to-Be-Done Framework
## California Housing Statutes App

## Core Job (Functional)

**"When I'm handling a California landlord-tenant matter, I need to locate, interpret, and operationalize the controlling statutes (and local carve-outs) so I can produce compliant actions, filings, and timelines with defensible citations—fast."**

## Key Job Stories

### Research & Understanding

#### 1. Locate controlling law
**When** I receive a housing issue (e.g., nonpayment, habitability), **I want to** surface the governing Civil Code/Code of Civ. Proc. sections and any local rent-control overlays, **so I can** anchor advice and next steps to the correct authority.

#### 2. Resolve definitions & exceptions
**When** statute text hinges on terms like "rent," "dwelling unit," or "owner," **I want** the app to pull definitions and follow "except as provided…" cross-refs, **so I can** apply the right scope without misreading carve-outs.

#### 3. Disambiguate conflicts
**When** multiple sections appear to conflict, **I want** a decision log explaining priority (general vs. specific, later-enacted, local preemption), **so I can** justify which rule controls.

### Action & Execution

#### 4. Generate procedural workflow
**When** I choose the issue and party type (e.g., nonpayment, month-to-month), **I want** a step-by-step checklist (Notice → Filing → Service → Hearing → Writ) with deadlines and forms, **so I can** execute without missing requirements.

#### 5. Compute deadlines
**When** a date triggers a clock (service date, move-out, filing), **I want** exact due dates (calendar vs business days, weekend/holiday rules), **so I can** avoid sanctions or dismissal for late/defective timing.

#### 6. Assemble filings & packets
**When** I'm ready to act, **I want** auto-filled notices, cover sheets, and evidence lists—with cites and line-level quotes—**so I can** file or serve with minimal rework.

### Quality & Risk

#### 7. Verify every claim
**When** I finalize advice or a document, **I want** every legal assertion to include a verbatim quoted span with section and line, **so I can** defend it to a judge or opposing counsel.

#### 8. Flag local variations
**When** the client is in a rent-controlled jurisdiction (e.g., LA, SF, Oakland), **I want** the app to flag stricter local rules, **so I can** avoid relying on state defaults where preempted.

#### 9. Know when to abstain
**When** the law is ambiguous or fact-dependent, **I want** the app to say "insufficient statutory basis" and show why, **so I can** prudently escalate or research further.

## Outcome Statements (ODI-style)

- **Increase** probability of retrieving the controlling section on first query
- **Reduce** time-to-first-answer from minutes to seconds for common issues
- **Increase** proportion of answers with line-level verbatim quotes to ≥ 95%
- **Reduce** missed deadlines due to calendar/business-day confusion to 0
- **Increase** detection of "definition/exception required" cases to >90%
- **Reduce** filings rejected for procedural defects by >80%
- **Increase** one-click packet generation usage to >70% of workflows
- **Increase** local-rule flagging coverage for top CA cities to 100%

## Forces Diagram

### Push (pain)
- Messy statutes with cross-refs
- Local overlays (rent control)
- Deadline traps
- Filing rejections

### Pull (desire)
- Trusted, cited steps
- Computed dates
- Exportable packets
- Verified quotes

### Anxieties
- Hallucination
- Outdated law
- Over-automation
- Local rules missed

### Habits
- Manual Westlaw/Lexis
- Firm checklists
- Calendar math spreadsheets

## Segmented Jobs (by user type)

### Attorney/Paralegal
Fast, defensible workflows; quote-verified memos; reduce non-billable research

### Property Manager/Owner
Plain-English steps, dates, forms; "what to do next" clarity

### Tenant Advocate/Legal Aid
Fact-pattern triage, defenses (habitability, retaliation), fee waivers

### Self-Represented Litigant
Guided Q&A, simple outputs, courthouse checklists

## Opportunity Scoring (Importance × Underserved)

### Build First:
1. **Deadline computation** (high × high) → DateMath with holiday logic
2. **Definition/exception resolution** (high × high) → FollowRef + Define gates
3. **Procedural workflow builder** (high × medium) → 5-step eviction/nonpayment checklist

### Build Next:
4. **Packet generation** (medium-high × medium) → notices, covers, evidence lists
5. **Local-rule flags** (high × high) → city detection + overlays (MVP for LA/SF/OAK)

### Already Have:
6. **Vanilla RAG answer with quotes** (medium × partly served) → baseline stays

## Feature Mapping → Jobs

| Feature | Serves Job |
|---------|-----------|
| Hybrid search (Qdrant dense+sparse) | Locate controlling law |
| RAG with line-verified quotes | Verify every claim |
| Agent tools: FollowRef, Define, DateMath | Resolve definitions/exceptions, Compute deadlines |
| Workflow composer (Notice→Writ) | Generate procedural workflow |
| Local overlay detector | Flag local variations |
| Packet exporter (PDF/ZIP) | Assemble filings & packets |
| Abstain policy | Know when to abstain |

## Acceptance Criteria (Done = usable by a litigator)

- [ ] Every step card shows (a) statute § link, (b) verbatim quote lines, (c) computed due date if applicable, (d) required docs
- [ ] If a retrieved passage contains "except as provided in §", the step also cites that referenced §
- [ ] If the query/step uses a defined term, the definition § is cited
- [ ] Date rules indicate calendar vs business days and account for CA court holidays
- [ ] Exported packet includes notice + proof of service template + evidence list with fields prefilled
- [ ] UI displays jurisdiction badges (e.g., "California · LA; local rules vary")
- [ ] Logged Decision Log (plan → evidence → synthesis) is downloadable for the file

## Anti-Jobs (what not to do)

- ❌ Don't "summarize all housing law"; focus on actionable workflows
- ❌ Don't guess local ordinances without coverage; flag and link out
- ❌ Don't output uncited conclusions; abstain if unverifiable

## KPIs to Prove Value

- Median time-to-workflow (query → 5-step plan)
- % steps with verified quotes and no corrections
- Packet exports per active user
- Deadline error rate (self-reported or QA)
- Adoption of local-rule flagging (cities covered / run rate)

## One-Slide Positioning

**"From statute to step-by-step—in minutes, with receipts."**

CA housing law, operationalized: verified cites, computed dates, local flags, and export-ready packets. Built on Qdrant hybrid search + RAG + a minimal agent that adds capabilities, not fluff.

