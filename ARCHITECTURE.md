# Earthquake Detection & Scraping Architecture

## Overview

This system consists of two independent components that work together:

1. **Detector** (`earthquake_detector.py`) - Runs forever, detects earthquakes
2. **Scraper Workers** (`scraper/scraper_worker.py`) - Auto-spawned, self-terminating processes

## Architecture Flow

```
┌─────────────────────────────────────┐
│   Earthquake Detector (Main)       │
│   - Monitors gündem every 30s       │
│   - Detects earthquake başlıks      │
│   - Spawns workers (fire & forget)  │
│   - NEVER shuts down                │
└──────────┬──────────────────────────┘
           │
           │ Spawns worker when earthquake detected
           ├──────────────────────────────────────────┐
           │                                          │
           ▼                                          ▼
┌─────────────────────────┐              ┌─────────────────────────┐
│  Worker Process 1       │              │  Worker Process 2       │
│  - Scrapes every 5min   │              │  - Scrapes every 5min   │
│  - Checks entry count   │              │  - Checks entry count   │
│  - Shuts self down      │              │  - Shuts self down      │
│    when count = 0       │              │    when count = 0       │
└─────────────────────────┘              └─────────────────────────┘
```

## Component Details

### Detector

**File**: `earthquake_detector.py`

**Behavior**:
- Runs forever (until manually stopped)
- Polls Ekşi Sözlük gündem every 30 seconds
- Detects earthquake başlıks using pattern matching
- When earthquake detected:
  1. Logs event to `data/detected_events.jsonl`
  2. Spawns a worker process for that thread URL
  3. Continues monitoring (fire and forget)
- **Duplicate prevention**: Checks lock file before spawning
  - Won't spawn if worker already running for that URL

**Never**:
- Doesn't track workers
- Doesn't shut down workers
- Doesn't manage worker lifecycle

### Scraper Worker

**File**: `scraper/scraper_worker.py`

**Behavior**:
- Independent process spawned by detector
- Scrapes assigned URL every 5 minutes
- After each scrape:
  - If entry count = 0 → **shuts itself down** (thread merged)
  - If entry count > 0 → continues monitoring
  - If scraping fails 3 times consecutively → shuts down
- Saves diffs when new entries detected
- Logs all activity to `worker.log`

**Self-terminating conditions**:
1. Entry count reaches 0 (thread merged)
2. Too many consecutive failures (3)
3. Receives shutdown signal (SIGTERM/SIGINT)

## Data Structure

```
data/
├── detected_events.jsonl         # All detected earthquakes
└── scrapers/
    └── <earthquake_id>/          # One folder per earthquake
        ├── state.json            # Current state for diff tracking
        ├── state.json.lock       # Lock file (worker running)
        ├── worker.log            # Worker logs
        └── diffs/                # Diff outputs
            ├── diff_20250111_120000.json
            └── diff_20250111_120500.json
```

## Running the System

### Start the detector:

```bash
python earthquake_detector.py
```

That's it! The detector will:
- Monitor for earthquakes
- Auto-spawn workers as needed
- Workers will auto-terminate when threads merge

### Manually test a worker:

```bash
python scraper/scraper_worker.py \
  "https://eksisozluk.com/deprem--123456" \
  "data/test_state.json" \
  "data/test_output/"
```

## Key Features

### Automatic Lifecycle Management

- **Detector**: Never stops (unless you kill it)
- **Workers**: Self-terminate when no longer needed
- No process manager required
- No manual cleanup needed

### Duplicate Prevention

Workers use lock files to prevent multiple workers on same URL:
- Lock created when worker starts
- Lock removed when worker exits
- Detector checks lock before spawning

### Graceful Shutdown

Workers handle signals properly:
- SIGTERM/SIGINT → graceful shutdown
- Cleans up lock files
- Saves final state

### Failure Handling

Workers are resilient:
- Retry logic with exponential backoff
- Automatic state backups (last 5 versions)
- Partial scrape detection
- Auto-shutdown after too many failures

## Monitoring

### Check running workers:

```bash
# Find all worker processes
ps aux | grep scraper_worker

# Check worker logs
tail -f data/scrapers/*/worker.log

# See what's being scraped
ls -la data/scrapers/
```

### Check detector logs:

```bash
tail -f logs/gundem_monitor.log
```

## Example Scenario

1. **10:00** - Detector starts, monitoring gündem
2. **10:15** - Earthquake detected in İzmir
   - Detector logs event
   - Spawns Worker A for İzmir thread
3. **10:20** - Worker A scrapes (500 entries)
4. **10:25** - Worker A scrapes (523 entries, 23 new)
5. **10:30** - Another earthquake detected in İstanbul
   - Detector spawns Worker B for İstanbul thread
6. **10:35** - Worker A scrapes (0 entries)
   - **Worker A shuts down** (thread merged)
7. **10:40** - Worker B still scraping (150 entries)
8. Detector continues running forever...

## Configuration

### Detector (`earthquake_detector.py`):
- `POLL_INTERVAL = 30` - How often to check gündem (seconds)

### Worker (`scraper/scraper_worker.py`):
- `SCRAPE_INTERVAL = 300` - How often to scrape (5 minutes)
- `MAX_CONSECUTIVE_FAILURES = 3` - Exit after N failures

## Troubleshooting

### Worker not starting?
- Check if lock file exists: `ls data/scrapers/*/state.json.lock`
- Check detector logs for errors

### Worker not stopping?
- Check worker log: `tail data/scrapers/*/worker.log`
- Manually kill if needed: `kill <pid>`
- Lock file will be cleaned up

### Stale lock files?
- If system crashed, remove manually: `rm data/scrapers/*/state.json.lock`
