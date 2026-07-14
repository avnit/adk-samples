"""ADK agent that exposes both 2-legged and 3-legged auth-backed tools.

This wires the provider-backed tools from ``tools.py`` into a standard ADK
``LlmAgent``. The agent can answer org-wide questions (2-legged) and
user-specific questions (3-legged) and, crucially, the two tools look
identical from the model's point of view -- the auth complexity is hidden
inside the providers.

Requires ``google-adk`` (see requirements.txt). The core ``auth_provider``
module and the ``demo``/tests do NOT require ADK, so you can explore the auth
flows without installing it.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from .tools import get_user_profile, list_org_security_findings

INSTRUCTION = """\
You are a security operations assistant that can retrieve two kinds of data:

1. Organization-wide security findings — use `list_org_security_findings`.
   This uses machine (2-legged) auth and needs no user identity.

2. A specific user's own profile — use `get_user_profile`. This uses
   on-behalf-of-user (3-legged) auth. If the tool responds that consent is
   required, present the returned `authorization_url` to the user and ask them
   to approve access before retrying.

Always pick the tool that matches the *ownership* of the requested data:
org-level data -> the 2-legged tool; a person's own data -> the 3-legged tool.
"""

root_agent = LlmAgent(
    model="gemini-2.0-flash",
    name="auth_provider_demo_agent",
    description=(
        "Demonstrates ADK tools backed by both 2-legged (client_credentials) "
        "and 3-legged (authorization_code) OAuth2 via a shared auth provider."
    ),
    instruction=INSTRUCTION,
    tools=[list_org_security_findings, get_user_profile],
)
