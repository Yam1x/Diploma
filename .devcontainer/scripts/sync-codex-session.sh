#!/usr/bin/env bash
set -euo pipefail

target_cwd="${1:-/workspaces/Diploma}"
host_codex="/mnt/host-codex"
local_codex="/root/.codex"

sync_file() {
  local rel="$1"
  local src="$host_codex/$rel"
  local dst="$local_codex/$rel"

  if [ -f "$src" ]; then
    mkdir -p "$(dirname "$dst")"
    cp -f "$src" "$dst"
  fi
}

sync_dir() {
  local rel="$1"
  local src="$host_codex/$rel"
  local dst="$local_codex/$rel"

  if [ -d "$src" ]; then
    mkdir -p "$dst"
    cp -a "$src/." "$dst/"
  fi
}

rewrite_paths_in_file() {
  local file="$1"

  TARGET_CWD="$target_cwd" perl -0pi -e '
    s{[Cc]:/Projects/Diploma}{$ENV{TARGET_CWD}}g;
    s{[Cc]:\\\\Projects\\\\Diploma}{$ENV{TARGET_CWD}}g;
    s{C:/Users/rychk/.codex/worktrees/[^/]+/Diploma}{$ENV{TARGET_CWD}}g;
    s{C:\\\\Users\\\\rychk\\\\\\.codex\\\\worktrees\\\\[^\\\\]+\\\\Diploma}{$ENV{TARGET_CWD}}g;
  ' "$file"
}

if [ ! -d "$host_codex" ]; then
  echo "Expected host Codex mount at $host_codex" >&2
  exit 1
fi

mkdir -p "$local_codex"
sync_file "auth.json"
sync_file "config.toml"
sync_file "cap_sid"
sync_file "session_index.jsonl"
sync_dir "sessions"
sync_dir "archived_sessions"

if [ -f "$local_codex/session_index.jsonl" ]; then
  rewrite_paths_in_file "$local_codex/session_index.jsonl"
fi

if [ -d "$local_codex/sessions" ]; then
  while IFS= read -r -d '' file; do
    rewrite_paths_in_file "$file"
  done < <(find "$local_codex/sessions" -type f -name '*.jsonl' -print0)
fi

if [ -d "$local_codex/archived_sessions" ]; then
  while IFS= read -r -d '' file; do
    rewrite_paths_in_file "$file"
  done < <(find "$local_codex/archived_sessions" -type f -name '*.jsonl' -print0)
fi

echo "Synced Codex session data into $local_codex using cwd $target_cwd"
