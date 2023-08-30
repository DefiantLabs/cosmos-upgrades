# cosmos-upgrades


`cosmos-upgrades` is a powerful tool developed by [Defiant Labs](https://github.com/DefiantLabs) to search for scheduled Cosmos upgrades. This tool aims to streamline the process of tracking and managing upgrades in the Cosmos ecosystem.

## 🌌 Introduction

The Cosmos ecosystem is vast and ever-evolving. With frequent upgrades and enhancements, it becomes crucial for stakeholders to keep track of scheduled upgrades. `cosmos-upgrades` bridges this gap by providing a centralized solution to fetch and monitor these upgrades.

## 🛠 Problem Statement

Keeping track of scheduled upgrades in a decentralized ecosystem can be challenging. Missing an upgrade can lead to potential downtimes, security vulnerabilities, and missed opportunities. `cosmos-upgrades` addresses this challenge by offering a reliable and up-to-date source of information for all scheduled Cosmos upgrades.

Certainly! Here's the expanded section about the `chain-registry`:

---

## 📚 Chain-Registry Deep Dive

The `chain-registry` is more than just a repository of chain details; it's the backbone that powers the `cosmos-upgrades` tool. Each chain specified in the request is mapped to its corresponding JSON file within the `chain-registry`. This mapping allows the tool to look up vital information, such as endpoints, for each chain.

For instance, when you specify "akash" in your request, the tool refers to the [`akash/chain.json`](https://github.com/cosmos/chain-registry/blob/master/akash/chain.json) file in the `chain-registry` to fetch the necessary details.

### Why is the Chain-Registry Essential?

1. **Accuracy & Reliability:** By centralizing the details of all chains in the `chain-registry`, we ensure that the data fetched by `cosmos-upgrades` is always accurate and up-to-date.
2. **Extensibility:** The design of the `chain-registry` allows for easy additions of new chains or updates to existing ones.
3. **Community Collaboration:** The `chain-registry` is open-source, fostering a collaborative environment. If a user notices a missing chain or outdated information, they can contribute by submitting a PR with the correct details.

### What if a Network is Missing?

If a particular network or chain is not present in the `chain-registry`, the `cosmos-upgrades` tool won't be able to provide information about it. In such cases, we strongly encourage users to:

- Reach out to the protocol leads to inform them about the omission.
- Take a proactive approach by submitting a PR to the `chain-registry` with the correct information.

By doing so, not only do you enhance the tool's capabilities, but you also contribute to the broader Cosmos community.

---

## 🚀 Making Requests

To fetch the scheduled upgrades, you can use the following `curl` command:

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "MAINNETS": ["akash"],
    "TESTNETS": ["cosmoshubtestnet"]
  }' \
  https://cosmos-upgrades.apis.defiantlabs.net/fetch 
```

**Note:** The testnet and mainnet names provided in the request payload should match one-for-one with the names of the chains in the chain-registry.

### Response Format:

The response will be in JSON format containing details of the scheduled upgrades. Here's a sample response:

```json
[
  {
    "latest_block_height": 12593557,
    "network": "akash",
    "rpc_server": "https://akash-rpc.lavenderfive.com:443",
    "source": "current_upgrade_plan",
    "type": "mainnet",
    "upgrade_block_height": 12606074,
    "upgrade_found": true,
    "version": "0.24.0"
  },
  {
    "latest_block_height": 17550150,
    "network": "cosmoshubtestnet",
    "rpc_server": "https://rpc-theta.osmotest5.osmosis.zone/",
    "source": "",
    "type": "testnet",
    "upgrade_block_height": null,
    "upgrade_found": false,
    "version": ""
  }
]
```

**Key Fields:**
- `latest_block_height`: The latest block height of the chain.
- `network`: The name of the network (e.g., "akash" or "cosmoshubtestnet").
- `rpc_server`: The RPC server that provided the response.
- `source`: The source from which the upgrade information was fetched.
- `type`: Specifies whether it's a "mainnet" or "testnet".
- `upgrade_block_height`: The block height at which the upgrade is scheduled.
- `upgrade_found`: A boolean indicating if an upgrade was found.
- `version`: The version of the upgrade.

**Note:** Chains with scheduled upgrades are displayed first in the response.

