# Changelog

All notable changes to this fork are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **LLM chat MVP (read-only).** New `src/pypsa_app/llm/` module exposes `POST /api/v1/chat`, gated behind the `CHAT_ENABLED` feature flag and authenticated by an active user. The chat endpoint runs a tool-use loop via [LiteLLM](https://github.com/BerriAI/litellm) against any OpenAI-compatible provider (Ollama, llama.cpp, OpenRouter, api.openai.com, etc.) selected by `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_API_BASE`. Tool exceptions are surfaced as error blocks instead of HTTP 500s; on hitting `LLM_MAX_TOOL_ITERATIONS` (default 8) the loop soft-stops with `truncated: true` so the client can offer a "continue" affordance. Three read-only tools auto-discovered from `src/pypsa_app/llm/tools/`:
  - `list_networks` — paginated list of the caller's visible networks (`offset` / `limit` / `sort_by` / `order`) with a field whitelist safe for LLM context.
  - `get_network_detail` — structured summary of one network from DB-cached metadata only (never opens the NetCDF). Unknown or non-visible ids return `{error: "network_not_found"}` so private networks are not leaked.
  - `get_network_statistics` — read-only statistic over a network using the existing allowlisted statistics service.
- **Backend supporting changes.** `chat_enabled` flag on `GET /api/v1/version`, sort/order query params on `GET /api/v1/networks`, JSON 404 for unmatched `/api/v1/*` paths (so the SPA shell does not leak HTML to API clients), Alembic advisory lock for concurrent migrations, and the `fom` statistic added to the allowlist.
- **Chat UI.** SvelteKit chat panel (FAB → modal) renders user/assistant messages, tool calls, and tool results, with custom renderers for network lists, network cards, statistics, JSON payloads, and charts. Built on a curated subset of [AI Elements](https://github.com/vercel/ai/tree/main/packages/ai-elements) primitives.

([#1](https://github.com/open-energy-transition/pypsa-app/issues/1), [#3](https://github.com/open-energy-transition/pypsa-app/issues/3), [#4](https://github.com/open-energy-transition/pypsa-app/issues/4), [#6](https://github.com/open-energy-transition/pypsa-app/issues/6))

[Unreleased]: https://github.com/open-energy-transition/pypsa-app/compare/v0.0.1...HEAD
