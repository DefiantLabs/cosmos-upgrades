import requests
from urllib3.exceptions import InsecureRequestWarning
import re
from datetime import datetime

# Suppress only the single InsecureRequestWarning from urllib3
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BASE_URL = "https://raw.githubusercontent.com/cosmos/chain-registry/master"
NETWORKS = ["osmosis", "neutron", "nolus", "crescent", "akash", "cosmoshub", "sentinel", "stargaze", "omniflixhub", "terra", "kujira", "stride", "injective", "juno"]
# NETWORKS = ["osmosis", "stride"]
SEMANTIC_VERSION_PATTERN = re.compile(r'v(\d+(?:\.\d+){0,2})')

def check_rest_endpoint(rest_url):
    """Check the REST endpoint and return the application version and response time."""
    start_time = datetime.now()
    try:
        response = requests.get(f"{rest_url}/node_info", timeout=3, verify=False)
        response.raise_for_status()
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        data = response.json()
        app_version = data.get('application_version', {}).get('version')
        return app_version, elapsed_time
    except (requests.RequestException, requests.Timeout):
        return None, (datetime.now() - start_time).total_seconds()

def get_latest_block_height_rpc(rpc_url):
    """Fetch the latest block height from the RPC endpoint."""
    try:
        response = requests.get(f"{rpc_url}/status", timeout=3)
        response.raise_for_status()
        data = response.json()
        return int(data.get('result', {}).get('sync_info', {}).get('latest_block_height', 0))
    except requests.RequestException as e:
        return -1  # Return -1 to indicate an error

def fetch_all_endpoints():
    """Fetch all the REST and RPC endpoints for all networks and store in a map."""
    endpoints_map = {}
    for network in NETWORKS:
        rest_endpoints, rpc_endpoints = fetch_endpoints(network)
        endpoints_map[network] = {
            "rest": rest_endpoints,
            "rpc": rpc_endpoints
        }
    return endpoints_map

def fetch_endpoints(network):
    """Fetch the REST and RPC endpoints for a given network."""
    try:
        response = requests.get(f"{BASE_URL}/{network}/chain.json")
        response.raise_for_status()
        data = response.json()
        rest_endpoints = data.get("apis", {}).get("rest", [])
        rpc_endpoints = data.get("apis", {}).get("rpc", [])
        return rest_endpoints, rpc_endpoints
    except requests.RequestException:
        return [], []

def fetch_active_upgrade_proposals(rest_url):
    try:
        response = requests.get(f"{rest_url}/cosmos/gov/v1beta1/proposals?proposal_status=2", verify=False)
        
        # Handle 501 Server Error
        if response.status_code == 501:
            return None, None
        
        response.raise_for_status()
        data = response.json()
        
        # print(f"Received response: {data} from server: {rest_url}")
        
        for proposal in data.get("proposals", []):
            content = proposal.get("content", {})
            if content.get("@type") == "/cosmos.upgrade.v1beta1.SoftwareUpgradeProposal":
                # Extract version from the plan name
                plan_name = content.get("plan", {}).get("name", "")
                plan_version_match = SEMANTIC_VERSION_PATTERN.search(plan_name)
                
                # Extract version from the description
                description = content.get("description", "")
                description_version_match = SEMANTIC_VERSION_PATTERN.search(description)
                
                # Prioritize the longer semantic version
                
                if plan_version_match and description_version_match:
                    version = plan_version_match.group(1) if len(plan_version_match.group(1)) > len(description_version_match.group(1)) else description_version_match.group(1)
                elif plan_version_match:
                    version = plan_version_match.group(1)
                elif description_version_match:
                    version = description_version_match.group(1)
                else:
                    version = None
                
                try:
                    height = int(content.get("plan", {}).get("height", 0))
                except ValueError:
                    height = 0
                
                if version:
                    return version, height
        return None, None
    except requests.RequestException as e:
        print(f"Error received from server {rest_url}: {e}")
        return None, None

def fetch_current_upgrade_plan(rest_url):
    try:
        response = requests.get(f"{rest_url}/cosmos/upgrade/v1beta1/current_plan", verify=False)
        response.raise_for_status()
        data = response.json()
        
        print(f"Received response: {data} from server: {rest_url}")
        
        plan = data.get("plan", {})
        if plan:
            version_match = SEMANTIC_VERSION_PATTERN.search(plan.get("name", ""))
            if version_match:
                version = version_match.group(1)
                try:
                    height = int(plan.get("height", 0))
                except ValueError:
                    height = 0
                return version, height
        return None, None
    except requests.RequestException as e:
        print(f"Error received from server {rest_url}: {e}")
        return None, None

def fetch_data_for_network(network, endpoints):
    """Fetch data for a specific network and print the results."""
    rest_endpoints = endpoints.get("rest", [])
    rpc_endpoints = endpoints.get("rpc", [])
    
    # Prioritize RPC endpoints for fetching the latest block height
    latest_block_height = -1
    for rpc_endpoint in rpc_endpoints:
        latest_block_height = get_latest_block_height_rpc(rpc_endpoint['address'])
        if latest_block_height > 0:
            break
    if latest_block_height <= 0:
        return

    # Check for active upgrade proposals
    for rest_endpoint in rest_endpoints:
        version, upgrade_height = fetch_active_upgrade_proposals(rest_endpoint['address'])
        if version and upgrade_height > latest_block_height:
            print(f"Found software upgrade for {network.capitalize()} on endpoint {rest_endpoint['address']}:")
            print(f"Upgrade proposal version: {version} at height {upgrade_height}\n")
            return

        # Check for current upgrade plan
        version, upgrade_height = fetch_current_upgrade_plan(rest_endpoint['address'])
        if version is None and upgrade_height is None:
            print(f"No software upgrade scheduled for {network.capitalize()} on endpoint {rest_endpoint['address']}.")
            return  # Stop checking more endpoints

        if version and upgrade_height > latest_block_height:
            print(f"Found software upgrade plan for {network.capitalize()} on endpoint {rest_endpoint['address']}:")
            print(f"Upgrade plan version: {version} at height {upgrade_height}\n")
            return

    print(f"No software upgrade found for {network.capitalize()} on checked endpoints.\n")
    return network

def main():
    endpoints_map = fetch_all_endpoints()
    for network in NETWORKS:
        fetch_data_for_network(network, endpoints_map.get(network, {}))

if __name__ == "__main__":
    main()
