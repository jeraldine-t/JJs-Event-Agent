#!/usr/bin/env bash
# LaunchAgent entry point: run once daily after 8 AM SGT when this Mac is online.
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
state_dir=${JJS_PRIVATE_STATE_DIR:-"$HOME/.local/share/jjs-event-agent"}
stamp_path="$state_dir/last-successful-refresh-date"
today=$(TZ=Asia/Singapore date +%F)
hour=$(TZ=Asia/Singapore date +%H)

if (( 10#$hour < 8 )); then
  exit 0
fi
if [[ -f "$stamp_path" && "$(<"$stamp_path")" == "$today" ]]; then
  exit 0
fi
if ! curl --fail --silent --show-error --max-time 12 https://luma.com/ >/dev/null; then
  exit 0
fi

"$repo_dir/scripts/private-refresh.sh"
mkdir -p "$state_dir"
printf '%s\n' "$today" >"$stamp_path"
