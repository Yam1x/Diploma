#!/usr/bin/env bash
set -euo pipefail

host_cwd="${1:-}"
host_codex="/mnt/host-codex"
local_codex="/root/.codex"
staging_dir="$(mktemp -d)"
staging_codex="$staging_dir/.codex"

cleanup() {
  rm -rf "$staging_dir"
}

trap cleanup EXIT

if [ -z "$host_cwd" ]; then
  echo "Usage: $0 <host-cwd>" >&2
  exit 1
fi

if [ ! -d "$host_codex" ]; then
  echo "Expected host Codex mount at $host_codex" >&2
  exit 1
fi

mkdir -p "$staging_codex"

copy_if_exists() {
  local rel="$1"
  local src="$local_codex/$rel"
  local dst="$staging_codex/$rel"

  if [ -f "$src" ]; then
    mkdir -p "$(dirname "$dst")"
    cp -f "$src" "$dst"
  fi
}

copy_dir_if_exists() {
  local rel="$1"
  local src="$local_codex/$rel"
  local dst="$staging_codex/$rel"

  if [ -d "$src" ]; then
    mkdir -p "$dst"
    cp -a "$src/." "$dst/"
  fi
}

rewrite_paths_in_file() {
  local file="$1"

  HOST_CWD="$host_cwd" perl -0pi -e '
    s{/workspaces/Diploma}{$ENV{HOST_CWD}}g;
    s{[Cc]:/Projects/Diploma}{$ENV{HOST_CWD}}g;
    s{[Cc]:\\\\Projects\\\\Diploma}{$ENV{HOST_CWD}}g;
    s{C:/Users/rychk/.codex/worktrees/[^/]+/Diploma}{$ENV{HOST_CWD}}g;
    s{C:\\\\Users\\\\rychk\\\\\\.codex\\\\worktrees\\\\[^\\\\]+\\\\Diploma}{$ENV{HOST_CWD}}g;
  ' "$file"
}

copy_if_exists "auth.json"
copy_if_exists "config.toml"
copy_if_exists "cap_sid"
copy_if_exists "session_index.jsonl"
copy_dir_if_exists "sessions"
copy_dir_if_exists "archived_sessions"

if [ -f "$staging_codex/session_index.jsonl" ]; then
  rewrite_paths_in_file "$staging_codex/session_index.jsonl"
fi

if [ -d "$staging_codex/sessions" ]; then
  while IFS= read -r -d '' file; do
    rewrite_paths_in_file "$file"
  done < <(find "$staging_codex/sessions" -type f -name '*.jsonl' -print0)
fi

if [ -d "$staging_codex/archived_sessions" ]; then
  while IFS= read -r -d '' file; do
    rewrite_paths_in_file "$file"
  done < <(find "$staging_codex/archived_sessions" -type f -name '*.jsonl' -print0)
fi

for rel in auth.json config.toml cap_sid session_index.jsonl; do
  if [ -f "$staging_codex/$rel" ]; then
    mkdir -p "$(dirname "$host_codex/$rel")"
    cp -f "$staging_codex/$rel" "$host_codex/$rel"
  fi
done

for rel in sessions archived_sessions; do
  if [ -d "$staging_codex/$rel" ]; then
    mkdir -p "$host_codex/$rel"
    cp -a "$staging_codex/$rel/." "$host_codex/$rel/"
  fi
done

echo "Synced Codex session data back to $host_codex using cwd $host_cwd"
