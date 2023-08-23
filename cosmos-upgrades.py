import requests
from urllib3.exceptions import InsecureRequestWarning
import re
from datetime import datetime

# Suppress only the single InsecureRequestWarning from urllib3
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BASE_URL = "https://raw.githubusercontent.com/cosmos/chain-registry/master"
# NETWORKS = ["osmosis", "neutron", "nolus", "crescent", "akash", "cosmoshub", "sentinel", "stargaze", "omniflixhub", "terra", "kujira", "stride", "injective", "juno"]
NETWORKS = ["akash", "osmosis"]
SEMANTIC_VERSION_PATTERN = re.compile(r'v(\d+(?:\.\d+){0,2})')

# these servers have given consistent error responses, this list is used to skip them
SERVER_BLACKLIST = ["https://stride.api.bccnodes.com:443", "https://api.omniflix.nodestake.top", "https://cosmos-lcd.quickapi.com:443"]

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
        raise e
    except Exception as e:
        print(f"Unhandled error while requesting active upgrade endpoint from {rest_url}: {e}")
        raise e

def fetch_current_upgrade_plan(rest_url):
    try:
        response = requests.get(f"{rest_url}/cosmos/upgrade/v1beta1/current_plan", verify=False)
        response.raise_for_status()
        data = response.json()
        
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
        raise e
    except Exception as e:
        print(f"Unhandled error while requesting current upgrade endpoint from {rest_url}: {e}")
        raise e

def fetch_data_for_network(network, endpoints):
    print(f"Fetching data for network {network}")
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
        print(f"Failed to find latest block height from all rpc endpoints for network {network}")
        return
    
    print(f"Found latest block height {latest_block_height}")

    # Check for active upgrade proposals
    for index, rest_endpoint in enumerate(rest_endpoints):
        #attempt to get data, move onto next endpoint if either of these fail
        current_endpoint = rest_endpoint["address"]
        
        if current_endpoint in SERVER_BLACKLIST:
            continue
        try:
            #2 data gathering methods, one preferred over the other
            active_upgrade_version, active_upgrade_height = fetch_active_upgrade_proposals(current_endpoint)
            current_upgrade_version, current_upgrade_height = fetch_current_upgrade_plan(current_endpoint)
        except:
            if index + 1 < len(rest_endpoints):
                print(f"Failed to query rest endpoints {current_endpoint}, trying next rest endpoint")
                continue
            else:
                print(f"Failed to query rest endpoints {current_endpoint}, all out of endpoints to try")
                break

            
        if active_upgrade_version and active_upgrade_height > latest_block_height:
            print(f"Found software upgrade for {network.capitalize()} on endpoint {current_endpoint}:")
            print(f"Upgrade proposal version: {active_upgrade_version} at height {active_upgrade_height}")
            return
    
        if current_upgrade_version and current_upgrade_height > latest_block_height:
            print(f"Found software upgrade plan for {network.capitalize()} on endpoint {current_endpoint}:")
            print(f"Upgrade plan version: {current_upgrade_version} at height {current_upgrade_height}")
            return

        # Check for current upgrade plan
        if current_upgrade_version is None and current_upgrade_height is None:
            print(f"No software upgrade scheduled for {network.capitalize()} on endpoint {current_endpoint}.")
            return

def main():
    endpoints_map = fetch_all_endpoints()
    for network in NETWORKS:
        fetch_data_for_network(network, endpoints_map.get(network, {}))

if __name__ == "__main__":
    main()
