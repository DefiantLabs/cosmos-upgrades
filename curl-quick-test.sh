#!/bin/bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "MAINNETS": ["akash"],
    "TESTNETS": ["cosmoshubtestnet"]
  }' \
  https://cosmos-upgrades.apis.defiantlabs.net/fetch | jq .
