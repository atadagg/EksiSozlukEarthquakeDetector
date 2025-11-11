#!/usr/bin/env python3
"""
Production-hardened Eksi Sozluk scraper with diff tracking.
Built for critical infrastructure - lives depend on reliability.

Usage: python scraper.py <url> [--output <file>] [--state <file>] [--diff-only]
"""

import sys
import json
import os
import time
import hashlib
import fcntl
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from contextlib import contextmanager

import requests
from bs4 import BeautifulSoup


# ============================================================================
# Configuration
# ============================================================================

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # Exponential backoff: 2^retry_count seconds
REQUEST_TIMEOUT = 20
STATE_BACKUP_COUNT = 5  # Keep last 5 state backups


# ============================================================================
# Lock File Management (Prevent Concurrent Runs)
# ============================================================================

@contextmanager
def acquire_lock(lock_file: str):
    """Acquire exclusive lock to prevent concurrent scraper runs."""
    lock_path = Path(lock_file)
    lock_fd = None

    try:
        # Create lock file
        lock_fd = open(lock_path, 'w')

        # Try to acquire exclusive lock (non-blocking)
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("ERROR: Another scraper instance is already running", file=sys.stderr)
            print("If this is incorrect, remove lock file:", lock_path, file=sys.stderr)
            sys.exit(2)

        # Write PID to lock file
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()

        yield lock_fd

    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
                lock_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"Warning: Error releasing lock: {e}", file=sys.stderr)


# ============================================================================
# Pure Functions - Data Extraction with Retry Logic
# ============================================================================

def fetch_html_with_retry(url: str, headers: Dict[str, str], max_retries: int = MAX_RETRIES) -> Optional[str]:
    """Fetch HTML with exponential backoff retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text

        except requests.exceptions.RequestException as e:
            wait_time = RETRY_BACKOFF_BASE ** attempt

            if attempt < max_retries - 1:
                print(f"  Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}", file=sys.stderr)
                time.sleep(wait_time)
            else:
                print(f"  Failed after {max_retries} attempts: {e}", file=sys.stderr)
                return None

    return None


def parse_html(html: str) -> BeautifulSoup:
    """Parse HTML string into BeautifulSoup object."""
    return BeautifulSoup(html, 'html.parser')


def get_page_count(soup: BeautifulSoup) -> int:
    """Extract total page count from pagination."""
    pager = soup.find('div', class_='pager')
    if not pager or 'data-pagecount' not in pager.attrs:
        return 1
    try:
        return int(pager['data-pagecount'])
    except ValueError:
        return 1


def extract_entry(entry_element) -> Optional[Dict]:
    """Extract entry data from HTML element."""
    entry_id = entry_element.get('data-id')
    if not entry_id:
        return None

    content_div = entry_element.find('div', class_='content')
    date_link = entry_element.find('a', class_='entry-date')

    return {
        'id': entry_id,
        'author': entry_element.get('data-author', 'N/A'),
        'timestamp': date_link.get_text(strip=True) if date_link else 'N/A',
        'content': content_div.get_text(separator='\n', strip=True) if content_div else 'N/A',
        'scraped_at': datetime.now().isoformat()
    }


def extract_entries_from_page(soup: BeautifulSoup) -> List[Dict]:
    """Extract all entries from a single page."""
    entry_list = soup.find('ul', id='entry-item-list')
    if not entry_list:
        return []

    entry_elements = entry_list.find_all('li', attrs={'data-id': True})
    entries = [extract_entry(elem) for elem in entry_elements]
    return [e for e in entries if e is not None]


def build_page_urls(base_url: str, page_count: int) -> List[str]:
    """Generate list of URLs for all pages."""
    if page_count == 1:
        return [base_url]
    return [f"{base_url}?p={page}" for page in range(1, page_count + 1)]


# ============================================================================
# Data Validation
# ============================================================================

def validate_entry(entry: Dict) -> bool:
    """Validate that entry has required fields and proper structure."""
    required_fields = ['id', 'author', 'timestamp', 'content', 'scraped_at']

    if not all(field in entry for field in required_fields):
        return False

    if not isinstance(entry['id'], str) or not entry['id']:
        return False

    if not isinstance(entry['content'], str):
        return False

    return True


def validate_entries(entries: List[Dict]) -> Tuple[List[Dict], List[str]]:
    """Validate all entries and return valid ones plus error list."""
    valid_entries = []
    errors = []

    seen_ids = set()

    for entry in entries:
        if not validate_entry(entry):
            errors.append(f"Invalid entry structure: {entry.get('id', 'unknown')}")
            continue

        # Check for duplicate IDs
        if entry['id'] in seen_ids:
            errors.append(f"Duplicate entry ID: {entry['id']}")
            continue

        seen_ids.add(entry['id'])
        valid_entries.append(entry)

    return valid_entries, errors


# ============================================================================
# Atomic State Management with Backups
# ============================================================================

def load_state(state_file: str) -> Dict[str, Dict]:
    """Load previous scrape state from file. Returns dict keyed by entry ID."""
    if not Path(state_file).exists():
        return {}

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            entries = json.load(f)

            # Validate structure
            if not isinstance(entries, list):
                print(f"Warning: State file has invalid format, ignoring", file=sys.stderr)
                return {}

            return {entry['id']: entry for entry in entries if validate_entry(entry)}
    except Exception as e:
        print(f"Error loading state file: {e}", file=sys.stderr)
        # Try to load from backup
        return load_state_from_backup(state_file)


def load_state_from_backup(state_file: str) -> Dict[str, Dict]:
    """Try to load state from backup files."""
    for i in range(1, STATE_BACKUP_COUNT + 1):
        backup_file = f"{state_file}.backup.{i}"
        if Path(backup_file).exists():
            try:
                print(f"Attempting to load from backup: {backup_file}", file=sys.stderr)
                with open(backup_file, 'r', encoding='utf-8') as f:
                    entries = json.load(f)
                    if isinstance(entries, list):
                        print(f"Successfully loaded from backup {i}", file=sys.stderr)
                        return {entry['id']: entry for entry in entries if validate_entry(entry)}
            except Exception as e:
                print(f"Backup {i} also corrupted: {e}", file=sys.stderr)
                continue

    print("All backups failed, starting fresh", file=sys.stderr)
    return {}


def rotate_backups(state_file: str):
    """Rotate backup files (keep last N versions)."""
    state_path = Path(state_file)

    if not state_path.exists():
        return

    # Rotate existing backups
    for i in range(STATE_BACKUP_COUNT - 1, 0, -1):
        old_backup = Path(f"{state_file}.backup.{i}")
        new_backup = Path(f"{state_file}.backup.{i + 1}")

        if old_backup.exists():
            old_backup.rename(new_backup)

    # Create new backup from current state
    backup_path = Path(f"{state_file}.backup.1")
    try:
        import shutil
        shutil.copy2(state_path, backup_path)
    except Exception as e:
        print(f"Warning: Failed to create backup: {e}", file=sys.stderr)


def save_state_atomic(entries: List[Dict], state_file: str) -> bool:
    """Save state atomically using temp file + rename."""
    try:
        # Validate before saving
        valid_entries, errors = validate_entries(entries)

        if errors:
            print(f"Warning: {len(errors)} validation errors found:", file=sys.stderr)
            for error in errors[:5]:  # Show first 5
                print(f"  - {error}", file=sys.stderr)

        if not valid_entries:
            print("ERROR: No valid entries to save!", file=sys.stderr)
            return False

        # Rotate backups before writing new state
        rotate_backups(state_file)

        # Write to temporary file
        temp_file = f"{state_file}.tmp.{os.getpid()}"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(valid_entries, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename
        os.rename(temp_file, state_file)

        return True

    except Exception as e:
        print(f"ERROR: Failed to save state: {e}", file=sys.stderr)
        # Clean up temp file if it exists
        try:
            Path(f"{state_file}.tmp.{os.getpid()}").unlink(missing_ok=True)
        except:
            pass
        return False


# ============================================================================
# Pure Functions - Diff Computation
# ============================================================================

def compute_diff(current_entries: List[Dict], previous_state: Dict[str, Dict]) -> Dict:
    """
    Compute differences between current and previous scrape.
    Returns dict with 'new', 'edited', 'deleted' entries.
    """
    current_by_id = {entry['id']: entry for entry in current_entries}
    current_ids = set(current_by_id.keys())
    previous_ids = set(previous_state.keys())

    # New entries: in current but not in previous
    new_ids = current_ids - previous_ids
    new_entries = [current_by_id[eid] for eid in new_ids]

    # Deleted entries: in previous but not in current
    deleted_ids = previous_ids - current_ids
    deleted_entries = [previous_state[eid] for eid in deleted_ids]

    # Edited entries: in both, but content or timestamp changed
    common_ids = current_ids & previous_ids
    edited_entries = []

    for eid in common_ids:
        curr = current_by_id[eid]
        prev = previous_state[eid]

        # Check if content or timestamp changed
        if curr['content'] != prev['content'] or curr['timestamp'] != prev['timestamp']:
            edited_entries.append({
                'id': eid,
                'author': curr['author'],
                'previous': {
                    'content': prev['content'],
                    'timestamp': prev['timestamp']
                },
                'current': {
                    'content': curr['content'],
                    'timestamp': curr['timestamp']
                },
                'scraped_at': curr['scraped_at']
            })

    return {
        'new': new_entries,
        'edited': edited_entries,
        'deleted': deleted_entries,
        'summary': {
            'new_count': len(new_entries),
            'edited_count': len(edited_entries),
            'deleted_count': len(deleted_entries),
            'total_current': len(current_entries),
            'total_previous': len(previous_state)
        }
    }


# ============================================================================
# Composition Functions with Failure Tracking
# ============================================================================

def scrape_page(url: str, headers: Dict[str, str]) -> Tuple[List[Dict], bool]:
    """
    Scrape entries from a single page.
    Returns (entries, success_flag).
    """
    html = fetch_html_with_retry(url, headers)
    if not html:
        return [], False

    soup = parse_html(html)
    entries = extract_entries_from_page(soup)
    return entries, True


def scrape_all_pages(base_url: str, headers: Dict[str, str]) -> Tuple[List[Dict], Dict]:
    """
    Scrape all pages of a thread.
    Returns (entries, metadata) where metadata includes failure info.
    """
    metadata = {
        'total_pages': 0,
        'successful_pages': 0,
        'failed_pages': 0,
        'partial_scrape': False,
        'start_time': datetime.now().isoformat(),
        'end_time': None
    }

    # Fetch first page to get page count
    html = fetch_html_with_retry(base_url, headers)
    if not html:
        metadata['end_time'] = datetime.now().isoformat()
        return [], metadata

    soup = parse_html(html)
    page_count = get_page_count(soup)
    metadata['total_pages'] = page_count

    print(f"Found {page_count} page(s)", file=sys.stderr)

    # Build URLs and scrape each page
    urls = build_page_urls(base_url, page_count)

    all_entries = []
    for i, url in enumerate(urls, 1):
        print(f"Scraping page {i}/{page_count}...", file=sys.stderr)
        entries, success = scrape_page(url, headers)

        if success:
            all_entries.extend(entries)
            metadata['successful_pages'] += 1
            print(f"  Found {len(entries)} entries", file=sys.stderr)
        else:
            metadata['failed_pages'] += 1
            print(f"  FAILED to scrape page {i}", file=sys.stderr)

    # Mark as partial if any pages failed
    if metadata['failed_pages'] > 0:
        metadata['partial_scrape'] = True
        print(f"\nWARNING: Partial scrape! {metadata['failed_pages']}/{page_count} pages failed", file=sys.stderr)

    metadata['end_time'] = datetime.now().isoformat()
    return all_entries, metadata


# ============================================================================
# Output Functions
# ============================================================================

def format_json(data: any) -> str:
    """Format data as JSON string."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def write_output_atomic(data: str, output_file: str) -> bool:
    """Write output atomically using temp file + rename."""
    try:
        temp_file = f"{output_file}.tmp.{os.getpid()}"

        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        os.rename(temp_file, output_file)
        return True

    except Exception as e:
        print(f"ERROR: Failed to write output: {e}", file=sys.stderr)
        try:
            Path(temp_file).unlink(missing_ok=True)
        except:
            pass
        return False


def write_output(data: str, output_file: Optional[str] = None) -> bool:
    """Write data to file or stdout."""
    if output_file:
        success = write_output_atomic(data, output_file)
        if success:
            print(f"Output written to {output_file}", file=sys.stderr)
        return success
    else:
        print(data)
        return True


# ============================================================================
# Configuration
# ============================================================================

def get_headers() -> Dict[str, str]:
    """Get HTTP headers for requests."""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }


def parse_args(args: List[str]) -> Optional[Dict]:
    """Parse command line arguments."""
    if len(args) < 2:
        return None

    config = {
        'url': args[1],
        'output_file': None,
        'state_file': None,
        'diff_only': False,
        'lock_file': None
    }

    i = 2
    while i < len(args):
        if args[i] == '--output' and i + 1 < len(args):
            config['output_file'] = args[i + 1]
            i += 2
        elif args[i] == '--state' and i + 1 < len(args):
            config['state_file'] = args[i + 1]
            # Auto-generate lock file path from state file
            config['lock_file'] = f"{args[i + 1]}.lock"
            i += 2
        elif args[i] == '--diff-only':
            config['diff_only'] = True
            i += 1
        else:
            i += 1

    return config


# ============================================================================
# Main Pipeline
# ============================================================================

def main():
    """Main entry point."""
    config = parse_args(sys.argv)

    if not config:
        print("Usage: python scraper.py <url> [options]", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("  --output <file>    Write output to file (default: stdout)", file=sys.stderr)
        print("  --state <file>     State file for diff tracking (enables locking)", file=sys.stderr)
        print("  --diff-only        Output only the diff (not full data)", file=sys.stderr)
        print("\nProduction Features:", file=sys.stderr)
        print("  • Atomic file writes (no corruption on crash)", file=sys.stderr)
        print("  • Automatic state backups (last 5 versions)", file=sys.stderr)
        print("  • Retry logic with exponential backoff", file=sys.stderr)
        print("  • Lock files prevent concurrent runs", file=sys.stderr)
        print("  • Data validation before saving", file=sys.stderr)
        print("  • Partial scrape detection", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  python scraper.py https://eksisozluk.com/topic--123456", file=sys.stderr)
        print("  python scraper.py https://eksisozluk.com/topic--123456 --output data.json", file=sys.stderr)
        print("  python scraper.py https://eksisozluk.com/topic--123456 --state state.json --diff-only", file=sys.stderr)
        sys.exit(1)

    url = config['url']
    output_file = config['output_file']
    state_file = config['state_file']
    diff_only = config['diff_only']
    lock_file = config['lock_file']

    # Acquire lock if using state file (prevents concurrent runs)
    lock_context = acquire_lock(lock_file) if lock_file else contextmanager(lambda: (yield None))()

    with lock_context:
        print(f"Scraping: {url}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        # Pipeline: scrape -> validate -> compute diff -> save state -> output
        headers = get_headers()
        current_entries, metadata = scrape_all_pages(url, headers)

        print("=" * 60, file=sys.stderr)
        print(f"Total entries scraped: {len(current_entries)}", file=sys.stderr)

        if not current_entries:
            print("ERROR: No entries found", file=sys.stderr)
            sys.exit(1)

        # Validate entries
        valid_entries, validation_errors = validate_entries(current_entries)

        if not valid_entries:
            print("ERROR: No valid entries after validation", file=sys.stderr)
            sys.exit(1)

        # If state file provided, compute diff
        if state_file:
            print(f"Loading previous state from: {state_file}", file=sys.stderr)
            previous_state = load_state(state_file)

            if previous_state:
                print(f"Previous state: {len(previous_state)} entries", file=sys.stderr)
                diff = compute_diff(valid_entries, previous_state)

                print("\nDiff Summary:", file=sys.stderr)
                print(f"  New entries:     {diff['summary']['new_count']}", file=sys.stderr)
                print(f"  Edited entries:  {diff['summary']['edited_count']}", file=sys.stderr)
                print(f"  Deleted entries: {diff['summary']['deleted_count']}", file=sys.stderr)

                # Save updated state atomically
                if not save_state_atomic(valid_entries, state_file):
                    print("ERROR: Failed to save state", file=sys.stderr)
                    sys.exit(1)

                print(f"State updated: {state_file}", file=sys.stderr)

                # Output diff or full data based on flag
                if diff_only:
                    output_data = {
                        **diff,
                        'metadata': metadata
                    }
                else:
                    output_data = {
                        'entries': valid_entries,
                        'diff': diff,
                        'metadata': metadata
                    }
            else:
                print("No previous state found. This is the first run.", file=sys.stderr)

                # Save initial state atomically
                if not save_state_atomic(valid_entries, state_file):
                    print("ERROR: Failed to save initial state", file=sys.stderr)
                    sys.exit(1)

                print(f"Initial state saved: {state_file}", file=sys.stderr)
                output_data = {
                    'entries': valid_entries,
                    'diff': None,
                    'metadata': metadata
                }
        else:
            # No state file, just output current entries
            output_data = {
                'entries': valid_entries,
                'metadata': metadata
            }

        # Add warning if partial scrape
        if metadata['partial_scrape']:
            print("\n⚠️  WARNING: PARTIAL SCRAPE DETECTED", file=sys.stderr)
            print(f"⚠️  {metadata['failed_pages']} pages failed to scrape", file=sys.stderr)
            print("⚠️  Data may be incomplete - use with caution", file=sys.stderr)

        # Output results
        json_output = format_json(output_data)
        if not write_output(json_output, output_file):
            sys.exit(1)

        # Exit with code 2 if partial scrape (warning)
        if metadata['partial_scrape']:
            sys.exit(2)

        sys.exit(0)


if __name__ == '__main__':
    main()
