# Production Safeguards

**This scraper is built for critical infrastructure where lives depend on reliability.**

## Implemented Safeguards

### 1. Atomic File Writes ✓

**Problem:** System crash during file write → corrupted state file → data loss

**Solution:**
```python
# Write to temporary file first
temp_file = f"{state_file}.tmp.{os.getpid()}"
with open(temp_file, 'w') as f:
    json.dump(data, f)
    f.flush()
    os.fsync(f.fileno())  # Force to disk

# Atomic rename (POSIX guarantee)
os.rename(temp_file, state_file)
```

**Guarantees:**
- Either old file exists OR new file exists
- Never partially written files
- Crash-safe operation

---

### 2. Automatic State Backups ✓

**Problem:** State file corruption → permanent data loss

**Solution:**
- Keep last 5 versions of state file
- Automatic rotation before each write
- Fallback cascade if corruption detected

**Files created:**
```
state.json           # Current state
state.json.backup.1  # Previous run
state.json.backup.2  # 2 runs ago
state.json.backup.3  # 3 runs ago
state.json.backup.4  # 4 runs ago
state.json.backup.5  # 5 runs ago
```

**Recovery flow:**
```
state.json corrupted
  → Try backup.1
  → Try backup.2
  → ... up to backup.5
  → If all fail, start fresh
```

---

### 3. Retry Logic with Exponential Backoff ✓

**Problem:** Temporary network issues → scrape failure → missed data

**Solution:**
```python
MAX_RETRIES = 3
BACKOFF_BASE = 2

Attempt 1: Immediate
Attempt 2: Wait 2^0 = 1 second
Attempt 3: Wait 2^1 = 2 seconds
Attempt 4: Wait 2^2 = 4 seconds
```

**Handles:**
- Network hiccups
- Temporary server issues
- Rate limiting
- DNS failures

---

### 4. Data Validation ✓

**Problem:** Malformed data saved → cascading failures in your system

**Solution:**
```python
def validate_entry(entry):
    # Required fields present?
    # Correct types?
    # Non-empty ID?
    # Valid structure?

validate_entries(all_entries)
# Only valid entries saved
```

**Checks:**
- Required fields exist
- Correct data types
- No duplicate IDs
- Content is not empty

**Result:** Invalid entries rejected before saving

---

### 5. Lock Files (Prevent Concurrent Runs) ✓

**Problem:** Earthquake triggers multiple detectors → concurrent scrapes → race condition → corrupted state

**Solution:**
```python
with acquire_lock("state.json.lock"):
    # Exclusive access guaranteed
    scrape_and_save()
```

**Uses:** POSIX `fcntl.flock()` - kernel-level locking

**Behavior:**
- First instance: Acquires lock, runs
- Second instance: Detects lock, exits with code 2

**Lock file contains:** PID of running process

---

### 6. Partial Scrape Detection ✓

**Problem:** Some pages fail → incomplete data → incorrect diff → false negatives

**Solution:**
```python
metadata = {
    'total_pages': 769,
    'successful_pages': 765,
    'failed_pages': 4,
    'partial_scrape': True  # WARNING FLAG
}
```

**Output warning:**
```
⚠️  WARNING: PARTIAL SCRAPE DETECTED
⚠️  4 pages failed to scrape
⚠️  Data may be incomplete - use with caution
```

**Exit code:** 2 (warning, not failure)

**Your system can:**
- Check `metadata.partial_scrape` flag
- Decide whether to use incomplete data
- Log for manual review
- Retry later

---

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Use data normally |
| 1 | Fatal error | Alert operators, investigate |
| 2 | Warning (partial scrape or lock conflict) | Log, consider retry |

---

## Failure Scenarios & Handling

### Scenario 1: Network Failure During Scrape

**What happens:**
1. First few pages succeed
2. Network drops
3. Retry logic attempts 3x with backoff
4. Pages that fail after retries are marked

**Result:**
- Partial data saved
- `metadata.partial_scrape = True`
- Exit code 2
- Your system can decide: use partial data or retry later

---

### Scenario 2: Crash During State Save

**What happens:**
1. Scraping completes
2. Writing to `state.json.tmp.12345`
3. Process killed (OOM, SIGKILL, etc.)

**Result:**
- Old `state.json` still intact
- Temp file abandoned
- Next run works normally with old state

**Recovery:** Automatic (temp file ignored)

---

### Scenario 3: Corrupted State File

**What happens:**
1. Load state.json
2. JSON parse error
3. Try backup.1, backup.2, ..., backup.5
4. If all fail, start fresh

**Result:**
- Falls back to last good state (within 5 runs)
- Or starts fresh if all backups corrupted
- Logs warnings to stderr

---

### Scenario 4: Concurrent Earthquake Events

**What happens:**
1. Detector 1: Earthquake in Istanbul → starts scraper
2. Detector 2: Earthquake in Izmir → starts scraper (2 seconds later)

**Result:**
- First scraper acquires lock
- Second scraper sees lock, exits with code 2
- No corruption, no race condition

**Your system should:**
- Check exit code 2
- Wait for first scraper to finish
- Retry if needed

---

## Configuration Tuning

```python
# In scraper.py, adjust these constants:

MAX_RETRIES = 3              # Network retry attempts
RETRY_BACKOFF_BASE = 2       # Exponential backoff base
REQUEST_TIMEOUT = 20         # HTTP timeout (seconds)
STATE_BACKUP_COUNT = 5       # Number of backups to keep
```

**For high-reliability systems:**
- Increase `MAX_RETRIES` to 5
- Increase `REQUEST_TIMEOUT` to 30
- Increase `STATE_BACKUP_COUNT` to 10

---

## Monitoring Checklist

Your earthquake detection system should monitor:

- [ ] Exit codes (0 = success, 1 = error, 2 = warning)
- [ ] `metadata.partial_scrape` flag in output
- [ ] `metadata.failed_pages` count
- [ ] Lock file conflicts (multiple exit code 2)
- [ ] Backup file count (should have 5)
- [ ] State file size (sudden drops = corruption)
- [ ] Scrape duration (sudden increases = network issues)

---

## Testing Recommendations

### Test 1: Crash Recovery
```bash
# Start scraper
python scraper.py <url> --state test.json &
PID=$!

# Kill it mid-scrape
sleep 5
kill -9 $PID

# Run again - should work
python scraper.py <url> --state test.json
```

**Expected:** Second run works, uses old state or backup

---

### Test 2: Concurrent Run Prevention
```bash
# Terminal 1
python scraper.py <url> --state test.json &

# Terminal 2 (immediately)
python scraper.py <url> --state test.json

# Expected: Second exits with code 2
```

---

### Test 3: Partial Scrape Handling
```bash
# Simulate network issues with firewall/DNS manipulation
# OR use a URL with many pages and kill network midway

python scraper.py <url> --state test.json

# Check metadata.partial_scrape in output
```

---

## Production Deployment Checklist

- [ ] Test on production hardware
- [ ] Test on production network (not just dev machine)
- [ ] Verify lock file path is writable
- [ ] Verify state file directory is writable
- [ ] Test with actual earthquake thread URLs
- [ ] Monitor first 10 runs in production
- [ ] Set up alerting for exit code 1
- [ ] Set up logging for exit code 2
- [ ] Document backup recovery procedure
- [ ] Train operators on manual recovery

---

## Emergency Recovery Procedures

### Recovery 1: All State Lost
```bash
# Remove corrupted files
rm state.json state.json.backup.*

# Run fresh scrape
python scraper.py <url> --state state.json
```

**Impact:** Loses diff history, but scraper works

---

### Recovery 2: Lock File Stuck
```bash
# Check if process is really dead
ps aux | grep scraper.py

# If dead, remove lock
rm state.json.lock

# Run again
python scraper.py <url> --state state.json
```

---

### Recovery 3: Restore from Backup
```bash
# Copy backup to main state
cp state.json.backup.1 state.json

# Run normally
python scraper.py <url> --state state.json
```

---

## Critical: Lives Depend On This

**If scraper fails:**
- Earthquake data missed
- Detection delayed
- Response time increased
- Lives at risk

**Therefore:**
- All errors logged
- All failures handled
- All edge cases covered
- No silent failures
- No data loss

**Test thoroughly. Monitor constantly. Fail safely.**
