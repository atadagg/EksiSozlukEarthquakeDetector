#!/usr/bin/env python3
"""
Simple test to demonstrate diff tracking functionality.
This simulates how your earthquake detector would use the scraper.
"""

import json
import subprocess
import sys

def run_scraper(url, state_file=None, diff_only=False):
    """Helper to run the scraper and parse output."""
    cmd = ['python', 'scraper.py', url]

    if state_file:
        cmd.extend(['--state', state_file])

    if diff_only:
        cmd.append('--diff-only')

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Print stderr (progress messages)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"Error: Scraper failed", file=sys.stderr)
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON output", file=sys.stderr)
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_diff.py <eksisozluk_url>")
        print("\nExample:")
        print("  python test_diff.py https://eksisozluk.com/topic--123456")
        sys.exit(1)

    url = sys.argv[1]
    state_file = "test_state.json"

    print("=" * 70)
    print("DIFF TRACKING DEMONSTRATION")
    print("=" * 70)
    print()

    # First run
    print(">>> FIRST RUN: Creating initial state")
    print("-" * 70)
    data = run_scraper(url, state_file=state_file)

    if not data:
        print("Failed to scrape. Exiting.")
        sys.exit(1)

    entries = data.get('entries', [])
    print(f"\n✓ Scraped {len(entries)} entries")
    print(f"✓ State saved to {state_file}")
    print()

    # Second run (should show no changes if immediate)
    print(">>> SECOND RUN: Checking for changes (diff-only mode)")
    print("-" * 70)
    diff = run_scraper(url, state_file=state_file, diff_only=True)

    if not diff:
        print("Failed to get diff. Exiting.")
        sys.exit(1)

    summary = diff.get('summary', {})
    print()
    print("DIFF SUMMARY:")
    print(f"  New entries:     {summary.get('new_count', 0)}")
    print(f"  Edited entries:  {summary.get('edited_count', 0)}")
    print(f"  Deleted entries: {summary.get('deleted_count', 0)}")
    print(f"  Total current:   {summary.get('total_current', 0)}")
    print(f"  Total previous:  {summary.get('total_previous', 0)}")
    print()

    # Show details if there are changes
    if summary.get('new_count', 0) > 0:
        print(f"\n{summary['new_count']} NEW ENTRIES:")
        for entry in diff['new'][:3]:  # Show first 3
            print(f"  - ID {entry['id']} by {entry['author']}")
            print(f"    {entry['content'][:80]}...")

    if summary.get('edited_count', 0) > 0:
        print(f"\n{summary['edited_count']} EDITED ENTRIES:")
        for entry in diff['edited'][:3]:  # Show first 3
            print(f"  - ID {entry['id']} by {entry['author']}")
            print(f"    Changed from {len(entry['previous']['content'])} to {len(entry['current']['content'])} chars")

    if summary.get('deleted_count', 0) > 0:
        print(f"\n{summary['deleted_count']} DELETED ENTRIES:")
        for entry in diff['deleted'][:3]:  # Show first 3
            print(f"  - ID {entry['id']} by {entry['author']}")

    print()
    print("=" * 70)
    print("HOW YOUR EARTHQUAKE DETECTOR WOULD USE THIS:")
    print("=" * 70)
    print("""
1. When earthquake detected:
   result = subprocess.run(['python', 'scraper.py', url, '--state', 'state.json', '--diff-only'], ...)

2. Parse the diff JSON:
   diff = json.loads(result.stdout)

3. Analyze changes:
   - New entries → people posting about the earthquake
   - Edited entries → people updating their posts
   - Use diff['new'], diff['edited'] for your NLP analysis

4. Track over time:
   - Each call updates the state file automatically
   - Next call will show only NEW changes since last call
""")


if __name__ == '__main__':
    main()
