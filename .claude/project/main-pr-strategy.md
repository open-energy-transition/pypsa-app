# Promoting `dev-llm-implementation` → `main`

Two distinct categories of paths get special handling when opening a PR against `main`. Keep the lists below in sync with reality before every promotion PR (see *Audit* at the bottom).

## Category A — Never on `main` (hard rule)

These exist only on `dev-llm-implementation` and derivative branches. They give an LLM assistant project context but are noise for everyone else.

| Path | Reason |
|---|---|
| `.claude/` | AI-assistant project context, commands, specs |
| `.sandcastle/` | Sandcastle agent scratch space |
| `CLAUDE.md` (root) | Top-level AI-assistant instructions |
| `AGENTS.md` (root) | Top-level AI-agent instructions |

Defensive backstop: `.claude` is already in `.gitignore`. Re-adding any of these by accident will not error, so the discipline matters more than the gitignore.

The `sync-upstream.md` command verifies `.claude/` is absent on `main` after every upstream sync; extend that check if you add categories here.

### Git pathspec (copy-pasteable)

```
':(exclude).claude/**'
':(exclude).sandcastle/**'
':(exclude)CLAUDE.md'
':(exclude)AGENTS.md'
```

## Category B — Split into a separate PR (visual-clutter rule)

These belong on `main` (deterministic builds need lockfiles; CI on `main` needs tests) but inflate the diff and make code review harder. **Open two stacked PRs**: the first ships only the real codebase, the second adds the surrounding files.

| Path | Reason |
|---|---|
| `tests/**` | Test suites (Python pytest, e2e harness) |
| `**/*.test.{ts,tsx,js,jsx}` | Vitest co-located component tests |
| `**/*.spec.{ts,tsx,js,jsx}` | Playwright / other co-located specs |
| `**/vitest.config.{ts,js}` | Vitest tooling config |
| `uv.lock` | Python deps lock |
| `package-lock.json` (root) | npm lock at repo root |
| `frontend/app/package-lock.json` | npm lock for the frontend SPA |

### Git pathspec (copy-pasteable)

```
':(exclude)tests/**'
':(exclude)**/*.test.ts' ':(exclude)**/*.test.tsx' ':(exclude)**/*.test.js' ':(exclude)**/*.test.jsx'
':(exclude)**/*.spec.ts' ':(exclude)**/*.spec.tsx' ':(exclude)**/*.spec.js' ':(exclude)**/*.spec.jsx'
':(exclude)**/vitest.config.ts' ':(exclude)**/vitest.config.js'
':(exclude)uv.lock'
':(exclude)package-lock.json'
':(exclude)frontend/app/package-lock.json'
```

## The two-PR split — workflow

When `dev-llm-implementation` is ready to promote to `main`:

1. **PR 1 — "Codebase"**
   - Branch from `main`. Apply files from `dev-llm-implementation` excluding **both** Category A and Category B.
   - Reviewers see only production code, configs, and user-facing docs.

2. **PR 2 — "Tests + lockfiles"** (stacked on PR 1)
   - From PR 1's branch, apply the Category B paths from `dev-llm-implementation`.
   - Lands tests and lockfiles aligned with the code from PR 1.
   - Reviewers can collapse this PR's diff with `?w=1&hide=lockfiles` or just glance at file paths.

Recipe (run on a fresh clone or worktree from `main`):

```
git fetch origin
git checkout -b promote/codebase main

# PR 1 source set = everything on dev except Category A and B
git ls-tree -r dev-llm-implementation --name-only \
  | grep -vE '^(\.claude/|\.sandcastle/|CLAUDE\.md$|AGENTS\.md$)' \
  | grep -vE '^tests/' \
  | grep -vE '\.test\.(ts|tsx|js|jsx)$' \
  | grep -vE '\.spec\.(ts|tsx|js|jsx)$' \
  | grep -vE '(^|/)vitest\.config\.(ts|js)$' \
  | grep -vE '^(uv\.lock|package-lock\.json|frontend/app/package-lock\.json)$' \
  > /tmp/codebase-paths.txt
xargs -a /tmp/codebase-paths.txt git checkout dev-llm-implementation --
git commit -m "feat: promote codebase from dev-llm-implementation"
git push -u origin promote/codebase
# Open PR 1 against main

# PR 2 stacks on top, adds tests + lockfiles
git checkout -b promote/tests-and-locks promote/codebase
git checkout dev-llm-implementation -- tests/ uv.lock package-lock.json frontend/app/package-lock.json
# Plus co-located *.test.* files:
git ls-tree -r dev-llm-implementation --name-only | grep -E '\.test\.(ts|tsx|js|jsx)$' \
  | xargs -r git checkout dev-llm-implementation --
git commit -m "test+deps: bring tests and lockfiles aligned with the codebase PR"
git push -u origin promote/tests-and-locks
# Open PR 2 against main, base = promote/codebase (retargets to main once PR 1 merges)
```

## Audit — before every main PR

Run this before promoting to catch new file types that should be in one of the lists above:

```
# What's NEW on dev-llm-implementation that main has never seen?
git fetch origin
git diff --name-only origin/main..origin/dev-llm-implementation \
  | grep -vE '^(\.claude/|\.sandcastle/|tests/|CLAUDE\.md$|AGENTS\.md$)' \
  | grep -vE '\.(test|spec)\.(ts|tsx|js|jsx)$' \
  | grep -vE '(^|/)vitest\.config\.(ts|js)$' \
  | grep -vE '^(uv\.lock|package-lock\.json|frontend/app/package-lock\.json)$'
```

Anything that comes out should be inspected:

- A new generated artifact (e.g. snapshot files, fixtures over a size threshold) → consider adding to Category B.
- A new AI/agent config (e.g. a new `.cursor/`, `.opencode/`, `MEMORY.md`) → add to Category A.
- A new dependency lock (e.g. `pnpm-lock.yaml`, `poetry.lock`) → add to Category B.
- Anything else → it belongs in the codebase PR, no action needed.

Update both the table and the pathspec snippets in this file when you add anything.
