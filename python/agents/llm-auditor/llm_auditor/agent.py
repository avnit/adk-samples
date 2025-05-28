"""LLM Auditor for verifying & refining LLM-generated answers using the web."""

from google.adk.agents import SequentialAgent

from .sub_agents.critic import critic_agent
from .sub_agents.reviser import reviser_agent


llm_auditor = SequentialAgent(
    name='llm_auditor',
    description=(
        'You are a security analytics and want to monitor all the commands that are passed to the LLM. We want to make it really safe and no credentials are passed to the LLM'
    ),
    sub_agents=[critic_agent, reviser_agent],
)

root_agent = llm_auditor
