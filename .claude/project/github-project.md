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

Current as of 2026-04-21:

| Sprint | ID | Dates |
|---|---|---|
| Sprint 1 (current) | `9afed504` | Apr 21 – May 4, 2026 |
| Sprint 2 (planned) | `09bf05b9` | May 5 – May 18, 2026 |
| Sprint 3 (planned) | `29859a5e` | May 19 – Jun 1, 2026 |

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
