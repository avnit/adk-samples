"""LLM Auditor for verifying & refining LLM-generated answers using the web."""
import os
import requests
import json

from google.adk.agents import SequentialAgent
from google.adk.agents import ParallelAgent, LlmAgent

from .sub_agents.critic import critic_agent
from .sub_agents.reviser import reviser_agent
from .sub_agents.wiz import wiz_agent_instance


llm_auditor = SequentialAgent(
    name='llm_auditor',
    description=(
        'You are a security analytics and want to monitor all the commands that are passed to the LLM. We want to make it really safe and no credentials are passed to the LLM'
    ),
    #sub_agents=[critic_agent, reviser_agent],
    sub_agents =[critic_agent, reviser_agent,wiz_agent_instance]
    # sub_agents =[wiz_agent_instance,critic_agent, reviser_agent, device42_agent]
)

root_agent = llm_auditor

if __name__ == "__main__":
    # IMPORTANT: Ensure WIZ_CLIENT_ID and WIZ_CLIENT_SECRET are set in your environment
    # export WIZ_CLIENT_ID="your_actual_client_id"
    # export WIZ_CLIENT_SECRET="your_actual_client_secret"
    
    if not os.environ.get("WIZ_CLIENT_ID") or not os.environ.get("WIZ_CLIENT_SECRET"):
        print("FATAL: WIZ_CLIENT_ID and WIZ_CLIENT_SECRET environment variables are not set.")
        print("Please set them before running the script, e.g.:")
        print("  export WIZ_CLIENT_ID=\"d3i2kqkz65d6tktv4rytwuyxoz5nhwedvzefuwfvgdoivpaabe7xg\"")
        print("  export WIZ_CLIENT_SECRET=\"8NzpglyRIi89gHv0IXkippfdmRYjZbhBGly4nHoszfHjB9AQByO33l2KNU8FCHTt\"")
    else:
        print("Starting LLM Auditor agent example with Wiz integration...")
        
        # Initial input for the agent sequence
        # This could be the command intended for an LLM, or context about it.
        initial_llm_interaction_context = {
            "llm_command_text": "Summarize recent critical vulnerabilities in our cloud environment.",
            "user_context": {"department": "security_operations"},
            "target_llm_params": {"model": "some_llm_vNext"}
        }
        
