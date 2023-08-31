#!/bin/bash

declare -A networks=(
  [mainnets]="osmosis neutron nolus crescent akash cosmoshub sentinel stargaze omniflixhub cosmoshub terra kujira stride injective juno agoric evmos noble omny quasar dvpn onomy"
  [testnets]="agorictestnet quasartestnet stridetestnet onomytestnet axelartestnet nibirutestnet nobletestnet dydxtestnet osmosistestnet cosmoshubtestnet"
)

base_url="https://cosmos-upgrades.apis.defiantlabs.net"

# Loop over both mainnets and testnets
for type in "${!networks[@]}"; do
  # Construct the jq filter dynamically
  jq_filter='.[] | select(.network | IN('
  for network in ${networks[$type]}; do
    jq_filter+='"'$network'",'
  done
  jq_filter=${jq_filter%,}')) | select(.upgrade_found == true)'

  # Use the constructed filter with curl and jq
  curl -s -X GET \
    -H "Content-Type: application/json" \
    $base_url/"$type" | jq "$jq_filter"
done
