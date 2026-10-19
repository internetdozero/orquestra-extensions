---
name: smart-build-router
description: Intelligently route build, test, and typecheck commands based on the exact change surface. Prevents wasteful test cascades, unneeded builds, and CPU overheating by only executing checks relevant to touched files.
---

# Smart Build Router

Ensure verification is strictly targeted to the change surface. Never run speculative, full-suite builds or heavy compiler commands when only a specific subsystem was touched.

## 1. Change-Surface Inspection

Before running any verification, check which files were modified:
- `rtk git status --short` or `rtk git diff --name-only`

Categorize modified files into one of the following domains:

### A. Frontend / UI Only (`src/`, `*.tsx`, `*.ts`, `*.css`, `*.html`, `public/`)
- **Action:** Verify types and bundle integrity only.
- **Run:** `npm run build` (or `tsc --noEmit && vite build`).
- **NEVER:**
  - DO NOT run `cargo test`, `cargo check`, or Rust compiler passes.
  - DO NOT trigger full native application release builds (`tauri build`, `./build.sh`).

### B. Backend / Core Only (`src-tauri/`, `Cargo.toml`, `*.rs`)
- **Action:** Verify compiler checks and nearest unit tests only.
- **Run:** `rtk cargo check` or focused module tests (`rtk cargo test --lib <module>`).
- **NEVER:**
  - DO NOT run frontend test suites (`npm test`, UI linting) unless IPC contracts or serialized models changed.
  - DO NOT run consecutive full release builds locally.

### C. Documentation & Metadata Only (`*.md`, `.github/`, `.gitignore`, `LICENSE`)
- **Action:** Zero compilation needed.
- **Run:** Lint or schema checks only if applicable.
- **NEVER:**
  - DO NOT run test suites or builds for prose/documentation changes.

### D. Full-Stack / IPC Boundary (Both Frontend & Backend touched, or Tauri Commands altered)
- **Action:** Verify both layers incrementally, starting with fastest checks.
  1. `rtk cargo check` (fast Rust type validation).
  2. `tsc --noEmit` (fast TypeScript interface validation).
  3. Run only integration or contract tests that cover the altered IPC boundary.

---

## 2. Resource & Thermal Preservation Guardrails

1. **Incremental Over Release:**
   - In day-to-day development, never run full release compilation (e.g. LTO passes, stripping, bundling) merely to test code.
   - Prefer incremental dev builds (`cargo check`, `npm run build:fast`, `npm run dev`).
2. **Nearest-Gate Principle:**
   - Run the single nearest test file or module covering the altered logic.
   - If that test passes, and the change has no ripple effects, stop there.
3. **No Redundant Passes:**
   - If a file was checked and unchanged since the last pass, never re-run the same check in the same turn.
