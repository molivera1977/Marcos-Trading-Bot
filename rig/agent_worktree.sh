#!/usr/bin/env bash
# ── AGENT WORKTREE — one checkout per agent, so concurrent agents CANNOT stage each
#    other's files (built 8/17 after the failure it prevents actually happened).
#
# THE FAILURE THIS EXISTS TO STOP (data/audits/COMMIT_RECORD_REPAIR_20260817.md)
# ------------------------------------------------------------------------------
# Two agents worked one worktree at once.  Agent X ran `git add -A` (and later a
# path-scoped `git add marcos_trading_bot.py`, which is just as fatal when the file is
# shared) and swept agent Y's IN-FLIGHT edits into X's commit.  A money-behaviour change
# — the B5 fail-open conversion — therefore landed in 460dca5 under a commit message
# that never mentions it and with NO Acceptance trailer, so GATE 5 never saw it.  A
# follow-up `--amend` then destroyed the other agent's commit message.
#
# Staging discipline cannot fix this: `marcos_trading_bot.py` is ONE path that several
# agents edit at once, so no path scope is narrow enough.  Only physical separation is.
# `git worktree` gives each agent its own checkout and its own index off a shared object
# store — agent X literally cannot see agent Y's unstaged edits.
#
# USAGE
#   rig/agent_worktree.sh create  <agent> [base]   # base defaults to HEAD
#   rig/agent_worktree.sh path    <agent>          # print the worktree path
#   rig/agent_worktree.sh status  <agent>          # git status --short inside it
#   rig/agent_worktree.sh remove  <agent>          # teardown (refuses if dirty)
#   rig/agent_worktree.sh remove  <agent> --force  # teardown, DISCARDING uncommitted work
#   rig/agent_worktree.sh list                     # every worktree this repo has
#
# `create` REFUSES when the base tree is dirty.  That is deliberate: branching off a
# dirty tree silently drops the dirt, so the agent would build against a base that
# does not match what it just read.  Commit or park the dirt first.
#
# Each agent gets branch `agent/<name>` at <base>.  Commits land in the shared object
# store immediately; the branch is merged into the mainline by whoever integrates.
set -euo pipefail

REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
ROOT="${AGENT_WORKTREE_ROOT:-${TMPDIR:-/tmp}/mtb_agent_worktrees}"

die() { echo "❌ $*" >&2; exit 1; }
wt_path() { echo "$ROOT/$1"; }

# git's index.lock is a real contention source with N agents on one object store.
git_retry() {
  local n=0
  until git -C "$REPO" "$@"; do
    n=$((n + 1)); [ "$n" -ge 5 ] && die "git $* failed after 5 attempts"
    sleep $((n * 2))
  done
}

cmd_create() {
  local agent="${1:-}"; local base="${2:-HEAD}"
  [ -n "$agent" ] || die "usage: agent_worktree.sh create <agent> [base]"
  [[ "$agent" =~ ^[A-Za-z0-9_-]+$ ]] || die "agent name must be [A-Za-z0-9_-]+ (got '$agent')"

  # ── the dirty-base refusal ──
  local dirt; dirt="$(git -C "$REPO" status --porcelain --untracked-files=no)"
  if [ -n "$dirt" ] && [ "${AGENT_WORKTREE_ALLOW_DIRTY:-}" != "1" ]; then
    echo "$dirt" >&2
    die "base tree is DIRTY (tracked files modified above).
    A worktree off a dirty tree is built against a base that does not exist in git —
    the agent would read one tree and commit against another.  Commit or park first.
    Override only if you are certain:  AGENT_WORKTREE_ALLOW_DIRTY=1"
  fi

  local sha; sha="$(git -C "$REPO" rev-parse --verify "$base^{commit}")" \
    || die "base '$base' is not a commit"
  local path; path="$(wt_path "$agent")"
  [ -e "$path" ] && die "worktree already exists: $path  (remove it first)"

  mkdir -p "$ROOT"
  git_retry worktree add -b "agent/$agent" "$path" "$sha" >/dev/null
  echo "✅ worktree for agent '$agent'"
  echo "   path:   $path"
  echo "   branch: agent/$agent"
  echo "   base:   ${sha:0:12}  ($(git -C "$REPO" log -1 --format=%s "$sha"))"
  echo
  echo "   cd $path   # do ALL of this agent's work here"
  echo "   Commits are visible to the repo immediately; merge agent/$agent when integrating."
}

cmd_path()   { local p; p="$(wt_path "${1:?agent}")"; [ -d "$p" ] || die "no worktree for '$1'"; echo "$p"; }
cmd_status() { git -C "$(cmd_path "${1:?agent}")" status --short; }

cmd_remove() {
  local agent="${1:?agent}"; local force="${2:-}"
  local path; path="$(wt_path "$agent")"
  [ -d "$path" ] || die "no worktree for '$agent'"
  local dirt; dirt="$(git -C "$path" status --porcelain --untracked-files=no)"
  if [ -n "$dirt" ] && [ "$force" != "--force" ]; then
    echo "$dirt" >&2
    die "worktree '$agent' has UNCOMMITTED work (above).  Commit it, or re-run with --force to discard."
  fi
  git_retry worktree remove ${force:+--force} "$path"
  echo "🧹 removed worktree '$agent' ($path).  Branch agent/$agent is KEPT — delete it yourself once merged."
}

cmd_list() { git -C "$REPO" worktree list; }

case "${1:-}" in
  create) shift; cmd_create "$@" ;;
  path)   shift; cmd_path   "$@" ;;
  status) shift; cmd_status "$@" ;;
  remove) shift; cmd_remove "$@" ;;
  list)   shift; cmd_list   "$@" ;;
  *) sed -n '1,40p' "${BASH_SOURCE[0]}"; exit 2 ;;
esac
