---
description: Start work on a GH issue — branch from dev-llm-implementation and mark In Progress
argument-hint: <issue-number> [branch-name]
---

You are starting work on issue #$1 in the `open-energy-transition/pypsa-app` repo. If a second argument is provided, use it as the branch name; otherwise propose a branch name based on the issue title and ask the user to confirm.

Steps (do not skip any):

1. Fetch the issue so you understand the scope:
   ```
   gh issue view $1 -R open-energy-transition/pypsa-app
   ```

2. Verify you're on `dev-llm-implementation` with a clean tree:
   ```
   git fetch origin
   git checkout dev-llm-implementation
   git pull --ff-only
   git status
   ```

3. Create the branch (branch name must match the convention in `.claude/project/branching.md` — `<type>/<kebab-task>`, one task only, never named by plan step):
   ```
   git checkout -b <branch-name>
   ```

4. Resolve the project item id for the issue and set its Status to "In Progress":
   ```
   ITEM=$(gh api graphql -f query='query { repository(owner: "open-energy-transition", name: "pypsa-app") { issue(number: '"$1"') { projectItems(first: 5) { nodes { id project { number } } } } } }' --jq '.data.repository.issue.projectItems.nodes[] | select(.project.number == 73) | .id')
   gh api graphql -f query='mutation { updateProjectV2ItemFieldValue(input: { projectId: "PVT_kwDOB88FCc4BVUZi", itemId: "'"$ITEM"'", fieldId: "PVTSSF_lADOB88FCc4BVUZizhQw_-E", value: { singleSelectOptionId: "fab25e10" } }) { projectV2Item { id } } }'
   ```

5. Before starting code, confirm understanding of the issue's Acceptance section with the user. If it mentions tests, plan the test-first approach.

6. Announce ready to start implementation.

Do NOT push the branch yet. Pushing happens when you open a PR (see `/ship`).
