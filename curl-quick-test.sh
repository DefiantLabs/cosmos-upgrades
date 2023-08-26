#!/bin/bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "MAINNETS": ["stargaze"],
    "TESTNETS": ["cosmoshubtestnet"]
  }' \
  http://localhost:5000/fetch