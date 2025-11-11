# Eksi Sozluk Scraper (Functional + Diff Tracking)

Simple, functional Python scraper for Eksi Sozluk threads with diff tracking capabilities.

Designed to be called by other programs (like earthquake detection systems) to scrape and analyze specific threads.

## Features

- **Functional Programming**: Pure functions, no classes, easy to reason about
- **Diff Tracking**: Detects new entries, edits, and deletions
- **Simple Interface**: Command-line tool that outputs JSON
- **Composable**: Easy to integrate with other programs

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage (no diff tracking)

```bash
# Output to stdout
python scraper.py https://eksisozluk.com/topic-name--123456

# Save to file
python scraper.py https://eksisozluk.com/topic-name--123456 --output data.json
```

### Diff Tracking

Use `--state <file>` to enable diff tracking:

```bash
# First run: scrapes and saves state
python scraper.py https://eksisozluk.com/topic--123 --state state.json --output result.json

# Second run: compares with previous state, detects changes
python scraper.py https://eksisozluk.com/topic--123 --state state.json --output result.json
```

**Output includes:**
- Full current data
- Diff with: `new`, `edited`, `deleted` entries
- Summary counts

### Diff-Only Mode

To get only the changes (without full data):

```bash
python scraper.py https://eksisozluk.com/topic--123 --state state.json --diff-only
```

## Integration Examples

### Called by Earthquake Detector

```bash
#!/bin/bash
# When earthquake detected, analyze specific thread

THREAD_URL="https://eksisozluk.com/some-earthquake-topic--123456"
STATE_FILE="/var/earthquake-monitor/eksisozluk_state.json"

# Scrape with diff tracking
python scraper.py "$THREAD_URL" --state "$STATE_FILE" --diff-only > changes.json

# Process changes
if [ -s changes.json ]; then
    echo "New activity detected!"
    # Pass to your analyzer
    ./analyze_changes.py changes.json
fi
```

### From Python

```python
import subprocess
import json

url = "https://eksisozluk.com/topic--123456"
result = subprocess.run(
    ['python', 'scraper.py', url, '--state', 'state.json', '--diff-only'],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    diff = json.loads(result.stdout)
    print(f"New entries: {diff['summary']['new_count']}")
    print(f"Edited entries: {diff['summary']['edited_count']}")
    print(f"Deleted entries: {diff['summary']['deleted_count']}")
```

### Pipe to Another Program

```bash
python scraper.py <url> --state state.json --diff-only | jq '.new | length'
```

## Output Format

### Without State File (basic mode)

```json
[
  {
    "id": "123456789",
    "author": "username",
    "timestamp": "01.01.2023 12:34",
    "content": "entry content...",
    "scraped_at": "2025-01-09T12:34:56.789123"
  }
]
```

### With State File (diff tracking mode)

```json
{
  "entries": [...],  // Full current data
  "diff": {
    "new": [...],       // New entries
    "edited": [         // Edited entries
      {
        "id": "123",
        "author": "user",
        "previous": {
          "content": "old content",
          "timestamp": "01.01.2023"
        },
        "current": {
          "content": "new content",
          "timestamp": "02.01.2023"
        },
        "scraped_at": "2025-01-09T12:34:56"
      }
    ],
    "deleted": [...],   // Deleted entries
    "summary": {
      "new_count": 5,
      "edited_count": 2,
      "deleted_count": 1,
      "total_current": 100,
      "total_previous": 98
    }
  }
}
```

### Diff-Only Mode Output

```json
{
  "new": [...],
  "edited": [...],
  "deleted": [...],
  "summary": { ... }
}
```

## Diff Detection

The scraper detects three types of changes:

1. **New Entries**: Entries that exist in current scrape but not in previous state
2. **Edited Entries**: Entries where `content` or `timestamp` changed
3. **Deleted Entries**: Entries that existed in previous state but not in current scrape

## Exit Codes

- `0`: Success
- `1`: Failure (no entries found or error occurred)

## Design Philosophy

Built using functional programming principles:
- **Pure functions** for data extraction and transformation
- **Immutable data structures** throughout
- **Function composition** for the scraping pipeline
- **No classes or stateful objects**
- **Declarative diff computation** using set operations

This makes it:
- Easy to test
- Easy to reason about
- Easy to compose with other programs
- Minimal side effects (only I/O at boundaries)
