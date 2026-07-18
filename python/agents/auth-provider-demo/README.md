# Auth Provider Demo — 2-legged & 3-legged OAuth for ADK

This sample demonstrates the **value of an auth provider**: one small, uniform
abstraction that lets ADK agents and tools obtain access tokens without caring
*how* those tokens were issued. It implements the two OAuth2 flows you actually
run into when building agents:

| | 2-legged (this repo's Wiz flow) | 3-legged |
|---|---|---|
| **Grant** | `client_credentials` | `authorization_code` (+ PKCE) |
| **Who is authenticated?** | the agent/service *itself* | a specific **end user** |
| **Human in the loop?** | No | Yes — consent screen |
| **Good for** | org/system-wide data (Wiz findings, infra APIs) | a user's own data (their profile, mail, repos) |
| **Token scope** | one shared app token | one token **per user**, with refresh |

The whole point: **a tool never sees the difference.** Both providers expose the
same interface —

```python
token   = provider.get_access_token(...)          # -> "ya29..."
headers = provider.auth_headers(...)              # -> {"Authorization": "Bearer ya29..."}
```

so you can swap machine auth for user auth (or add a new provider) without
touching tool code. The providers also cache tokens and refresh them
transparently, which is the practical reason to centralize auth in one place
instead of copy-pasting token logic into every tool.

## Why this matters (the "value")

Before, the only auth in this repo was hand-rolled inside the Wiz agent:
`client_credentials` requests, manual token handling, and no story at all for
acting on behalf of a user. This sample generalizes that into:

1. **`TwoLeggedAuthProvider`** — a clean, cached version of the Wiz-style
   machine-to-machine flow.
2. **`ThreeLeggedAuthProvider`** — the missing user-consent flow, with PKCE,
   CSRF `state` validation, per-user token storage, and automatic refresh.
3. A **single `AuthProvider` interface** both implement, so tools and agents
   stay flow-agnostic.

## Layout

```
auth-provider-demo/
├── auth_provider_demo/
│   ├── auth_provider.py     # core: AuthProvider, TwoLegged/ThreeLegged, Token, TokenStore
│   ├── auth_manager.py      # AuthManager: named-authorization registry (2LO/3LO)
│   ├── mock_oauth_server.py # dependency-free mock OAuth2 server (demo/tests)
│   ├── tools.py             # ADK tool functions backed by the providers
│   ├── agent.py             # ADK LlmAgent wiring both tools (needs google-adk)
│   └── demo.py              # runnable end-to-end walkthrough (no ADK needed)
├── notebooks/               # Gemini Enterprise demos (A2A, MCP, gateway+PSC)
│   ├── 00_overview_auth_manager.ipynb
│   ├── 01_agent_to_agent_auth.ipynb
│   ├── 02_agent_to_mcp_auth.ipynb
│   └── 03_agent_gateway_psc.ipynb
└── tests/
    ├── test_auth_provider.py
    └── test_auth_manager.py
```

## Notebooks — Gemini Enterprise: A2A, MCP, and gateway + PSC

The [`notebooks/`](notebooks/) folder demonstrates the auth manager driving
real Gemini Enterprise integration surfaces — **agent-to-agent (A2A)**,
**agent-to-MCP**, and a **private agent gateway over Private Service Connect
(PSC)** — each runnable fully offline against the bundled mock servers, with the
production ADK / Vertex AI mapping alongside. See the
[notebooks README](notebooks/README.md).

## Run the demo (no dependencies, no ADK, no network)

```bash
cd python/agents/auth-provider-demo
python -m auth_provider_demo.demo
```

It boots the bundled mock OAuth2 server and walks through both flows:

```
2-LEGGED (client_credentials): the agent authenticates AS ITSELF
  grant_type      : client_credentials
  Authorization   : Bearer app-access-1
  cached (reused) : True

3-LEGGED (authorization_code + PKCE): the agent acts ON BEHALF OF a user
  1. send user to  : http://127.0.0.1:.../authorize?response_type=code&...
  2. redirected to : https://app.example.com/oauth/callback?code=...&state=...
  3. exchanged code -> token stored for 'alice'
  Authorization   : Bearer user-access-...
```

## Run the tests

```bash
cd python/agents/auth-provider-demo
python -m unittest discover -s tests -v      # or: pytest
```

Covers token caching, forced refresh, PKCE, CSRF `state` rejection, expiry +
refresh-token reuse, and the two flow-agnostic tools.

## Using it in a real agent

`agent.py` wires the provider-backed tools into a standard ADK `LlmAgent`
(requires `google-adk`). Configure real endpoints via environment variables:

```bash
# Shared
export OAUTH_TOKEN_URL="https://auth.example.com/oauth/token"
export OAUTH_CLIENT_ID="..."
export OAUTH_CLIENT_SECRET="..."          # 2-legged; optional for public 3-legged clients
export OAUTH_SCOPE="read:findings read:profile"

# 3-legged only
export OAUTH_AUTHORIZATION_URL="https://auth.example.com/oauth/authorize"
export OAUTH_REDIRECT_URI="https://your-app.example.com/oauth/callback"
```

Then, for example:

```python
from auth_provider_demo.tools import list_org_security_findings, get_user_profile

list_org_security_findings()      # machine token, no user
get_user_profile(user_id="alice") # returns a consent URL until the user approves
```

### Mapping the 2-legged flow to Wiz

The existing Wiz integration in `llm-auditor` does the same `client_credentials`
request by hand. It is equivalent to:

```python
from auth_provider_demo.auth_provider import TwoLeggedAuthProvider, OAuthEndpoints

wiz = TwoLeggedAuthProvider(
    endpoints=OAuthEndpoints(token_url="https://auth.app.wiz.io/oauth/token"),
    client_id=os.environ["WIZ_CLIENT_ID"],
    client_secret=os.environ["WIZ_CLIENT_SECRET"],
    audience="wiz-api",
)
headers = wiz.auth_headers()   # cached + auto-refreshed
```

### Production notes

* The `MockOAuthServer` is a **test/demo fixture only** — never use it as a real
  authorization server.
* Swap `InMemoryTokenStore` for a database / secret-manager-backed `TokenStore`
  so returning users don't have to re-consent and tokens survive restarts.
* In a hosted ADK deployment, the 3-legged redirect/callback is handled by your
  web layer; hand the callback URL to `fetch_token_from_redirect(...)`. ADK also
  provides native tool-auth primitives (`ToolContext` credential requests) — this
  provider slots in behind those or can be used standalone.

## Disclaimer

This sample is for demonstration purposes only and is not intended for
production use.
