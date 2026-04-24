# Changelog

All notable changes to this fork are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **AI integration — backend foundation.** Added the `anthropic` Python SDK (`>=0.96`) as a runtime dependency and exposed two optional settings for the upcoming Claude-powered chat endpoint: `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL`. Leaving `ANTHROPIC_BASE_URL` unset targets `api.anthropic.com`; setting it lets the same SDK talk to any Anthropic-compatible endpoint (e.g. OpenRouter at `https://openrouter.ai/api/v1`, or a local `llama-server`) without an abstraction layer. No client, endpoint, or model selection yet — those land in the chat-endpoint tasks. ([#1](https://github.com/open-energy-transition/pypsa-app/issues/1), [#13](https://github.com/open-energy-transition/pypsa-app/pull/13))
- **Chat MVP — plain conversation.** New `src/pypsa_app/llm/` module exposes `POST /api/v1/chat` authenticated by an active user. Accepts a message plus conversation history and returns the assistant reply via the `anthropic` SDK. Works against any Anthropic-compatible provider (Ollama, llama.cpp, OpenRouter, api.anthropic.com) by overriding `ANTHROPIC_BASE_URL`. Adds `LLM_MODEL_DEFAULT` (per-request override supported) and `LLM_THINKING_ENABLED` (off by default). No tools, streaming, or persistence yet — those land in later tasks. ([#3](https://github.com/open-energy-transition/pypsa-app/issues/3))
- **LLM tool-use loop + first tool (`list_networks`).** Chat endpoint now runs an Anthropic tool-use loop: when the model emits `tool_use`, the backend executes the registered tool and feeds the result back as `tool_result` until the model stops. Tool exceptions are surfaced as `is_error` blocks instead of HTTP 500s. On hitting `LLM_MAX_TOOL_ITERATIONS` (default 10), the loop soft-stops — one final text-only turn asks the model to summarize and the response carries `truncated: true` so the client can offer a "continue" affordance. New `src/pypsa_app/llm/tools/` package auto-discovers tools dropped into it (no registration boilerplate). First tool, `list_networks`, returns the caller's visible networks (owned + public) with paginated `offset`/`limit`/`sort_by`/`order` and a field whitelist safe for LLM context. ([#6](https://github.com/open-energy-transition/pypsa-app/issues/6))

[Unreleased]: https://github.com/open-energy-transition/pypsa-app/compare/main...dev-llm-implementation
