# Docs index

Everything in `docs/`, one line each. Status: **live** = kept current, **audit** = dated snapshot, **reference** = long-term, partly aspirational, **research** = sourced notes with UNVERIFIED labels, **pending** = being written, link will work when it lands.

## Core (what to read and keep current)

| Doc | Purpose | Status |
|-----|---------|--------|
| [PRD.md](PRD.md) | What we build and why: users, scope, success metrics, non-goals. | pending |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the system is built: layout, request flow, data, AI, safety design. | live |
| [DESIGN.md](DESIGN.md) | UI/UX design system, tone, accessibility and frontend budgets. | pending |
| [TRACKER.md](TRACKER.md) | Work items, priorities and open gaps; the live to-do list. | pending (lead writes it) |
| [RULES.md](RULES.md) | Engineering and AI-agent rulebook with IDs, enforcement, PR checklist, Definition of Done. | live |
| [MEMORY.md](MEMORY.md) | Durable project memory: snapshot, cleanup timeline, ADRs, glossary, gotchas, unknowns, hand-off template. | live |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Run locally, env vars, hosting notes, audio dataset on a server. | live (some lines stale, see MEMORY gotcha 7) |
| [MIGRATIONS.md](MIGRATIONS.md) | Alembic workflow, `SKIP_CREATE_ALL`, baseline 0001. | live |
| [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md) | Clinical safety rules: PHQ-9/GAD-7 bands, crisis handling, test fixtures, India helplines, regulation notes. | live; not clinical or legal advice |
| [STATUS.md](STATUS.md) | Nov 2026 audit: feature state, open issues, roadmap. | audit (predates many fixes; verify against tests) |

## Reference (long-term, partly aspirational)

| Doc | Purpose |
|-----|---------|
| [requirements.md](requirements.md) | Original system requirements document (Jan 2026); target scope, not what is built. |
| [target-design.md](target-design.md) | Aspirational system design (microservices, Kubernetes, PWA, MFA); NOT the running system. |
| [process-flow.md](process-flow.md) | Mermaid process flows; crisis escalation, provider alerts and RPM ingestion are designed, not built. |

## Research (`research/`, dated 2026-11-24, sourced, claims marked UNVERIFIED/SECONDARY must stay unverified)

| Doc | Purpose |
|-----|---------|
| [research/llm-security.md](research/llm-security.md) | OWASP LLM risks, prompt-injection defences, mental-health chatbot risks, Gemini privacy, 55-case test corpus, recommended AI pipeline. |
| [research/product-market.md](research/product-market.md) | India problem size, regulation, competitors, evidence on what works, personas, proposed metrics, claims we must not make, MoSCoW. |
| [research/queue-reliability.md](research/queue-reliability.md) | Job queue options, outbox and idempotency patterns, Gemini resilience, DB integrity, operability; basis for ADR-001. |

Outside `docs/`: [../README.md](../README.md) (project front page), [SECURITY.md](SECURITY.md) (how to report vulnerabilities), [../CLAUDE.md](../CLAUDE.md) (short rules loaded by AI agents).

## Reading order

**New engineer**
1. [../README.md](../README.md), then [MEMORY.md](MEMORY.md) section 1 (snapshot, run, test).
2. [ARCHITECTURE.md](ARCHITECTURE.md), then [DEVELOPMENT.md](DEVELOPMENT.md) and [MIGRATIONS.md](MIGRATIONS.md).
3. [RULES.md](RULES.md) (at least ARCH, CODE, API, SEC, TEST and the PR checklist).
4. [TRACKER.md](TRACKER.md) to pick a task; [MEMORY.md](MEMORY.md) section 5 (gotchas) before your first edit.
5. As needed: [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md), research notes.

**Product owner**
1. [PRD.md](PRD.md), then [TRACKER.md](TRACKER.md).
2. [research/product-market.md](research/product-market.md) (market, personas, claims we must not make).
3. [DESIGN.md](DESIGN.md), then [MEMORY.md](MEMORY.md) sections 3 and 6 (decisions, unknowns).
4. [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md) for what needs clinician and counsel review before launch.

**AI agent**
1. [../CLAUDE.md](../CLAUDE.md), then [RULES.md](RULES.md) (AGENT section first).
2. [MEMORY.md](MEMORY.md) (snapshot, gotchas, unknowns, hand-off template).
3. [TRACKER.md](TRACKER.md) for your assignment and file ownership; [ARCHITECTURE.md](ARCHITECTURE.md) for the area you touch.
4. Area docs: crisis, scoring or AI -> [SAFETY_RESEARCH.md](SAFETY_RESEARCH.md) and [research/llm-security.md](research/llm-security.md); jobs, retries, DB state -> [research/queue-reliability.md](research/queue-reliability.md); schema -> [MIGRATIONS.md](MIGRATIONS.md); UI -> [DESIGN.md](DESIGN.md).
5. End every session with the hand-off from MEMORY.md section 8.

## Doc ownership and update rule

One fact lives in one doc; other docs link to it. Update the owner doc in the same PR as the change.

| When this changes | Update | Also check |
|-------------------|--------|------------|
| Scope, users, success metrics, non-goals | PRD.md | TRACKER.md |
| Layout, blueprints, data flow, AI pipeline, deployment shape | ARCHITECTURE.md | MEMORY.md ADR if it is a decision |
| UI patterns, copy tone, accessibility, frontend budgets | DESIGN.md | RULES.md CONTENT/PERF |
| A task starts, finishes or is found | TRACKER.md | STATUS.md is not updated (frozen audit) |
| A rule is added, relaxed or its enforcement changes | RULES.md | The test that enforces it |
| A decision is made or reversed; a gotcha is learned; a fact is found UNVERIFIED | MEMORY.md (ADR, gotchas, unknowns) | RULES.md if a rule follows |
| Env vars, run/deploy steps, hosting | DEVELOPMENT.md and `.env.example` | README.md quick start |
| `models.py` or a migration | MIGRATIONS.md only if the workflow changes | Alembic file and `tests/test_db.py` |
| Helpline numbers or clinical thresholds | `utils/helplines.py` (bump `LAST_VERIFIED`) or `ai/scoring.py` | SAFETY_RESEARCH.md table |
| Crisis phrases or negation logic | `ai/severity.py` and `tests/test_safety.py` | SAFETY_RESEARCH.md fixtures |
| New research finding | The relevant `research/*.md` with a URL and a verified/UNVERIFIED label | MEMORY.md section 6 |
| Security reporting process | docs/SECURITY.md | README.md |
| Short agent rules | CLAUDE.md (keep under 40 lines) | RULES.md is the long form |

Conventions: every doc starts with a one-line purpose; facts must be checkable against files or tests; do not paste secrets, real user data or patient text; dated audits are replaced by a new dated doc, not silently edited; a doc that disagrees with code and tests is a bug in the doc.
