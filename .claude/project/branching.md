# Branching

## Layout

```
upstream:PyPSA/pypsa-app  (not yet configured as a remote — TBD)
   │
   ▼
origin:open-energy-transition/pypsa-app  (origin; acts as upstream for now)
   │
   ▼
main                      ← tracks origin/main; keep clean, no .claude/, no OET-specific commits
   │
   ▼
dev-llm-implementation    ← integration branch; .claude/ lives here; feature branches merge here
   │
   ▼
feat/<task>               ← one-task-per-branch; named after the concrete task, not a plan step
```

## Non-negotiable rules

1. **One task = one branch = one PR = one issue.** Never bundle unrelated tasks even if they share a plan "step".
2. **Always branch from `dev-llm-implementation`**, never from `main`. `.claude/` won't exist on a branch cut from `main`.
3. **Branch-name format:** `<type>/<kebab-case-task>` — e.g. `feat/chat-endpoint`, `fix/network-cache-race`, `chore/anthropic-dep`. Match the issue's intent, not its number.
4. **Never force-push `main` or `dev-llm-implementation`.** Force-push only on your own `feat/*` branches, and only if no one has pulled.

## Starting a task

```
git fetch origin
git checkout dev-llm-implementation
git pull --ff-only
git checkout -b <type>/<task-name>
```

Then mark the issue `Status = In Progress` (see `issue-workflow.md`).

## Upstream sync (when upstream moves)

See `.claude/commands/sync-upstream.md` for the full procedure.

Short version:
```
git checkout main
git pull --ff-only origin main
git checkout dev-llm-implementation
git merge main       # no .claude/ conflicts because .claude/ isn't on main
git push origin dev-llm-implementation
```

If the `.claude/` folder ever appears on `main`, it was committed by mistake — revert immediately.
