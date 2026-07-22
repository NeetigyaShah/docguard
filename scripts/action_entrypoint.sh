#!/bin/sh
# Map GitHub Action inputs (INPUT_*) to DocGuard env, then run the action.
set -e

export DOCGUARD_LLM_PROVIDER="${INPUT_LLM_PROVIDER:-mock}"
export DOCGUARD_EMBEDDING_PROVIDER="${INPUT_EMBEDDING_PROVIDER:-mock}"
export DOCGUARD_HIGH_CONFIDENCE="${INPUT_CONFIDENCE_THRESHOLD:-0.85}"
export DOCGUARD_AUTO_FIX="${INPUT_AUTO_FIX:-false}"
export DOCGUARD_DOCS_PATHS="${INPUT_DOCS_PATHS:-docs}"
export DOCGUARD_SRC_PATHS="${INPUT_SRC_PATHS:-src}"

# Diff base: explicit input, else the PR base sha, else previous commit.
BASE="${INPUT_BASE:-${GITHUB_BASE_REF:-HEAD~1}}"

# GitHub checks out a detached HEAD; make base refs resolvable.
git config --global --add safe.directory "${GITHUB_WORKSPACE:-$PWD}" || true

exec docguard action --repo "${GITHUB_WORKSPACE:-.}" --base "$BASE"
