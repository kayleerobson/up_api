#!/usr/bin/env bash
# Pulls everything the 2Up Money page needs from the Up API into a work folder.
# usage: tools/up_money/fetch_all.sh [WORK_DIR]   (default: .up_work)
# Needs UP_API_TOKEN in the environment.
set -euo pipefail
WORK="${1:-.up_work}"
API="https://api.up.com.au/api/v1"
: "${UP_API_TOKEN:?UP_API_TOKEN is not set}"
mkdir -p "$WORK/joint"

get() { curl -gsS --fail-with-body -H "Authorization: Bearer $UP_API_TOKEN" "$1"; }

# Follows links.next and writes one JSON array of every resource.
get_all() {
  local url="$1" out="$2" tmp
  tmp="$(mktemp)"
  : > "$tmp"
  while [ -n "$url" ] && [ "$url" != "null" ]; do
    local page; page="$(get "$url")"
    echo "$page" | jq -c '.data[]' >> "$tmp"
    url="$(echo "$page" | jq -r '.links.next // empty')"
  done
  jq -s '.' "$tmp" > "$out"; rm -f "$tmp"
}

get "$API/accounts?page[size]=100" > "$WORK/accounts.json"
get "$API/categories" > "$WORK/categories.json"
get_all "$API/tags?page[size]=100" "$WORK/tags.json"
for id in $(jq -r '.data[] | select(.attributes.ownershipType=="JOINT") | .id' "$WORK/accounts.json"); do
  get_all "$API/accounts/$id/transactions?page[size]=100" "$WORK/joint/$id.json"
done
echo "Fetched $(jq -s 'map(length) | add' "$WORK"/joint/*.json) joint transactions into $WORK"
