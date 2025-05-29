import os
import requests
import json
from typing import Dict, Any, Optional, Union, Callable # Added Callable
# --- Wiz API Configuration ---
WIZ_CLIENT_ID = os.environ.get("WIZ_CLIENT_ID")
WIZ_CLIENT_SECRET = os.environ.get("WIZ_CLIENT_SECRET")
DEFAULT_WIZ_AUTH_URL = "https://auth.wiz.io/oauth/token"
# Default Wiz API Base URL - adjust if your Wiz instance is in a specific region e.g., https://api.us1.wiz.io
DEFAULT_WIZ_API_BASE_URL = "https://api.wiz.io"
DEFAULT_WIZ_GQL_PATH = "/graphql" # Common path for GraphQL queries
class WizQueryAgent:
    def __init__(self,
                 name: str = 'WizQueryAgent',
                 description: str = 'Queries Wiz API for security data after LLM processing.',
                 default_query: Optional[Dict[str, Any]] = None,
                 default_endpoint: str = DEFAULT_WIZ_GQL_PATH,
                 default_method: str = "POST", # GraphQL is typically POST
                 wiz_api_base_url: str = DEFAULT_WIZ_API_BASE_URL):
        self.name = name
        self.description = description
        self.access_token: Optional[str] = None
        self.default_query = default_query if default_query else self._get_default_graphql_query()
        self.default_endpoint = default_endpoint
        self.default_method = default_method
        self.wiz_api_base_url = wiz_api_base_url
        print(f"{self.name} initialized. Ready to act as an ADK callback.")

    def _get_default_graphql_query(self) -> Dict[str, Any]:
        """Provides a default GraphQL query. Customize as needed."""
        return {
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

    def _ensure_token(self) -> bool:
        """Ensures a valid access token is available."""
        if not self.access_token:
            self.access_token = _get_wiz_access_token()
        return self.access_token is not None

    def fetch_wiz_data(self,
                       endpoint: str,
                       method: str,
                       payload: Optional[Dict[str, Any]] = None
                       ) -> Optional[Union[Dict[str, Any], list]]:
        """A reusable method to fetch data from Wiz."""
        if not self._ensure_token() or not self.access_token:
            print(f"{self.name}: Cannot fetch Wiz data, authentication failed or token not available.")
            return None

        json_body_to_send = None
        query_params_to_send = None

        if method.upper() in ["POST", "PUT", "PATCH"]:
            json_body_to_send = payload
        else: # GET, DELETE etc.
            query_params_to_send = payload

        return _make_wiz_api_request(
            base_api_url=self.wiz_api_base_url,
            endpoint_path=endpoint,
            access_token=self.access_token,
            method=method,
            query_params=query_params_to_send,
            json_body=json_body_to_send
        )

        def __call__(self, callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
            """
            ADK callback method. Fetches Wiz data and appends it to the LlmResponse.
            The parameter names 'callback_context' and 'llm_response' must match
            how the ADK framework calls this callback.
            """
            #print(f"{self.name} (callback) received LLM response ID: {llm_response.id}. Invocation ID: {callback_context.invocation_id}") # Changed context to callback_context

            wiz_query_payload = self.default_query
            wiz_endpoint = self.default_endpoint
            wiz_method = self.default_method

            print(f"{self.name}: Using Wiz query payload: {json.dumps(wiz_query_payload)[:200]}...")

            wiz_results = self.fetch_wiz_data(
                endpoint=wiz_endpoint,
                method=wiz_method,
                payload=wiz_query_payload
            )
            return llm_response

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

    response_obj = None # To store the response object for logging in case of JSONDecodeError
    try:
        print(f"WizAgent: Making {method.upper()} request to: {full_url}")
        if query_params: print(f"WizAgent: With query params: {query_params}")
        if json_body: print(f"WizAgent: With JSON body: {json.dumps(json_body)[:200]}...")

        response_obj = requests.request(method.upper(), full_url, headers=headers, params=query_params, json=json_body)
        response_obj.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)

        if response_obj.status_code == 204: # No Content
            return {}
        return response_obj.json()

    except requests.exceptions.HTTPError as e:
        print(f"WizAgent HTTP Error during API request to {full_url}: {e}")
        if e.response is not None:
            print(f"WizAgent Error Response content: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e: # For other network/DNS issues etc.
        print(f"WizAgent RequestException during API request to {full_url}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"WizAgent Error: Failed to decode JSON response from API: {full_url} - {e}")
        if response_obj is not None:
            try:
                print(f"WizAgent Error: Response content that failed to parse: {response_obj.text}")
            except Exception as text_ex:
                print(f"WizAgent Error: Could not get text from response object: {text_ex}")
        return None

# --- WizQueryAgent (Callable Class for ADK Callback) ---
