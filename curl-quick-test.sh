#!/bin/bash
curl -vvv -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "MAINNETS": ["stargaze"],
    "TESTNETS": ["cosmoshubtestnet"]
  }' \
  http://localhost:80/fetch
