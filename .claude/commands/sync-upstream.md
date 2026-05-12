---
description: Pull upstream changes from origin/main into dev-llm-implementation
---

Sync procedure. Run only on a clean working tree.

**Current topology:** there is no separate `upstream` remote; `origin` (`open-energy-transition/pypsa-app`) acts as upstream. When the original `PyPSA/pypsa-app` remote is added in the future, this procedure will need to fetch from `upstream` and merge into `main` first.

Steps:

1. Confirm a clean tree:
   ```
   git status --porcelain
   ```
   Must be empty. If not, abort and ask the user.

2. Update `main` from origin (fast-forward only — never let `main` diverge):
   ```
   git fetch origin
   git checkout main
   git pull --ff-only origin main
   ```

3. Merge `main` into `dev-llm-implementation`:
   ```
   git checkout dev-llm-implementation
   git merge --no-ff main -m "chore: sync from main"
   ```
   `.claude/` should survive untouched because it only exists on this branch.

4. Verify Category A paths (see `.claude/project/main-pr-strategy.md`) did NOT get introduced on `main`:
   ```
   git ls-tree main -- .claude .sandcastle CLAUDE.md AGENTS.md
   ```
   Output must be empty. If not, revert the offending commit on `main` before pushing.

5. Push:
   ```
   git push origin dev-llm-implementation
   ```

6. Report the merged commit range to the user so they know what upstream work is now in dev.
