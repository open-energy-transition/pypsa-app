# Issue workflow

Each issue transits through this lifecycle. The Status field on the GH Project is the source of truth — the issue's open/closed state is just a side-effect.

## States

| Status | Entry trigger | Exit trigger |
|---|---|---|
| Backlog | Issue created | Scoped + accepted into a sprint |
| Ready | Assigned a Sprint | Someone starts work |
| In Progress | Branch created from `dev-llm-implementation` | PR opened |
| In Review | PR opened against `dev-llm-implementation` | PR merged / closed |
| Blocked | Depends on external thing | Dependency resolved |
| Done | PR merged + issue manually closed (see *Shipping an issue*) | — |

## Setting status via GraphQL

Field and option IDs are in `.claude/project/github-project.md`. Template:

```
gh api graphql -f query="mutation {
  updateProjectV2ItemFieldValue(input: {
    projectId: \"PVT_kwDOB88FCc4BVUZi\"
    itemId: \"<ITEM_ID>\"
    fieldId: \"PVTSSF_lADOB88FCc4BVUZizhQw_-E\"
    value: { singleSelectOptionId: \"<OPTION_ID>\" }
  }) { projectV2Item { id } }
}"
```

Get the project item id from the issue number:

```
N=6    # issue number
gh api graphql -f query="query { repository(owner: \"open-energy-transition\", name: \"pypsa-app\") { issue(number: $N) { projectItems(first: 5) { nodes { id project { number } } } } } }" \
  --jq '.data.repository.issue.projectItems.nodes[] | select(.project.number == 73) | .id'
```

## Picking up an issue

1. Check the Sprint view; pick a P1 item in `Ready`/`Backlog`.
2. Create the branch: `git checkout -b <type>/<task-name>` off `dev-llm-implementation`.
3. Set Status = `In Progress` (option id `fab25e10`).
4. Optionally self-assign: `gh issue edit <N> --add-assignee @me`.

## Shipping an issue

1. Make sure tests/type-checks pass locally; run pre-commit.
2. Push the branch, open a PR against `dev-llm-implementation` with `Closes #<N>` in the body.
3. Set Status = `In Review` (option id `4f2e3ecb`).
4. Request review (or self-merge for solo work — team norms TBD).
5. After merge:
   - **Manually close the linked issue** — `gh issue close <N> --reason completed`. The `Closes #N` keyword only auto-closes issues when the PR's base is the repository's *default branch* (`main`). PRs merged into `dev-llm-implementation` do not trigger auto-close.
   - Set Status = `Done` on the project item (option id `7844fc97`).

## Blocking

Set Status = `Blocked` (option id `2b60f3e1`) and add a comment on the issue explaining the dependency. Unblock by flipping back to the previous status when the dependency clears.

## Scoping out / wontfix

For an issue that won't ship:

1. `gh issue close <N> --reason "not planned"` — marks the issue closed with the *not planned* state-reason (distinct from a normal "completed" close).
2. Remove it from the project board so it doesn't linger in active views — use `deleteProjectV2Item` (see `github-project.md` → *Useful project-item mutations*). The issue itself stays on the repo for history.

Setting Status = `Done` for a not-planned issue is misleading — the board's Done column should mean shipped, not abandoned.
