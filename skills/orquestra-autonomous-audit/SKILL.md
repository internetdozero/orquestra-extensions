---
name: orquestra-autonomous-audit
description: Time-boxed autonomous code audit and hardening shift. Executes continuous multi-scope sweeps, atomic 1-issue commits with reproduction tests, formal negative passes, optional idea-vault/board integration, and structured ledger persistence.
---

# Autonomous Code Audit Shift

Autonomous protocol for continuous, time-boxed software audits across multi-harness fleets. Breaks the premature-stop reflex by locking the agent into an active endurance shift until the specified duration expires or all scopes yield verified negative passes.

---

## 1. Parameters & Defaults

When triggered (e.g. `/autonomous-audit [duration] [scopes]`):
- **Duration ($X$ minutes):** User-specified time window (e.g., `60m`, `120m`, `180m`). Defaults to **120 minutes** if omitted.
- **Target Scopes:** User-specified comma-separated list (e.g. `security, api, database`). If omitted, defaults to the **4 Universal Scopes**:
  1. `Security & Hardening`: Path/symlink traversal, command/SQL injection, input sanitization, secret/key leaks, unsafe deserialization.
  2. `Performance & Resources`: Memory leaks, unbounded reads/file parsing, hot-path CPU contention, event-loop stalls, unnecessary re-renders.
  3. `Reliability & Logic`: Unchecked unwraps/panics on external input, unhandled error paths, race conditions, config drift, edge-case regressions.
  4. `Workflow & DX`: Objective dead code, redundant configuration, anti-monolith file cap violations (>300-400 lines), broken contracts.

---

## 2. Invariants & Ground Rules

1. **Anti-Premature-Stop & Anti-Idling Invariant:**
   - Never stop after fixing a single issue. Once an issue is committed and logged, immediately advance to the next scope or investigation vector.
   - The shift runs actively for the **entire duration**. Finishing primary sweeps or logging negative passes does NOT terminate the shift.
   - **STRICTLY FORBIDDEN:** Executing `sleep`, `timeout`, or any idle-waiting command to burn shift time. Every turn MUST produce active repository inspection, test execution, or patch evaluation.
   - **Continuous Deepening Expansion:** If all declared scopes yield verified negative passes before the shift duration expires, the agent **MUST NOT STOP OR SLEEP**. It must immediately transition to the Deepening Loop:
     - *Vector A (Test Coverage Gaps):* Audit `tests/` across packages, find uncovered functions or edge cases, and author rigorous unit tests.
     - *Vector B (Fuzzing & Hostile Inputs):* Stress-test public entry points and MCP handlers with boundary, negative, and malformed inputs.
     - *Vector C (Typing & Linting Drift):* Run linters or typecheckers to fix unhandled type edge-cases and eliminate dead code.
     - *Vector D (Idea Vault Backlog):* If `idea-vault` is connected or backlog items exist in the ledger, pick and implement the highest-priority architectural improvement.
2. **Atomic Micro-Commits (1 Defect = 1 Commit):**
   - Strictly one problem per commit. Never bundle disparate natures into a single commit.
   - Standard Conventional Commits (`fix(scope): ...`, `perf(scope): ...`, `refactor(scope): ...`).
   - **STRICTLY FORBIDDEN:** Running `git push` unless explicitly ordered by the operator.
3. **Reproduction Oracle Mandatory:**
   - Every behavioral fix MUST have a failing test before the patch that passes after the patch (Rust `#[test]`, `node --test`, `pytest`).
   - Non-behavioral cleanups (dead code, configs) require a captured command showing defect elimination (e.g. `rg`).
   - Pure prose is not proof.
4. **RAM & Workspace Safety:**
   - NEVER write scratch or temporary test files to RAM-backed `/tmp/`. Use `/var/tmp/testing/` or local test fixtures.

---

## 3. Execution Cycle (Per Defect)

```
[Scan Scope] 
     │
     ▼
[Confirm Real Defect?] ──(No)──► [Log Formal Negative Pass at current HEAD] ──► [Next Scope]
     │ (Yes)
     ▼
[Write Failing Reproduction Test] (Assert failure before fix)
     │
     ▼
[Apply Minimal Surgical Patch]
     │
     ▼
[Run Verification Suite] (Ensure test passes + whole suite stays green)
     │
     ▼
[Commit Locally (1 problem = 1 commit)] (Conventional Commit)
     │
     ▼
[Append Entry to Audit Ledger]
     │
     ▼
[Advance to Next Vector]
```

---

## 4. Formal Negative Pass Protocol

When an exhaustive scan of a scope yields no reproducible defects:
- **Do NOT manufacture artificial or trivial edits.**
- Append a formal Negative Entry to the ledger at current `HEAD`:
  ```markdown
  - **Commit:** `<current_HEAD_short_hash>`
  - **Files:** none
  - **Scope:** `<Scope Name>`
  - **Diagnosis:** Negative pass. Inspected [vectors/files]; no reproducible defect found.
  ```

---

## 5. Audit Ledger & Telemetry (External State Machine)

To survive context window compaction and enable inter-agent handoff, the agent maintains an external markdown ledger at:
`./.orquestra/audits/audit-YYYY-MM-DD.md` (create `./.orquestra/audits/` if absent).

Every entry strictly follows this 4-field schema:
```markdown
- **Commit:** `<hash>`
- **Files:** `<file1>`, `<file2>`
- **Scope:** `<Security | Performance | Logic | Workflow>`
- **Diagnosis:** `<Concise technical diagnosis of root cause and fix>`
```

On start or after context compaction, the agent reads the ledger to instantly re-synchronize what has been completed, what scopes remain, and where the shift left off.

---

## 6. Task Backlog & Inter-Agent Board (Optional `idea-vault` Integration)

During deep sweeps, the auditor will inevitably uncover broader architectural improvements, deferred technical debt, or multi-step refactors that exceed the scope of an atomic micro-commit.

### Protocol:
1. **When `idea-vault` MCP is connected:**
   - **Capture Backlog Ideas:** Register non-trivial future tasks immediately via:
     `record_idea(project="<project>", title="<title>", description="<details>", category="<category>", priority="<priority>")`
   - **Post Blackboard Alerts:** If an issue requires attention from a different specialist agent or a peer working concurrently, post an asynchronous note via:
     `post_board_note(note="[Audit Alert] ...")`
   - **Task Lifecycle:** If the operator triggered the audit to address an existing Idea Vault item, update its status (`in_progress` on kickoff, `completed` on verified negative/resolution).

2. **When `idea-vault` MCP is absent (Graceful Zero-Dependency Fallback):**
   - The absence of the MCP **must NEVER halt, block, or degrade** the audit shift.
   - The agent transparently falls back to recording future recommendations and warnings directly into the audit ledger under an `### Open Backlog & Future Tasks` section at the end of the file.
