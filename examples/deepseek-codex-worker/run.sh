#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s WORKSPACE ASSIGNMENT_FILE\n' "$0" >&2
  exit 64
}

[[ $# -eq 2 ]] || usage
command -v codex >/dev/null 2>&1 || {
  printf 'ERROR: codex is not available on PATH\n' >&2
  exit 69
}
command -v git >/dev/null 2>&1 || {
  printf 'ERROR: git is not available on PATH\n' >&2
  exit 69
}
[[ -n "${DEEPSEEK_API_KEY:-}" ]] || {
  printf 'ERROR: DEEPSEEK_API_KEY is required\n' >&2
  exit 64
}

workspace_input=$1
assignment_input=$2
[[ -d "$workspace_input" ]] || {
  printf 'ERROR: workspace is not a directory\n' >&2
  exit 66
}
[[ -f "$assignment_input" ]] || {
  printf 'ERROR: assignment file does not exist\n' >&2
  exit 66
}

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
workspace=$(cd -- "$workspace_input" && pwd -P)
if ! git -C "$workspace" rev-parse --show-toplevel >/dev/null 2>&1; then
  printf 'ERROR: workspace must be inside a Git repository\n' >&2
  exit 66
fi
assignment_dir=$(cd -- "$(dirname -- "$assignment_input")" && pwd -P)
assignment_file="$assignment_dir/$(basename -- "$assignment_input")"
codex_bin=$(command -v codex)

cleanup_profile=false
if [[ -n "${KLP_CODEX_HOME:-}" ]]; then
  profile_dir=$KLP_CODEX_HOME
  mkdir -p -- "$profile_dir"
else
  profile_dir=$(mktemp -d "${TMPDIR:-/tmp}/klp-deepseek-codex.XXXXXX")
  cleanup_profile=true
fi

cleanup() {
  if [[ "$cleanup_profile" == true ]]; then
    rm -r -- "$profile_dir"
  fi
}
trap cleanup EXIT

install -m 600 "$script_dir/config.toml.example" "$profile_dir/config.toml"
install -m 600 "$script_dir/instructions.md" "$profile_dir/instructions.md"

toml_workspace=${workspace//\\/\\\\}
toml_workspace=${toml_workspace//\"/\\\"}
printf '\n[projects."%s"]\ntrust_level = "trusted"\n' "$toml_workspace" \
  >> "$profile_dir/config.toml"

set +e
env -i \
  HOME="${HOME:-$workspace}" \
  PATH="$PATH" \
  LANG="${LANG:-C.UTF-8}" \
  CODEX_HOME="$profile_dir" \
  DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" \
  "$codex_bin" exec --strict-config --ephemeral -C "$workspace" - \
  < "$assignment_file"
status=$?
set -e
exit "$status"
