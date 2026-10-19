---
name: orquestra-modular-start
description: Mandatory when starting a new project, empty repository, or scaffold in any programming language. Initializes git, sets up a concise root AGENTS.md with file-size caps and module map, and commits each coherent slice locally.
---

# Modular start

Run this before any source file exists. The project must be a git repo whose root `AGENTS.md` already states the size cap and the module map. A later session follows that file.

A direct instruction in the current conversation wins over this skill. Otherwise do the steps below without asking.

## Order

1. Use the directory the user named as the project root. If it already has an `AGENTS.md` with a `file_size_cap` line, follow that file and skip setup. Do not rewrite it.
2. Run `git init` when `.git` is missing. Do not change global git config. If `user.name` or `user.email` is unset, set them on this repo only, from `gh api user` (`login`, and `{id}+{login}@users.noreply.github.com`). If that fails, stop and say the commit cannot be made. Do not invent an identity.
3. Add a `.gitignore` before the first commit. Start from `assets/gitignore`. Extend it in the same commit that adds the tool files for this stack (dependencies, build output, secrets, local environments).
4. Copy `assets/AGENTS.md` to the project root and fill the blanks. Copy `scripts/check-file-size.sh` to the project's `scripts/check-file-size.sh`. These are the first files you write. Do not raise `file_size_cap` or `file_size_soft` unless the user gives a number. Keep `AGENTS.md` under 100 lines. It is the contract every session loads: the two cap lines, the layout, the commands. A longer note goes in one `docs/` file linked from here.
5. Add a README of at most 40 lines: what it is, how to run, how to test. Use "not yet" until a command exists, then replace it in the commit that adds the command. Mirror the real commands in `AGENTS.md`. The file-size check is `rtk bash scripts/check-file-size.sh`.
6. Commit: `chore: start repo with module rules`.
7. Only then add source.

## Shape

Group by what the program does, in the layout that language already uses. A capability owns its types, its logic, and the edge where it touches input and output. Other code imports only its public surface.

The entry point wires capabilities. It does not implement them.

Do not open one file per technical layer (`handlers`, `utils`, `helpers`, `common`, `models`, `types`) and pour the program into it. A shared module appears the second time two capabilities need the same behavior. Until then the copy stays local.

A file that needs a section banner to stay readable is already two modules. When the next edit would reach `file_size_soft`, split by reason to change in that same edit, then add the behavior. When a file is over `file_size_cap`, the next edit starts with the split.

A nested `AGENTS.md` exists only when a subtree has different commands or a different cap. Keep it shorter than the root file. The closest file wins.

Do not add a monorepo, a plugin system, or a framework the task did not ask for.

## Commits

Commit locally after the skeleton and after each coherent slice (one capability, one behavior, or the split the cap required). Do not wait until the end, and do not ask permission for these local commits.

Use an imperative message: `feat:`, `fix:`, or `chore:`, then what changed.

Do not commit secrets, credentials, or generated binaries. Do not push, force-push, or skip hooks. If a hook rejects the commit, fix the cause and commit again.

## Check

```bash
rtk bash scripts/check-file-size.sh
```

Run the project's copy before saying the project is started and before saying a slice is done. The tree for that slice is committed. `file_size_cap` in the project's `AGENTS.md` is the number the checker enforces. Generated files, lockfiles, and vendored trees are outside the cap.

On a later session, read the root `AGENTS.md` before editing. New code follows its cap. Split a file that is already over the cap when you touch it. Do not restructure the rest of the tree unasked.
