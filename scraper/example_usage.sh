#!/bin/bash
# Example: How to use the scraper with diff tracking

URL="https://eksisozluk.com/6-subat-2023-kahramanmaras-depremi--7708989"
STATE_FILE="earthquake_state.json"
OUTPUT_FILE="earthquake_data.json"

echo "=== Example 1: First run (creates initial state) ==="
python scraper.py "$URL" --state "$STATE_FILE" --output "$OUTPUT_FILE"
echo ""
echo "State saved to: $STATE_FILE"
echo "Data saved to: $OUTPUT_FILE"
echo ""

echo "=== Example 2: Second run (shows no changes if immediate) ==="
python scraper.py "$URL" --state "$STATE_FILE" --diff-only
echo ""

echo "=== Example 3: Get only diff summary ==="
python scraper.py "$URL" --state "$STATE_FILE" --diff-only 2>/dev/null | jq '.summary'
echo ""

echo "=== Integration with earthquake detector ==="
echo "In your earthquake detection system, you would:"
echo "1. Detect earthquake event"
echo "2. Call: python scraper.py <eksisozluk_url> --state state.json --diff-only"
echo "3. Parse JSON output to analyze new entries, edits, deletions"
echo "4. Feed changes to your NLP/analysis pipeline"
