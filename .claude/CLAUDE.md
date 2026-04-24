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
| `.claude/commands/pick-up.md` | `/pick-up <issue#>` — branch + mark In Progress |
| `.claude/commands/ship.md` | `/ship` — open PR, mark In Review |
| `.claude/commands/sync-upstream.md` | `/sync-upstream` — fetch from `PyPSA/pypsa-app`, fast-forward `main`, merge into `dev-llm-implementation` |

## On session start — capture current state

Before proposing work, check:

```
# What's my current branch, what's ahead of dev-llm-implementation?
git status && git log --oneline dev-llm-implementation..HEAD

# What's currently in the active sprint?
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
