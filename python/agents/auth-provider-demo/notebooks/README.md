# Auth Manager Notebooks — Gemini Enterprise agents

Four runnable Jupyter notebooks that demonstrate a single **auth manager**
supplying **2-legged** (service identity) and **3-legged** (on-behalf-of-user)
OAuth2 credentials to Gemini Enterprise agents across three integration
surfaces: **agent-to-agent (A2A)**, **agent-to-MCP**, and a **private agent
gateway over Private Service Connect (PSC)**.

| Notebook | Scenario | Runs offline? |
|----------|----------|:---:|
| [`00_overview_auth_manager.ipynb`](00_overview_auth_manager.ipynb) | The auth manager, 2LO vs 3LO, and mapping to Gemini Enterprise *Authorizations*. | ✅ |
| [`01_agent_to_agent_auth.ipynb`](01_agent_to_agent_auth.ipynb) | A2A calls authenticated through the auth manager (Agent Card `securitySchemes`). | ✅ |
| [`02_agent_to_mcp_auth.ipynb`](02_agent_to_mcp_auth.ipynb) | MCP `tools/call` authenticated through the auth manager (OAuth-protected resource). | ✅ |
| [`03_agent_gateway_psc.ipynb`](03_agent_gateway_psc.ipynb) | A private, PSC-fronted gateway validating auth at the edge and routing to agent + MCP backends. | ✅ |

## What "runs offline" means

Every notebook has two kinds of cells:

- **Runnable demo** cells use only the local `auth_provider_demo` package + the
  Python standard library. They stand up a bundled **mock OAuth2 server** (and
  mock A2A / MCP / gateway services) and execute the real auth flows —
  discovery, `401` challenges, token issuance, consent, refresh, routing. No
  Google Cloud project, no `google-adk`, no network.
- **Production mapping** cells show the equivalent **Gemini Enterprise / Vertex
  AI Agent Engine + ADK** code (`RemoteA2aAgent`, `MCPToolset`, PSC `gcloud`).
  Python production cells are gated behind a `RUN_PRODUCTION = False` flag so the
  notebooks execute end-to-end during validation; flip it to `True` (with the
  extra dependencies installed and a project configured) to run them for real.

All four notebooks are committed **with executed outputs**, so you can read the
results without running anything.

## Run them

```bash
cd python/agents/auth-provider-demo

# one-time: notebook tooling + a kernel
pip install jupyter
python -m ipykernel install --user --name python3

jupyter notebook notebooks/        # or: jupyter lab notebooks/
```

Or re-execute headless to verify:

```bash
pip install nbclient nbformat ipykernel
cd notebooks
python - <<'PY'
import nbformat, glob
from nbclient import NotebookClient
for path in sorted(glob.glob("*.ipynb")):
    nb = nbformat.read(path, as_version=4)
    NotebookClient(nb, kernel_name="python3",
                   resources={"metadata": {"path": "."}}).execute()
    print("ok:", path)
PY
```

## Going to production (Gemini Enterprise)

1. **Register Authorizations** — create a named *Authorization* resource per
   credential (2-legged or 3-legged) as shown in notebook 00. These are the
   managed equivalent of `AuthManager.register_*`.
2. **A2A** — publish/consume Agent Cards whose `securitySchemes` reference those
   authorizations; ADK `RemoteA2aAgent` handles the call (notebook 01).
3. **MCP** — attach the authorization to an ADK `MCPToolset`; the platform mints
   the MCP bearer token (notebook 02).
4. **Gateway + PSC** — front your agents/MCP servers with a gateway published via
   a **service attachment**, reached from your VPC through a **PSC endpoint**;
   the gateway validates the authorization at the edge (notebook 03).

## Relationship to the rest of this sample

These notebooks build on the package in the parent directory:

- `auth_provider_demo/auth_provider.py` — `TwoLeggedAuthProvider` /
  `ThreeLeggedAuthProvider` (the OAuth flows).
- `auth_provider_demo/auth_manager.py` — `AuthManager`, the named-authorization
  registry the notebooks use.
- `auth_provider_demo/mock_oauth_server.py` — the offline OAuth2 server.

See the [parent README](../README.md) for the library, the CLI demo, and tests.

> These notebooks are for demonstration purposes only and are not intended for
> production use as-is; the mock servers are test fixtures, not real
> authorization servers or gateways.
