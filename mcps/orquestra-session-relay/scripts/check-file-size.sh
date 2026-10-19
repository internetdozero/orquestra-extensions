#!/usr/bin/env bash
# Fail when hand-written files exceed file_size_cap in the project's AGENTS.md.
set -euo pipefail

root="${1:-.}"
root=$(cd "$root" && pwd)
agents="$root/AGENTS.md"

if [[ ! -f "$agents" ]]; then
  echo "missing $agents" >&2
  exit 1
fi

cap=$(grep -E '^file_size_cap:[[:space:]]*[0-9]+' "$agents" | head -1 | grep -oE '[0-9]+' || true)
soft=$(grep -E '^file_size_soft:[[:space:]]*[0-9]+' "$agents" | head -1 | grep -oE '[0-9]+' || true)

if [[ -z "$cap" ]]; then
  echo "AGENTS.md has no file_size_cap line" >&2
  exit 1
fi

fail=0
agents_lines=$(wc -l < "$agents" | tr -d ' ')
if (( agents_lines > 100 )); then
  echo "AGENTS.md has $agents_lines lines (max 100)" >&2
  fail=1
fi

skip_path() {
  case "$1" in
    */.git/*|*/node_modules/*|*/vendor/*|*/dist/*|*/build/*|*/target/*|*/.next/*|*/out/*|*/coverage/*|*/__pycache__/*|*/.venv/*|*/venv/*)
      return 0
      ;;
  esac
  case "$1" in
    *.lock|*.min.js|*.min.css|*.map|*.svg|*.png|*.jpg|*.jpeg|*.gif|*.webp|*.ico|*.woff|*.woff2|*.pdf|*.sum)
      return 0
      ;;
  esac
  base=$(basename "$1")
  case "$base" in
    package-lock.json|yarn.lock|pnpm-lock.yaml|Cargo.lock|go.sum|poetry.lock|composer.lock|Gemfile.lock|bun.lock|bun.lockb)
      return 0
      ;;
  esac
  return 1
}

if git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  mapfile -t files < <(git -C "$root" ls-files -co --exclude-standard)
else
  mapfile -t files < <(cd "$root" && find . -type f ! -path './.git/*')
fi

for rel in "${files[@]}"; do
  rel=${rel#./}
  [[ -z "$rel" ]] && continue
  skip_path "$rel" && continue
  path="$root/$rel"
  [[ -f "$path" ]] || continue
  # Bash cannot hold a NUL, so detect a binary file by grep treating it as one.
  if [[ -s "$path" ]] && ! LC_ALL=C grep -I -q . "$path"; then
    continue
  fi
  lines=$(wc -l < "$path" | tr -d ' ')
  if [[ "$rel" == "AGENTS.md" ]]; then
    continue
  fi
  if (( lines > cap )); then
    echo "$rel has $lines lines (cap $cap)" >&2
    fail=1
  elif [[ -n "$soft" ]] && (( lines >= soft )); then
    echo "$rel has $lines lines (soft $soft, cap $cap)" >&2
  fi
done

exit "$fail"
