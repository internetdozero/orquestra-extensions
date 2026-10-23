# AGENTS.md

file_size_cap: 400
file_size_soft: 300

Those two lines are the size rule. Count with `wc -l`. A hand-written file at the soft number gets no new behavior; split it first. A file over the cap is a broken tree. Generated files, lockfiles, and vendored code are outside the cap.

## What this is

<one sentence>

## Layout

Group by capability. The entry point only wires modules. A shared module exists only after a second capability needs the same behavior.

<one line per directory: path — what it owns>

## Commands

- Check file size: `rtk bash scripts/check-file-size.sh`
- Run: not yet
- Test: not yet

## While editing

- Read this file before adding code.
- Import only a module's public surface.
- A section banner inside a file means it is already two modules.
- A nested AGENTS.md is only for a subtree with different commands or a different cap. The closest file wins.
- Commit each coherent slice locally. Do not push unless asked.

## Temporary Files & Storage Policy (Strict)

- **Forbidden Path:** NEVER create or write scratch files, mock repositories, temporary test workspaces, or artifacts inside `/tmp/`. On this Linux machine, `/tmp` is a RAM-backed `tmpfs`; consuming it directly exhausts physical RAM and causes the kernel OOM Killer to crash critical user processes.
- **Designated Scratch Path:** All temporary files, scratch scripts, mock repositories, and sandbox tests MUST use `/var/tmp/testing/` (create if absent: `mkdir -p /var/tmp/testing`). Always remove transient test assets upon test completion.
