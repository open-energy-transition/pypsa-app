# Sprint workflow

Sprints are 2-week iterations tracked by the `Sprint` iteration field on GH Project #73. The "Sprint" view (`/views/3`) is the daily standup surface.

## Creating a new sprint

Iterations are created via UI only (GraphQL for iteration creation is not exposed):

1. Go to **Settings → Sprint field** on the project.
2. Click `+ Add iteration`. Default is 2 weeks, starts the day after the previous sprint ends.
3. Click **Save**.

Then capture the new iteration's ID:

```
gh api graphql -f query='query { node(id: "PVTIF_lADOB88FCc4BVUZizhQxA1Y") { ... on ProjectV2IterationField { configuration { iterations { id title startDate } } } } }'
```

Update the table in `.claude/project/github-project.md` so future sprint-assignment commands have the IDs.

## Planning a sprint

1. Review the Backlog view; sort by Priority.
2. Pick issues whose total Estimate fits your velocity (start with 15–20 points per sprint for a solo contributor until you have real data).
3. For each picked issue, set:
   - `Sprint = <upcoming sprint iteration>`
   - `Estimate = <points>` (if not already set)
   - Optionally flip `Status = Ready`

Batch script (adjust issue numbers, points, and sprint ID):

```
ORG_PROJECT="PVT_kwDOB88FCc4BVUZi"
SPRINT_FIELD="PVTIF_lADOB88FCc4BVUZizhQxA1Y"
SPRINT_ID="<NEW_SPRINT_ID>"
ESTIMATE_FIELD="PVTF_lADOB88FCc4BVUZizhQxA1U"

declare -A POINTS=( [N1]=pts [N2]=pts ... )
for n in "${!POINTS[@]}"; do
  item=$(gh api graphql -f query="query { repository(owner: \"open-energy-transition\", name: \"pypsa-app\") { issue(number: $n) { projectItems(first: 5) { nodes { id project { number } } } } } }" \
    --jq '.data.repository.issue.projectItems.nodes[] | select(.project.number == 73) | .id')
  gh api graphql -f query="mutation {
    updateProjectV2ItemFieldValue(input: { projectId: \"$ORG_PROJECT\", itemId: \"$item\", fieldId: \"$SPRINT_FIELD\", value: { iterationId: \"$SPRINT_ID\" } }) { projectV2Item { id } }
  }" >/dev/null
  gh api graphql -f query="mutation {
    updateProjectV2ItemFieldValue(input: { projectId: \"$ORG_PROJECT\", itemId: \"$item\", fieldId: \"$ESTIMATE_FIELD\", value: { number: ${POINTS[$n]} } }) { projectV2Item { id } }
  }" >/dev/null
done
```

## During the sprint

- The `Sprint` view is the standup surface. Move cards between Status columns as work progresses.
- Nothing enters the current sprint mid-flight unless it's an emergency (P0) — add it explicitly and write a comment on the issue.

## Closing a sprint

1. Review the Sprint view: move everything that shipped to `Status = Done` and close the issue (`gh issue close <N> --reason completed`).
2. Anything unfinished: either (a) move it to next sprint (set `Sprint = <next>`) and flip `Status = Ready`, or (b) push it back to `Backlog` (clear the Sprint field). Don't leave open items tagged with the closed sprint — they break the `sprint:@current` filter.
3. Write a brief retro as a comment on a tracking issue, OR in the project README (Settings → Short description).
4. Create the next sprint iteration if it doesn't exist yet.

### Sprint rollover audit

After closing, sanity-check the board with the audit query in `github-project.md` and grep for inconsistencies:

- Any issue with `state=OPEN` and `Sprint=<closed sprint>` → roll over to the next sprint or to Backlog.
- Any closed-not-planned issue still on the board → `deleteProjectV2Item`.
- Any `Status=Ready` on an issue without a Sprint → either schedule or push to Backlog.
- Backlog issues tied to the active milestone whose work is starting → flip `Status=Ready` and set a Sprint.

## Velocity tracking

After 2–3 completed sprints, sum the points of shipped issues to get a velocity baseline. Use that (not optimism) to size the next sprint.
