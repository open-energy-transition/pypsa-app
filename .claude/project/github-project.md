# GitHub Project reference

**Project:** PyPSA-App AI Integration (private) · https://github.com/orgs/open-energy-transition/projects/73

## Node IDs (stable — do not duplicate these elsewhere)

| Entity | ID |
|---|---|
| Project | `PVT_kwDOB88FCc4BVUZi` |
| OET org | `O_kgDOB88FCQ` |
| `open-energy-transition/pypsa-app` repo | `R_kgDOSI2vXw` |

## Fields

| Field | Node ID | Type |
|---|---|---|
| Status | `PVTSSF_lADOB88FCc4BVUZizhQw_-E` | SINGLE_SELECT |
| Priority | `PVTSSF_lADOB88FCc4BVUZizhQxA1Q` | SINGLE_SELECT |
| Estimate | `PVTF_lADOB88FCc4BVUZizhQxA1U` | NUMBER |
| Sprint | `PVTIF_lADOB88FCc4BVUZizhQxA1Y` | ITERATION |

### Status option IDs

| Option | ID |
|---|---|
| Backlog | `f0dc12f3` |
| Ready | `47989c9d` |
| In Progress | `fab25e10` |
| In Review | `4f2e3ecb` |
| Blocked | `2b60f3e1` |
| Done | `7844fc97` |

### Priority option IDs

| Option | ID |
|---|---|
| P0 | `a80c3ef3` |
| P1 | `abee5ab2` |
| P2 | `bbb483d8` |
| P3 | `26b67a18` |

### Sprint iteration IDs

Fetch fresh when needed — new iterations get generated; list at:

```
gh api graphql -f query='query { node(id: "PVTIF_lADOB88FCc4BVUZizhQxA1Y") { ... on ProjectV2IterationField { configuration { iterations { id title startDate } } } } }'
```

Current as of 2026-05-12:

| Sprint | ID | Dates |
|---|---|---|
| Sprint 1 (archived) | `9afed504` | Apr 21 – May 4, 2026 |
| Sprint 2 (current) | `09bf05b9` | May 5 – May 18, 2026 |
| Sprint 3 (planned) | `29859a5e` | May 19 – Jun 1, 2026 |

Past iterations drop out of the live `iterations` array once they end; only current + upcoming are returned. Use `completedIterations { ... }` on the `IterationFieldConfiguration` if you need archived IDs.

## Views

| View | URL | Purpose |
|---|---|---|
| Roadmap | `/views/1` | Table, grouped by Milestone — big-picture |
| Board | `/views/2` | Kanban by Status — all items |
| Sprint | `/views/3` | Kanban filtered `sprint:@current` — daily work |
| Backlog | `/views/4` | Table filtered `status:Backlog` — grooming |

## Milestones (repo-scoped, not project-scoped)

| # | Title |
|---|---|
| 1 | M1: Read-only chat MVP |
| 2 | M2: Mutating chat via WebSocket |
| 3 | M3: Safety, approvals, and persistence |
| 4 | M4: MCP server for external clients |

## Labels (repo-scoped)

`ai-integration`, `area:backend`, `area:frontend`, `area:infra`, `area:docs` + defaults (`bug`, `documentation`, `enhancement`, `question`, `wontfix`, `duplicate`, `good first issue`, `help wanted`, `invalid`).

## Issue ↔ project-item ID map

Fetch fresh — items and issues persist, so the map is stable but long:

```
gh api graphql -f query='query { node(id: "PVT_kwDOB88FCc4BVUZi") { ... on ProjectV2 { items(first: 50) { nodes { id content { ... on Issue { number } } } } } } }' --jq '.data.node.items.nodes[] | [.content.number, .id] | @tsv' | sort -n
```

## Creating new items (for future issues)

```
# 1. Create the issue
gh issue create -R open-energy-transition/pypsa-app --title "..." --body-file ... --milestone "M1: Read-only chat MVP" --label ai-integration --label area:backend

# 2. Add to the project
ISSUE_NODE=$(gh api /repos/open-energy-transition/pypsa-app/issues/N --jq '.node_id')
gh api graphql -f query="mutation { addProjectV2ItemById(input: {projectId: \"PVT_kwDOB88FCc4BVUZi\", contentId: \"$ISSUE_NODE\"}) { item { id } } }"
```

## Useful project-item mutations

### Remove an item from the board (descope without deleting the issue)

Closed-as-not-planned issues should be removed from the board so they don't clutter active views. The issue itself stays closed on the repo.

```
gh api graphql -f query='mutation { deleteProjectV2Item(input: { projectId: "PVT_kwDOB88FCc4BVUZi", itemId: "<ITEM_ID>" }) { deletedItemId } }'
```

### Reorder items globally (default sort across all views)

`updateProjectV2ItemPosition` sets the project's default item order. Views without their own sort/group config inherit this order — including the `ROADMAP_LAYOUT` "Sprint Gantt" view. Use `afterId: null` to place an item at the top; otherwise pass the id of the item it should follow.

```
# Place ITEM at the top
gh api graphql -f query='mutation { updateProjectV2ItemPosition(input: { projectId: "PVT_kwDOB88FCc4BVUZi", itemId: "<ITEM>", afterId: null }) { items { totalCount } } }'

# Stack a list of items in a defined order
ORDER=( <item_id_1> <item_id_2> ... )
prev="null"
for item in "${ORDER[@]}"; do
  AFTER=$([ "$prev" = "null" ] && echo 'afterId:null' || echo "afterId:\"$prev\"")
  gh api graphql -f query="mutation { updateProjectV2ItemPosition(input: { projectId: \"PVT_kwDOB88FCc4BVUZi\", itemId: \"$item\", $AFTER }) { items { totalCount } } }" >/dev/null
  prev="$item"
done
```

Per-view sort settings in the UI override the project default — a view with its own sort won't respect this reordering. Check `sortByFields` / `groupByFields` on a view if items don't move where expected:

```
gh api graphql -f query='query { node(id: "<VIEW_ID>") { ... on ProjectV2View { name layout filter sortByFields(first: 5) { nodes { direction field { ... on ProjectV2FieldCommon { name } } } } groupByFields(first: 5) { nodes { ... on ProjectV2FieldCommon { name } } } } } }'
```

## Whole-board audit query

Single query returning every item with all relevant fields — useful for verifying convention consistency in one shot.

```
gh api graphql -f query='query {
  organization(login: "open-energy-transition") {
    projectV2(number: 73) {
      items(first: 50) { nodes {
        content { ... on Issue { number title state milestone { title } labels(first: 10) { nodes { name } } } }
        status:   fieldValueByName(name: "Status")   { ... on ProjectV2ItemFieldSingleSelectValue { name } }
        priority: fieldValueByName(name: "Priority") { ... on ProjectV2ItemFieldSingleSelectValue { name } }
        estimate: fieldValueByName(name: "Estimate") { ... on ProjectV2ItemFieldNumberValue { number } }
        sprint:   fieldValueByName(name: "Sprint")   { ... on ProjectV2ItemFieldIterationValue { title } }
      } }
    }
  }
}' --jq '.data.organization.projectV2.items.nodes[]
| "#\(.content.number)\t\(.content.state[0:1])\t\(.status.name // "—")\t\(.priority.name // "—")\t\(.estimate.number // "—")\t\(.sprint.title // "—")\t\(.content.milestone.title // "—")\t\(.content.title)"' \
| column -t -s$'\t' -N "ISS,ST,STATUS,P,E,SPRINT,MILESTONE,TITLE"
```
