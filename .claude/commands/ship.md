---
description: Open a PR for the current task branch against dev-llm-implementation and mark the issue In Review
argument-hint: <issue-number>
---

You are finishing work on issue #$1. Before running anything, verify the code meets the issue's Acceptance criteria. Evidence before assertion — if tests exist, they must pass; if there's a dev server, it must start cleanly.

Steps:

1. Confirm branch state:
   ```
   git status
   git log --oneline dev-llm-implementation..HEAD
   ```
   If working tree isn't clean, ask the user what to do.

2. Run pre-commit on the diff:
   ```
   pre-commit run --from-ref dev-llm-implementation --to-ref HEAD
   ```
   If it fails, fix and re-commit as NEW commits (never `--amend` pushed commits).

3. Push the branch:
   ```
   git push -u origin "$(git rev-parse --abbrev-ref HEAD)"
   ```

4. Open the PR against `dev-llm-implementation` (not `main`):
   ```
   gh pr create \
     --repo open-energy-transition/pypsa-app \
     --base dev-llm-implementation \
     --title "<concise title matching issue intent>" \
     --body "$(cat <<'EOF'
   Closes #$1

   ## Summary
   <1–3 bullets on what shipped>

   ## Verification
   <how you confirmed Acceptance was met>
   EOF
   )"
   ```

5. Mark the project item Status = "In Review":
   ```
   ITEM=$(gh api graphql -f query='query { repository(owner: "open-energy-transition", name: "pypsa-app") { issue(number: '"$1"') { projectItems(first: 5) { nodes { id project { number } } } } } }' --jq '.data.repository.issue.projectItems.nodes[] | select(.project.number == 73) | .id')
   gh api graphql -f query='mutation { updateProjectV2ItemFieldValue(input: { projectId: "PVT_kwDOB88FCc4BVUZi", itemId: "'"$ITEM"'", fieldId: "PVTSSF_lADOB88FCc4BVUZizhQw_-E", value: { singleSelectOptionId: "4f2e3ecb" } }) { projectV2Item { id } } }'
   ```

6. Report the PR URL to the user.

Do NOT merge the PR. Merge is a separate, explicit step (team norms TBD).
