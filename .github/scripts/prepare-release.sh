#!/usr/bin/env bash
set -euo pipefail

version_pattern='^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
if [[ ! "$GITHUB_REF_NAME" =~ $version_pattern ]]; then
  echo "Only stable release tags in the form vMAJOR.MINOR.PATCH are published" >&2
  exit 1
fi

printf 'Release %s\n' "$GITHUB_REF_NAME"
