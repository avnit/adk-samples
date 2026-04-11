## Quick orientation — what this repo is

- This repository hosts Python sample agents built on top of the Google
  Agent Development Kit (ADK). Top-level samples live under
  `python/agents/` (e.g. `llm-auditor`, `RAG`, `wiz/wiz-mcp`). See
  `python/README.md` for a high-level map.

## Top-level architecture notes an AI helper needs to know

- Each sample agent follows the same pattern: a directory with a hyphenated
  folder name (e.g. `llm-auditor/`) contains a Python package folder with the
  underscore-converted name (e.g. `llm_auditor/`). Look for `agent.py`,
  `prompt.py`, `tools/`, `sub_agents/`, `eval/`, `tests/`, `deployment/`.
- Sub-agents live in `sub_agents/` and typically provide specialized roles
  (e.g. `critic`, `reviser`). Prompts and agent wiring live in
  `agent.py` and `prompt.py` in the package folder.
- The `wiz/wiz-mcp` sample implements an MCP server style integration. Tool
  definitions for the MCP server are YAML files under
  `src/wiz_mcp_server/tools/tool_definitions/` and user/test payloads are in
  `examples/`.

## Developer workflows (concrete commands)

- Use Poetry for Python dependency management. Typical flow inside an agent
  directory (example: `python/agents/llm-auditor`):

  - Install: `poetry install`
  - With dev deps (tests/eval): `poetry install --with dev`
  - Activate virtualenv: `poetry shell` or `poetry env activate`

- ADK CLI / dev UI:
  - Run agent (CLI): `adk run <package_name>` (e.g. `adk run llm_auditor`)
  - Start web UI for interactive debugging: `adk web`

- Tests and evaluation (examples found in `tests/` and `eval/`):
  - Unit tests: `python -m pytest tests`
  - Eval scripts: `python -m pytest eval` or `poetry run pytest eval`

- Deployment examples:
  - Vertex Agent Engine deploy (example agent):
    `python deployment/deploy.py --create`
  - List/delete deployed agent: `python deployment/deploy.py --list` /
    `--delete`

## Project-specific conventions and patterns

- Environment variables live in `.env.example` files inside each agent. The
  canonical step is `cp .env.example .env` and fill credentials (GCP project,
  API keys, Wiz credentials, RAG corpus id, etc.). Agents read `.env`.
- Naming: the folder uses `kebab-case` while Python package uses `snake_case`.
  When referencing imports or the ADK package name, use the snake_case package
  (e.g. `llm_auditor`).
- Agent entry points: look for `agent.py` (root agent) and `sub_agents/*/agent.py`.
- Tools: custom tools are either Python modules under `tools/` or declarative
  YAML tool definitions (Wiz MCP). The Wiz MCP server exposes `--execute-tool`
  to run a tool payload without running the full server.

## Integration points & external deps to be aware of

- Google Cloud + Vertex AI (Gemini) — many agents expect `GOOGLE_CLOUD_PROJECT`,
  `GOOGLE_CLOUD_LOCATION`, and either Vertex settings or API keys. See each
  agent's `README.md` for exact env variables.
- Wiz API — `wiz/wiz-mcp` requires `WIZ_CLIENT_ID` and `WIZ_CLIENT_SECRET` in
  `.env` or explicit CLI args. MCP integration uses stdio/SSE transports for
  assistant clients.
- Docker is supported for MCP server and some deployment scenarios. Example
  Dockerfile lives under `wiz-mcp/` and the README shows `docker build` and
  `docker run` examples with `--env-file`.

## What to update or inspect before making changes

- Always open the agent's `README.md` first — it documents exact
  environment variables and `pyproject.toml` requirements for that sample.
- Check `pyproject.toml` in the agent directory to see which model/provider
  flags are used (e.g. `GOOGLE_GENAI_USE_VERTEXAI=true/false`).

## Concrete examples to reference when editing or adding features

- Fix an LLM prompt: open `python/agents/llm-auditor/llm_auditor/prompt.py` and
  `llm_auditor/agent.py` to find prompt templates and the critic/reviser
  wiring.
- Add a new Wiz tool: add a YAML under
  `python/agents/wiz/wiz-mcp/src/wiz_mcp_server/tools/tool_definitions/` and a
  matching test payload in `examples/`; test with the `--execute-tool` CLI.

## Preferred modeling/runtime choices (repo-level preference)

- Enable Claude Sonnet 3.5 for all clients: prefer `claude-sonnet-3.5`
  (or the vendor-equivalent token name) whenever the client supports it.
  - Actionable: for local assistant configs (examples in the repo show
    `claude_desktop_config.json` and `cline_mcp_settings.json` snippets used
    for MCP integrations), set the model field to `claude-sonnet-3.5`.
  - Fallback order: if Claude Sonnet 3.5 is not available, fall back to the
    repo's historically used model (check `pyproject.toml` and agent README
    for which provider was used—often Vertex/Gemini). Document any change in
    the specific agent README.

## Edge cases & guardrails for AI editing

- Do not hardcode secrets. Use `.env` or environment variables.
- When changing prompts, preserve existing prompt variables and examples to
  avoid silent behavior regressions — unit tests and eval scripts rely on
  predictable outputs.
- For MCP changes, update `examples/` payloads and `tool_definitions/` YAMLs
  and exercise `--execute-tool` to validate.

## Useful file pointers (quick)

- Repo root README: `README.md`
- Python samples overview: `python/README.md`
- Agents: `python/agents/<agent-name>/README.md` (each agent)
- Agent code: `python/agents/<agent-name>/<agent_name>/agent.py`,
  `prompt.py`, `sub_agents/`
- Wiz MCP tool YAMLs: `python/agents/wiz/wiz-mcp/src/wiz_mcp_server/tools/tool_definitions/`
- Examples & payloads: `python/agents/wiz/wiz-mcp/examples/`

If any section is unclear or you'd like more examples (for a specific
agent or workflow), tell me which agent and I'll expand that section.
