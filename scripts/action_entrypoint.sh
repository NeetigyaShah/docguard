#!/bin/sh
# Map GitHub Action inputs (INPUT_*) to DocGuard env, then run the action.
set -e

export DOCGUARD_LLM_PROVIDER="${INPUT_LLM_PROVIDER:-mock}"
export DOCGUARD_EMBEDDING_PROVIDER="${INPUT_EMBEDDING_PROVIDER:-mock}"
export DOCGUARD_HIGH_CONFIDENCE="${INPUT_CONFIDENCE_THRESHOLD:-0.85}"
export DOCGUARD_AUTO_FIX="${INPUT_AUTO_FIX:-false}"
export DOCGUARD_DOCS_PATHS="${INPUT_DOCS_PATHS:-docs}"
export DOCGUARD_SRC_PATHS="${INPUT_SRC_PATHS:-src}"

# `github-token` input wins; otherwise inherit a GITHUB_TOKEN set via `env:`.
if [ -n "${INPUT_GITHUB_TOKEN}" ]; then
  export GITHUB_TOKEN="${INPUT_GITHUB_TOKEN}"
fi

WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
# GitHub checks out a detached HEAD owned by a different uid; make git trust it.
git config --global --add safe.directory "${WORKSPACE}" || true

# Resolve the diff base to something that actually exists in this checkout.
# On pull_request, GITHUB_BASE_REF is a bare branch name ("main") which is only a
# local ref if it was fetched -- with actions/checkout it normally exists as
# origin/main. Probe candidates in order and fall back to the previous commit.
resolve_base() {
  for c in "$@"; do
    [ -n "$c" ] || continue
    if git -C "${WORKSPACE}" rev-parse --verify --quiet "$c^{commit}" >/dev/null 2>&1; then
      echo "$c"
      return 0
    fi
  done
  echo "HEAD~1"
}

if [ -n "${INPUT_BASE}" ]; then
  BASE=$(resolve_base "${INPUT_BASE}" "origin/${INPUT_BASE}")
elif [ -n "${GITHUB_BASE_REF}" ]; then
  # merge-base keeps the diff to what THIS PR changed, not everything on main since.
  CAND=$(resolve_base "origin/${GITHUB_BASE_REF}" "${GITHUB_BASE_REF}")
  MB=$(git -C "${WORKSPACE}" merge-base "${CAND}" HEAD 2>/dev/null || true)
  BASE="${MB:-$CAND}"
else
  BASE="HEAD~1"
fi

echo "DocGuard: diffing against base '${BASE}'"
exec docguard action --repo "${WORKSPACE}" --base "${BASE}"
