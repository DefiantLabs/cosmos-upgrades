import requests
import re
from datetime import datetime
from datetime import timedelta
from random import shuffle
# import logging
import threading
from flask import Flask, jsonify, request, Response
from flask_caching import Cache
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from collections import OrderedDict
import os
import zipfile
import json
import tempfile

app = Flask(__name__)

# Logging configuration
# logging.basicConfig(filename='app.log', level=print, format='%(asctime)s - %(levelname)s - %(message)s')

# Suppress only the single InsecureRequestWarning from urllib3
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

# Initialize cache
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Initialize repo vars
repo_path = ""
repo_last_download_time = None
repo_retain_hours = int(os.environ.get('REPO_RETAIN_HOURS', 3))

# Initialize number of workers
num_workers = int(os.environ.get('NUM_WORKERS', 10))

GITHUB_API_BASE_URL = "https://api.github.com/repos/cosmos/chain-registry/contents"

# these servers have given consistent error responses, this list is used to skip them
SERVER_BLACKLIST = ["https://stride.api.bccnodes.com:443", "https://api.omniflix.nodestake.top", "https://cosmos-lcd.quickapi.com:443"]

# Global variables to store the data for mainnets and testnets
MAINNET_DATA = []
TESTNET_DATA = []

SEMANTIC_VERSION_PATTERN = re.compile(r'v(\d+(?:\.\d+){0,2})')

# Define all utility functions
def download_and_extract_repo():
    """Download the GitHub repository as a zip file, extract it, and return the path to the extracted content."""
    global repo_path

    # Create a temporary directory for extraction
    temp_dir = tempfile.mkdtemp()

    # GitHub API endpoint to get the zip download URL
    repo_api_url = "https://api.github.com/repos/cosmos/chain-registry"
    headers = {
        'Accept': 'application/vnd.github.v3+json',
    }

    print(f"Fetching repo {repo_api_url}...")
    response = requests.get(repo_api_url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from GitHub API. Status code: {response.status_code}")

    response_data = response.json()
    zip_url = response_data.get('archive_url', '').replace('{archive_format}', 'zipball').replace('{/ref}', '/master')

    if not zip_url:
        raise Exception("Failed to obtain the zip URL from the GitHub API response.")

    # Download the zip file
    zip_response = requests.get(zip_url, stream=True, headers=headers)
    zip_filename = "chain-registry.zip"
    with open(zip_filename, 'wb') as zip_file:
        for chunk in zip_response.iter_content(chunk_size=8192):
            zip_file.write(chunk)

    # Extract the zip file
    with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
        extracted_folder = next((folder for folder in os.listdir(temp_dir) if folder.startswith('cosmos-chain-registry-')), None)
        new_repo_path = os.path.join(temp_dir, extracted_folder)

    # Update the global repo_path only after successful extraction
    repo_path = new_repo_path

    return repo_path

def get_healthy_rpc_endpoints(rpc_endpoints):
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        healthy_rpc_endpoints = [rpc for rpc, is_healthy in executor.map(lambda rpc: (rpc, is_endpoint_healthy(rpc['address'])), rpc_endpoints) if is_healthy]

    return healthy_rpc_endpoints[:5]  # Select the first 5 healthy RPC endpoints

def get_healthy_rest_endpoints(rest_endpoints):
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        healthy_rest_endpoints = [rest for rest, is_healthy in executor.map(lambda rest: (rest, is_endpoint_healthy(rest['address'])), rest_endpoints) if is_healthy]

    return healthy_rest_endpoints[:5]  # Select the first 5 healthy REST endpoints

def is_endpoint_healthy(endpoint):
    try:
        response = requests.get(f"{endpoint}/health", timeout=1, verify=False)
        return response.status_code == 200
    except:
        return False

def get_healthy_endpoints(endpoints):
    healthy_endpoints = []

    def check_endpoint(endpoint):
        if is_endpoint_healthy(endpoint['address']):
            healthy_endpoints.append(endpoint)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        executor.map(check_endpoint, endpoints)

    return healthy_endpoints

def check_rest_endpoint(rest_url):
    """Check the REST endpoint and return the application version and response time."""
    start_time = datetime.now()
    try:
        response = requests.get(f"{rest_url}/node_info", timeout=1, verify=False)
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
        response = requests.get(f"{rpc_url}/status", timeout=1)
        response.raise_for_status()
        data = response.json()
        return int(data.get('result', {}).get('sync_info', {}).get('latest_block_height', 0))
    except requests.RequestException as e:
        return -1  # Return -1 to indicate an error

def get_block_time_rpc(rpc_url, height):
    """Fetch the block header time for a given block height from the RPC endpoint."""
    try:
        response = requests.get(f"{rpc_url}/block?height={height}", timeout=1)
        response.raise_for_status()
        data = response.json()
        return data.get('result', {}).get('block', {}).get('header', {}).get('time', "")
    except requests.RequestException as e:
        return None

def parse_isoformat_string(date_string):
    date_string = re.sub(r"(\.\d{6})\d+Z", r"\1Z", date_string)
    date_string = date_string.replace("Z", "+00:00")
    return datetime.fromisoformat(date_string)

def reorder_data(data):
    ordered_data = OrderedDict([
        ("type", data.get("type")),
        ("network", data.get("network")),
        ("rpc_server", data.get("rpc_server")),
        ("latest_block_height", data.get("latest_block_height")),
        ("upgrade_found", data.get("upgrade_found")),
        ("upgrade_name", data.get("upgrade_name")),
        ("source", data.get("source")),
        ("upgrade_block_height", data.get("upgrade_block_height")),
        ("estimated_upgrade_time", data.get("estimated_upgrade_time")),
        ("version", data.get("version"))
    ])
    return ordered_data

def fetch_all_endpoints(network_type, base_url, request_data):
    """Fetch all the REST and RPC endpoints for all networks and store in a map."""
    networks = request_data.get("MAINNETS", []) if network_type == "mainnet" else request_data.get("TESTNETS", [])
    endpoints_map = {}
    for network in networks:
        rest_endpoints, rpc_endpoints = fetch_endpoints(network, base_url)
        endpoints_map[network] = {
            "rest": rest_endpoints,
            "rpc": rpc_endpoints
        }
    return endpoints_map

def fetch_endpoints(network, base_url):
    """Fetch the REST and RPC endpoints for a given network."""
    try:
        response = requests.get(f"{base_url}/{network}/chain.json")
        print(f"{base_url}/{network}/chain.json")
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
                    return plan_name, version, height
        return None, None, None
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
            plan_name = plan.get("name", "")
            version_match = SEMANTIC_VERSION_PATTERN.search(plan_name)
            if version_match:
                version = version_match.group(1)
                try:
                    height = int(plan.get("height", 0))
                except ValueError:
                    height = 0
                return plan_name, version, height
        return None, None, None
    except requests.RequestException as e:
        print(f"Error received from server {rest_url}: {e}")
        raise e
    except Exception as e:
        print(f"Unhandled error while requesting current upgrade endpoint from {rest_url}: {e}")
        raise e

def fetch_data_for_network(network, network_type):
    global repo_path
    """Fetch data for a given network."""

    # Construct the path to the chain.json file based on network type
    if network_type == "mainnet":
        chain_json_path = os.path.join(repo_path, network, 'chain.json')
    elif network_type == "testnet":
        chain_json_path = os.path.join(repo_path, 'testnets', network, 'chain.json')
    else:
        raise ValueError(f"Invalid network type: {network_type}")

    # Check if the chain.json file exists
    if not os.path.exists(chain_json_path):
        print(f"chain.json not found for network {network}. Skipping...")
        return None

    # Load the chain.json data
    with open(chain_json_path, 'r') as file:
        data = json.load(file)

    rest_endpoints = data.get("apis", {}).get("rest", [])
    rpc_endpoints = data.get("apis", {}).get("rpc", [])
    print(f"Found {len(rest_endpoints)} rest endpoints and {len(rpc_endpoints)} rpc endpoints for {network}")

    # Prioritize RPC endpoints for fetching the latest block height
    latest_block_height = -1
    healthy_rpc_endpoints = get_healthy_rpc_endpoints(rpc_endpoints)
    healthy_rest_endpoints = get_healthy_rest_endpoints(rest_endpoints)

    # Shuffle the healthy endpoints
    shuffle(healthy_rpc_endpoints)
    shuffle(healthy_rest_endpoints)

    rpc_server_used = ""
    for rpc_endpoint in healthy_rpc_endpoints:
        latest_block_height = get_latest_block_height_rpc(rpc_endpoint['address'])
        if latest_block_height > 0:
            rpc_server_used = rpc_endpoint['address']
            break

    # Check for active upgrade proposals
    upgrade_block_height = None
    upgrade_name = ""
    upgrade_version = ""
    source = ""

    for index, rest_endpoint in enumerate(healthy_rest_endpoints):
        current_endpoint = rest_endpoint["address"]

        if current_endpoint in SERVER_BLACKLIST:
            continue
        try:
            active_upgrade_name, active_upgrade_version, active_upgrade_height = fetch_active_upgrade_proposals(current_endpoint)
            current_upgrade_name, current_upgrade_version, current_upgrade_height = fetch_current_upgrade_plan(current_endpoint)
        except:
            if index + 1 < len(healthy_rest_endpoints):
                print(f"Failed to query rest endpoints {current_endpoint}, trying next rest endpoint")
                continue
            else:
                print(f"Failed to query rest endpoints {current_endpoint}, all out of endpoints to try")
                break

        if active_upgrade_version and (active_upgrade_height is not None) and active_upgrade_height > latest_block_height:
            upgrade_block_height = active_upgrade_height
            upgrade_version = active_upgrade_version
            upgrade_name = active_upgrade_name
            source = "active_upgrade_proposals"
            break

        if current_upgrade_version and (current_upgrade_height is not None) and current_upgrade_height > latest_block_height:
            upgrade_block_height = current_upgrade_height
            upgrade_version = current_upgrade_version
            upgrade_name = current_upgrade_name
            source = "current_upgrade_plan"
            break

    # Calculate average block time
    current_block_time = get_block_time_rpc(rpc_server_used, latest_block_height)
    past_block_time = get_block_time_rpc(rpc_server_used, latest_block_height - 10000)
    avg_block_time_seconds = None

    if current_block_time and past_block_time:
        current_block_datetime = parse_isoformat_string(current_block_time)
        past_block_datetime = parse_isoformat_string(past_block_time)
        avg_block_time_seconds = (current_block_datetime - past_block_datetime).total_seconds() / 10000

    # Estimate the upgrade time
    estimated_upgrade_time = None
    if upgrade_block_height and avg_block_time_seconds:
        estimated_seconds_until_upgrade = avg_block_time_seconds * (upgrade_block_height - latest_block_height)
        estimated_upgrade_datetime = datetime.utcnow() + timedelta(seconds=estimated_seconds_until_upgrade)
        estimated_upgrade_time = estimated_upgrade_datetime.isoformat().replace('+00:00', 'Z')

    output_data = {
        "network": network,
        "type": network_type,
        "rpc_server": rpc_server_used,
        "latest_block_height": latest_block_height,
        "upgrade_found": upgrade_version != "",
        "upgrade_name": upgrade_name,
        "source": source,
        "upgrade_block_height": upgrade_block_height,
        "estimated_upgrade_time": estimated_upgrade_time,
        "version": upgrade_version
    }
    print(f"Completed fetch data for network {network}")
    return output_data

# periodic cache update
def update_data():
    """Function to periodically update the data for mainnets and testnets."""
    global repo_last_download_time

    while True:
        start_time = datetime.now()  # Capture the start time
        print("Starting data update cycle...")

        # Check if it's time to download the repo
        if repo_last_download_time is None or (datetime.now() - repo_last_download_time).total_seconds() >= 60 * 60 * repo_retain_hours:
            try:
                repo_path = download_and_extract_repo()
                print(f"Repository downloaded and extracted to: {repo_path}")
                repo_last_download_time = datetime.now()
            except Exception as e:
                print(f"Error downloading and extracting repo: {e}")

        try:
            # Process mainnets & testnets
            mainnet_networks = [d for d in os.listdir(repo_path)
                                if os.path.isdir(os.path.join(repo_path, d))
                                and not d.startswith(('.', '_'))
                                and d != "testnets"]

            testnet_path = os.path.join(repo_path, 'testnets')
            testnet_networks = [d for d in os.listdir(testnet_path)
                                if os.path.isdir(os.path.join(testnet_path, d))
                                and not d.startswith(('.', '_'))]

            with ThreadPoolExecutor() as executor:
                testnet_data = list(filter(None, executor.map(lambda network: fetch_data_for_network(network, "testnet"), testnet_networks)))
                mainnet_data = list(filter(None, executor.map(lambda network: fetch_data_for_network(network, "mainnet"), mainnet_networks)))

            # Update the Flask cache
            cache.set('MAINNET_DATA', mainnet_data)
            cache.set('TESTNET_DATA', testnet_data)

            elapsed_time = (datetime.now() - start_time).total_seconds()  # Calculate the elapsed time
            print(f"Data update cycle completed in {elapsed_time} seconds. Sleeping for 1 minute...")
            sleep(60)
        except Exception as e:
            elapsed_time = (datetime.now() - start_time).total_seconds()  # Calculate the elapsed time in case of an error
            print(f"Error in update_data loop after {elapsed_time} seconds: {e}")
            print("Error encountered. Sleeping for 1 minute before retrying...")
            sleep(60)


def start_update_data_thread():
    update_thread = threading.Thread(target=update_data)
    update_thread.daemon = True
    update_thread.start()

@app.route('/healthz')
def health_check():
    return jsonify(status="OK"), 200

@app.route('/fetch', methods=['POST'])
def fetch_network_data():
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "Invalid payload"}), 400

        mainnet_data = cache.get('MAINNET_DATA')
        testnet_data = cache.get('TESTNET_DATA')

        # If the data is not in the cache, fetch it live
        if not mainnet_data or not testnet_data:
            results = []
            for network_type, networks in [("mainnet", request_data.get("MAINNETS", [])),
                                          ("testnet", request_data.get("TESTNETS", []))]:
                for network in networks:
                    try:
                        network_data = fetch_data_for_network(network, network_type)
                        results.append(network_data)
                    except Exception as e:
                        print(f"Error fetching data for network {network}: {e}")
        else:
            # Filter the cached data based on the networks provided in the POST request
            filtered_mainnet_data = [data for data in mainnet_data if data['network'] in request_data.get("MAINNETS", [])]
            filtered_testnet_data = [data for data in testnet_data if data['network'] in request_data.get("TESTNETS", [])]
            results = filtered_mainnet_data + filtered_testnet_data

        sorted_results = sorted(results, key=lambda x: x['upgrade_found'], reverse=True)
        reordered_results = [reorder_data(result) for result in sorted_results]
        return Response(json.dumps(reordered_results, indent=2) + '\n', content_type="application/json")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mainnets')
# @cache.cached(timeout=600)  # Cache the result for 10 minutes
def get_mainnet_data():
    results = cache.get('MAINNET_DATA')
    if results is None:
        return jsonify({"error": "Data not available"}), 500

    results = [r for r in results if r is not None]
    sorted_results = sorted(results, key=lambda x: x['upgrade_found'], reverse=True)
    reordered_results = [reorder_data(result) for result in sorted_results]
    return Response(json.dumps(reordered_results) + '\n', content_type="application/json")

@app.route('/testnets')
# @cache.cached(timeout=600)  # Cache the result for 10 minutes
def get_testnet_data():
    results = cache.get('TESTNET_DATA')
    if results is None:
        return jsonify({"error": "Data not available"}), 500

    results = [r for r in results if r is not None]
    sorted_results = sorted(results, key=lambda x: x['upgrade_found'], reverse=True)
    reordered_results = [reorder_data(result) for result in sorted_results]
    return Response(json.dumps(reordered_results) + '\n', content_type="application/json")

if __name__ == '__main__':
    app.debug = True
    start_update_data_thread()
    app.run(host='0.0.0.0', use_reloader=False)
