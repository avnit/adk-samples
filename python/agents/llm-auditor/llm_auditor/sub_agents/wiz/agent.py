import os
import requests
import json
from typing import Dict, Any, Optional, Union # Added Union for type hinting

# --- Wiz API Configuration ---
WIZ_CLIENT_ID = os.environ.get("WIZ_CLIENT_ID")
WIZ_CLIENT_SECRET = os.environ.get("WIZ_CLIENT_SECRET")
DEFAULT_WIZ_AUTH_URL = "https://auth.wiz.io/oauth/token"
# Default Wiz API Base URL - adjust if your Wiz instance is in a specific region e.g., https://api.us1.wiz.io
DEFAULT_WIZ_API_BASE_URL = "https://api.wiz.io"
DEFAULT_WIZ_GQL_PATH = "/graphql" # Common path for GraphQL queries

# --- Internal Helper Functions ---
def _get_wiz_access_token(
    auth_url: str = DEFAULT_WIZ_AUTH_URL,
    client_id: Optional[str] = WIZ_CLIENT_ID,
    client_secret: Optional[str] = WIZ_CLIENT_SECRET
) -> Optional[str]:
    """Authenticates with the Wiz API to get an access token."""
    if not client_id or not client_secret:
        print("WizAgent Error: WIZ_CLIENT_ID and WIZ_CLIENT_SECRET environment variables must be set.")
        return None

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": "wiz-api"  # Common audience for Wiz API
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        print(f"WizAgent: Attempting to get access token from: {auth_url}")
        response = requests.post(auth_url, data=payload, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")
        if access_token:
            print("WizAgent: Successfully obtained access token.")
            return access_token
        else:
            print(f"WizAgent Error: Access token not found in response. Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"WizAgent Error during authentication: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"WizAgent Error Response content: {e.response.text}")
    return None

def _make_wiz_api_request(
    base_api_url: str,
    endpoint_path: str,
    access_token: str,
    method: str = "GET",
    query_params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None
) -> Optional[Union[Dict[str, Any], list]]: # Can return dict or list
    """Makes an authenticated request to a specified Wiz API endpoint."""
    if not endpoint_path.startswith("/"):
        full_url = f"{base_api_url}/{endpoint_path}"
    else:
        full_url = f"{base_api_url}{endpoint_path}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        print(f"WizAgent: Making {method} request to: {full_url}")
        if query_params: print(f"WizAgent: With query params: {query_params}")
        if json_body: print(f"WizAgent: With JSON body: {json.dumps(json_body)[:200]}...") # Log snippet

        response = requests.request(method.upper(), full_url, headers=headers, params=query_params, json=json_body)
        response.raise_for_status()
        if response.status_code == 204: # No Content
            return {}
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"WizAgent Error during API request to {endpoint_path}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"WizAgent Error Response content: {e.response.text}")
    except json.JSONDecodeError:
        print(f"WizAgent Error: Failed to decode JSON response from API: {endpoint_path}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"WizAgent Error Response content: {e.response.text}")
    return None

# --- WizQueryAgent ---
# Assuming your ADK agents are callable classes or have a specific base class.
# For this example, we'll make it a simple callable class.
# If 'google.adk.agents.BaseAgent' is available and preferred, you can inherit from it.
class WizQueryAgent:
    def __init__(self, name: str = 'WizQueryAgent', description: str = 'Queries Wiz API for security data.'):
        self.name = name
        self.description = description
        self.access_token: Optional[str] = None
        # You could allow configuring default queries here or pass them in __call__

    def _ensure_token(self) -> bool:
        """Ensures a valid access token is available."""
        if not self.access_token: # Or add token expiry check if needed
            self.access_token = _get_wiz_access_token()
        return self.access_token is not None

    def fetch_wiz_data(self, 
                         endpoint: str = DEFAULT_WIZ_GQL_PATH, 
                         method: str = "POST", 
                         payload: Optional[Dict[str, Any]] = None,
                         api_base_url: str = DEFAULT_WIZ_API_BASE_URL) -> Optional[Union[Dict[str, Any], list]]:
        """
        A reusable method to fetch data from Wiz.
        'payload' here is typically 'json_body' for POST or 'query_params' for GET.
        """
        if not self._ensure_token() or not self.access_token:
            print(f"{self.name}: Cannot fetch data, authentication failed or token not available.")
            return None
        
        json_body_to_send = None
        query_params_to_send = None

        if method.upper() == "POST" or method.upper() == "PUT":
            json_body_to_send = payload
        else: # GET, DELETE
            query_params_to_send = payload
            
        return _make_wiz_api_request(
            base_api_url=api_base_url,
            endpoint_path=endpoint,
            access_token=self.access_token,
            method=method,
            query_params=query_params_to_send,
            json_body=json_body_to_send
        )

    def __call__(self, input_data: Any, **kwargs) -> Any:
        """
        Processes input data, fetches relevant Wiz information, and appends it.
        'input_data' could be a dictionary or a custom object.
        'kwargs' could provide specific query instructions.
        """
        print(f"{self.name} received input: {str(input_data)[:200]}...")
        
        # Example: Define a default query or take instructions from kwargs
        # This is a placeholder for critical issues query.
        # You should customize this query based on what 'llm_auditor' needs.
        default_graphql_query = {
            "query": """
                query CriticalIssues($filterBy: IssueFilters, $first: Int) {
                  issues(filterBy: $filterBy, first: $first) {
                    nodes {
                      id
                      type
                      severity
                      status
                      entitySnapshot {
                        id
                        name
                        type
                        cloudPlatform
                      }
                    }
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                  }
                }
            """,
            "variables": {
                "first": 5, # Fetch top 5 critical issues
                "filterBy": {
                    "status": ["OPEN"],
                    "severity": ["CRITICAL"]
                }
            }
        }
        
        # Allow overriding the query via kwargs if needed
        wiz_query_payload = kwargs.get("wiz_query_payload", default_graphql_query)
        wiz_endpoint = kwargs.get("wiz_endpoint", DEFAULT_WIZ_GQL_PATH)
        wiz_method = kwargs.get("wiz_method", "POST" if wiz_endpoint == DEFAULT_WIZ_GQL_PATH else "GET")
        
        wiz_results = self.fetch_wiz_data(
            endpoint=wiz_endpoint,
            method=wiz_method,
            payload=wiz_query_payload
        )

        if isinstance(input_data, dict):
            input_data['wiz_findings'] = wiz_results if wiz_results else {}
        else:
            # If input_data is not a dict, you might need to handle it differently
            # For simplicity, we'll just show it as a new key if it were a dict
            print(f"{self.name}: Input data is not a dict, Wiz findings not directly appended. Findings: {wiz_results}")
            # Potentially return a tuple or a modified structure
            return {"original_input": input_data, "wiz_findings": wiz_results if wiz_results else {}}


        print(f"{self.name}: Successfully processed and appended Wiz findings.")
        return input_data

# You can create a default instance for easy import if desired
wiz_query_agent_instance = WizQueryAgent()