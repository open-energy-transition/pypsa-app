# Claude Code session context for pypsa-app (dev-llm-implementation)

You are assisting with the AI Integration work on the OET fork of `pypsa-app`. On every session start, read this file, then read the files in `.claude/project/` relevant to the task at hand. Do not re-read them on every turn — they are stable.

## Ground rules (non-negotiable)

1. **Branch naming: one task per branch, never by plan step.** See `.claude/project/branching.md`.
2. **Always branch from `dev-llm-implementation`, never from `main`.** `main` tracks upstream cleanly.
3. **This `.claude/` folder only exists on `dev-llm-implementation` and its derivative branches.** Never let it leak onto `main` — it will generate merge conflicts on upstream syncs.
4. **GitHub is the source of truth** for project state (sprints, priorities, statuses). Do not create local snapshot files that will drift.
5. **Conventional commits** (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`). Enforced by pre-commit.
6. **Implement first, test after — no TDD.** Write working code first, verify it manually, then write tests against the real implementation.

## What lives where

| File | Purpose |
|---|---|
| `.claude/project/github-project.md` | GH Project #73 details: IDs, fields, option IDs, ready-to-paste GraphQL snippets |
| `.claude/project/branching.md` | Branch naming rules, upstream sync procedure |
| `.claude/project/issue-workflow.md` | Pick-up → implement → PR → merge, and how each step updates the Project |
| `.claude/project/sprint-workflow.md` | How to plan, assign, and close a sprint |
| `.claude/project/main-pr-strategy.md` | Two-PR split for promotions to `main`; the curated list of "never on main" and "split into a separate PR" paths |
| `.claude/commands/pick-up.md` | `/pick-up <issue#>` — branch + mark In Progress |
| `.claude/commands/ship.md` | `/ship` — open PR, mark In Review |
| `.claude/commands/sync-upstream.md` | `/sync-upstream` — fetch from `PyPSA/pypsa-app`, fast-forward `main`, merge into `dev-llm-implementation` |

## On session start — capture current state

**Do this proactively, without being asked.** The user should never have to say "check the project status" — surfacing the current Sprint state, recently merged PRs, and the next Ready issue is part of orienting at session start. Report it as part of the opening turn whenever the user asks anything about "what's next", project state, or exploration.

**Always `git fetch` first and cross-check the remote — local-only state is stale by default.** PR approval and merge happen on GitHub, not locally, so:
- A squash-merged PR leaves your local task branch looking "ahead of origin" when it has in fact been merged. That stale state is expected — task branches are kept locally on purpose as a record of past work; do **not** treat them as in-flight and do **not** auto-delete them.
- After confirming the current branch's PR is merged, **switch to `dev-llm-implementation` and pull**, then wait there until the user picks the next task. Do not create a new task branch until the user agrees on which issue to pick up.

```
# Sync remote refs FIRST — never report state from local-only data
git fetch origin

# What's my current branch, what's on origin, what's been merged recently?
git status
git log --oneline origin/dev-llm-implementation..HEAD       # commits not yet on remote dev branch
git log --oneline dev-llm-implementation..origin/dev-llm-implementation  # commits the local dev branch is missing
gh pr list --state merged --limit 5 --json number,title,mergedAt,headRefName,baseRefName
gh issue list --state closed --limit 5 --json number,title,closedAt

# What's currently in the active sprint? (re-run every session — don't trust prior snapshots)
gh api graphql -f query='query {
  node(id: "PVT_kwDOB88FCc4BVUZi") {
    ... on ProjectV2 {
      items(first: 30) {
        nodes {
          content { ... on Issue { number title state url } }
          status: fieldValueByName(name: "Status") { ... on ProjectV2ItemFieldSingleSelectValue { name } }
          priority: fieldValueByName(name: "Priority") { ... on ProjectV2ItemFieldSingleSelectValue { name } }
          estimate: fieldValueByName(name: "Estimate") { ... on ProjectV2ItemFieldNumberValue { number } }
          sprint: fieldValueByName(name: "Sprint") { ... on ProjectV2ItemFieldIterationValue { title } }
        }
      }
    }
  }
}' --jq '.data.node.items.nodes[] | select(.sprint.title == "Sprint 1") | [.content.number, .status.name, .priority.name, .estimate.number, .content.title] | @tsv' | sort -n
```

## On task completion — update state

When you finish a task, before reporting success:

1. **Verify** the code compiles / tests pass (don't claim success without evidence).
2. **Create a PR** against `dev-llm-implementation` linking the issue (`Closes #N`).
3. **Update the Project item** to `Status = In Review` (see `.claude/project/issue-workflow.md` for the GraphQL snippet).
4. **Do not mark the GitHub issue "closed"** — that happens automatically when the PR merges.

## What not to do

- Don't create planning/summary `.md` files in the repo. Keep private notes outside the repo (`~/projects/oet/pypsa-app-private-notes/` for this user).
- Don't reference `.claude/` from upstream-tracked paths (README, etc.).
- Don't hardcode secrets. `ANTHROPIC_API_KEY` comes from env.
- Don't bundle unrelated fixes into a task branch. One task = one branch = one PR.
