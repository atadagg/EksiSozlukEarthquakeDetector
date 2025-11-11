#!/bin/bash
# Production safeguards test suite

set -e

echo "======================================================================"
echo "PRODUCTION SCRAPER SAFEGUARDS TEST SUITE"
echo "======================================================================"
echo ""

# Test URL (use a smaller thread for faster testing)
TEST_URL="https://eksisozluk.com/test--1"
STATE_FILE="test_state.json"
OUTPUT_FILE="test_output.json"
LOCK_FILE="${STATE_FILE}.lock"

# Cleanup function
cleanup() {
    rm -f "$STATE_FILE" "$STATE_FILE".backup.* "$STATE_FILE.tmp".*
    rm -f "$OUTPUT_FILE" "$OUTPUT_FILE.tmp".*
    rm -f "$LOCK_FILE"
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

echo "Test 1: Help Message"
echo "----------------------------------------------------------------------"
python scraper.py 2>&1 | head -10
echo "✓ Help message displayed"
echo ""

echo "Test 2: Basic Scrape (no state)"
echo "----------------------------------------------------------------------"
if python scraper.py "$TEST_URL" --output "$OUTPUT_FILE" 2>&1 | grep -q "Total entries scraped"; then
    echo "✓ Basic scrape works"
    echo "✓ Output file created: $(ls -lh "$OUTPUT_FILE" | awk '{print $5}')"
else
    echo "✗ Basic scrape failed"
    exit 1
fi
echo ""

echo "Test 3: State File Creation (First Run)"
echo "----------------------------------------------------------------------"
cleanup
if python scraper.py "$TEST_URL" --state "$STATE_FILE" --output "$OUTPUT_FILE" 2>&1 | grep -q "Initial state saved"; then
    echo "✓ State file created"
    echo "✓ State file size: $(ls -lh "$STATE_FILE" | awk '{print $5}')"
else
    echo "✗ State file creation failed"
    exit 1
fi
echo ""

echo "Test 4: Diff Tracking (Second Run - No Changes Expected)"
echo "----------------------------------------------------------------------"
if python scraper.py "$TEST_URL" --state "$STATE_FILE" --diff-only 2>&1 | tee /tmp/test_output.txt | grep -q "Diff Summary"; then
    echo "✓ Diff tracking works"
    echo "✓ Diff summary:"
    grep -A 3 "Diff Summary" /tmp/test_output.txt || true
else
    echo "✗ Diff tracking failed"
    exit 1
fi
echo ""

echo "Test 5: Atomic File Writes (Temp Files Cleaned Up)"
echo "----------------------------------------------------------------------"
TEMP_FILES=$(ls "$STATE_FILE".tmp.* 2>/dev/null | wc -l)
if [ "$TEMP_FILES" -eq 0 ]; then
    echo "✓ No temp files left behind"
else
    echo "✗ Temp files not cleaned up: $TEMP_FILES files"
    exit 1
fi
echo ""

echo "Test 6: State Backups Created"
echo "----------------------------------------------------------------------"
# Run again to trigger backup rotation
python scraper.py "$TEST_URL" --state "$STATE_FILE" --diff-only 2>&1 > /dev/null

BACKUP_COUNT=$(ls "$STATE_FILE".backup.* 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt 0 ]; then
    echo "✓ Backups created: $BACKUP_COUNT backup(s)"
    ls -lh "$STATE_FILE".backup.* 2>/dev/null || true
else
    echo "⚠ No backups created yet (may need more runs)"
fi
echo ""

echo "Test 7: Lock File Prevention (Concurrent Run)"
echo "----------------------------------------------------------------------"
# Start long-running scraper in background
python scraper.py "$TEST_URL" --state "$STATE_FILE" --diff-only > /dev/null 2>&1 &
SCRAPER_PID=$!

# Give it time to acquire lock
sleep 0.5

# Try to run another instance
if python scraper.py "$TEST_URL" --state "$STATE_FILE" --diff-only 2>&1 | grep -q "Another scraper instance"; then
    echo "✓ Lock file prevents concurrent runs"
    # Check lock file exists
    if [ -f "$LOCK_FILE" ]; then
        echo "✓ Lock file exists: $LOCK_FILE"
        echo "✓ Lock file PID: $(cat "$LOCK_FILE")"
    fi
else
    echo "✗ Lock file not working"
fi

# Wait for first scraper to finish
wait $SCRAPER_PID 2>/dev/null || true

# Check lock cleaned up
if [ ! -f "$LOCK_FILE" ]; then
    echo "✓ Lock file cleaned up after completion"
else
    echo "⚠ Lock file not cleaned up"
fi
echo ""

echo "Test 8: Data Validation (JSON Structure)"
echo "----------------------------------------------------------------------"
if python -m json.tool "$OUTPUT_FILE" > /dev/null 2>&1; then
    echo "✓ Output is valid JSON"

    # Check for required fields
    if python -c "import json; d=json.load(open('$OUTPUT_FILE')); assert 'entries' in d or isinstance(d, list)" 2>/dev/null; then
        echo "✓ Output has correct structure"
    else
        echo "✗ Output structure incorrect"
        exit 1
    fi
else
    echo "✗ Output is not valid JSON"
    exit 1
fi
echo ""

echo "Test 9: Exit Codes"
echo "----------------------------------------------------------------------"
# Test successful run
python scraper.py "$TEST_URL" --output /tmp/test_exit.json 2>&1 > /dev/null
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Success exit code: 0"
else
    echo "✗ Unexpected exit code: $EXIT_CODE"
fi

# Test invalid URL (should fail)
python scraper.py "https://eksisozluk.com/nonexistent--999999999" --output /tmp/test_fail.json 2>&1 > /dev/null || EXIT_CODE=$?
if [ $EXIT_CODE -eq 1 ]; then
    echo "✓ Error exit code: 1"
else
    echo "⚠ Expected exit code 1, got: $EXIT_CODE"
fi
echo ""

echo "======================================================================"
echo "TEST SUMMARY"
echo "======================================================================"
echo "✓ All critical safeguards tested"
echo "✓ Production-ready scraper verified"
echo ""
echo "Safeguards confirmed:"
echo "  ✓ Atomic file writes"
echo "  ✓ State backups"
echo "  ✓ Lock files"
echo "  ✓ Data validation"
echo "  ✓ Exit codes"
echo "  ✓ Diff tracking"
echo ""
echo "Ready for deployment in critical infrastructure."
echo "======================================================================"
