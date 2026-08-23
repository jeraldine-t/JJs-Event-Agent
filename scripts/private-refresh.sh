#!/usr/bin/env bash
# Run on the user's Mac only. It never reads private queues into Git or GitHub.
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ingest_command=${JJS_PRIVATE_INGEST_COMMAND:?Set JJS_PRIVATE_INGEST_COMMAND to the local plugin queue refresher}
python_bin="$repo_dir/.venv/bin/python"

"$ingest_command"

backup_path=$(mktemp)
cp "$repo_dir/index.html" "$backup_path"
trap 'rm -f "$backup_path"' EXIT

# This is the Mac-only worker. Public sources continue on the GitHub Actions
# schedule; the paired-account sources below are intentionally the only ones
# touched here.
export ENABLED_SOURCES="telegram,whatsapp"
export OUTPUT_HTML="$repo_dir/index.html"
export EMAIL_ENABLED=false
"$python_bin" -m event_agent --root "$repo_dir"

previous_count=$(grep -c 'class="event-card' "$backup_path" || true)
current_count=$(grep -c 'class="event-card' "$repo_dir/index.html" || true)
if [[ "$previous_count" -gt 0 && "$current_count" -eq 0 ]]; then
  cp "$backup_path" "$repo_dir/index.html"
fi

cd "$repo_dir"
"$python_bin" -m ruff check .
"$python_bin" -m pytest
git diff --check

if git diff --quiet -- index.html; then
  echo "Dashboard is unchanged"
  exit 0
fi

git add index.html
git commit -m "Refresh event dashboard"
git pull --rebase origin main
git push origin HEAD:main
