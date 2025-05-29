import os
import requests
import json
from typing import Dict, Any, Optional, Union, Callable # Added Callable

import google.adk # Assuming this is the correct base Agent class
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.adk.agents import llm_agent as llmagent
# Assuming prompt.py exists in the same directory or is correctly pathed
from google.genai import types
from . import prompt,wizqueryagent
   
custom_wiz_query_for_run = {
             "query": """
                query SpecificAssetVulnerabilities($assetId: ID!, $severity: [Severity!]) {
                  asset(id: $assetId) {
                    id
                    name
                    operatingSystem
                    vulnerabilities(filterBy: {severity: $severity, status: [OPEN]}, first: 25) {
                      nodes { id name severity }
                    }
                  }
                }
            """,
            "variables": {
                "assetId": "wiz_asset_id_123", # Replace with a real or dynamically determined asset ID
                "severity": ["CRITICAL", "HIGH"]
            }
}
ask_wiz_for_case_solution = wizqueryagent.WizQueryAgent(
    description = "Get security data for old cases",
    default_query=custom_wiz_query_for_run
)



wiz_agent_instance = llmagent.LlmAgent(
    model='gemini-2.0-flash',
    name='wiz_security_auditor_agent',
    instruction=prompt.return_instructions_root(), 
  #  tools=[ask_wiz_for_case_solution]
)

# Example of how you might run this agent (conceptual, actual usage depends on ADK framework)
# if __name__ == '__main__':
#     # This is a conceptual test and NOT how ADK typically invokes agents.
#     # It's just to illustrate a potential flow if you were to test parts manually.
#     print("Starting conceptual WizQueryAgent test...")
#     if not WIZ_CLIENT_ID or not WIZ_CLIENT_SECRET:
#         print("Please set WIZ_CLIENT_ID and WIZ_CLIENT_SECRET environment variables for testing.")
#     else:
#         # Simulate an LlmResponse and CallbackContext
#         mock_llm_response = LlmResponse(id="test_llm_resp_001", text="LLM analysis complete.")
#         mock_context = CallbackContext(invocation_id="test_inv_001", agent_input={"user_query": "Audit my critical issues"})
#
#         callback_instance = WizQueryAgent() # Instantiating manually for test
#         updated_response = callback_instance(mock_context, mock_llm_response)
#
#         if updated_response and updated_response.output_data:
#             print("\n--- Conceptual Test Result ---")
#             print(f"LLM Response ID: {updated_response.id}")
#             print(f"Original Text: {updated_response.text}")
#             print("Wiz Findings in output_data:")
#             print(json.dumps(updated_response.output_data.get('wiz_findings'), indent=2))
#             if 'wiz_error' in updated_response.output_data:
#                 print(f"Wiz Error: {updated_response.output_data['wiz_error']}")
#         else:
#             print("Conceptual test did not yield an updated response or output_data.")