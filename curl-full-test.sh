#!/bin/bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "MAINNETS": ["osmosis", "neutron", "nolus", "crescent", "akash", "cosmoshub", "sentinel", "stargaze", "omniflixhub", "terra", "kujira", "stride", "injective", "juno"],
    "TESTNETS": ["cosmoshubtestnet", "osmosistestnet"]
  }' \
  https://cosmos-upgrades.apis.defiantlabs.net/fetch | jq .
