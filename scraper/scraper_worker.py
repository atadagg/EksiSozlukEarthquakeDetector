#!/usr/bin/env python3
"""
Scraper Worker - Periodically scrapes an Ekşi Sözlük thread until entry count reaches 0.

This worker runs as a separate process, scraping a specific URL every 5 minutes.
It automatically shuts down when the thread has been merged (entry count = 0).

Usage: python scraper_worker.py <url> <state_file> <output_dir>
"""

import sys
import time
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
import signal

# Configuration
SCRAPE_INTERVAL = 300  # 5 minutes in seconds
MAX_CONSECUTIVE_FAILURES = None  # Never give up - keep trying forever

class ScraperWorker:
    def __init__(self, url: str, state_file: str, output_dir: str):
        self.url = url
        self.state_file = state_file
        self.output_dir = output_dir
        self.consecutive_failures = 0
        self.running = True

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        self.log(f"Worker started for URL: {url}")
        self.log(f"State file: {state_file}")
        self.log(f"Output directory: {output_dir}")
        self.log(f"Scrape interval: {SCRAPE_INTERVAL} seconds")

    def log(self, message: str):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [Worker-{os.getpid()}] {message}"
        print(log_line, flush=True)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.log(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def get_entry_count(self) -> int:
        """
        Scrape the URL and return the current entry count.
        Returns -1 if scraping failed.
        """
        try:
            # Get the path to scraper.py
            scraper_path = Path(__file__).parent / "scraper.py"

            # Run scraper with state tracking and diff-only mode
            result = subprocess.run(
                [
                    sys.executable,
                    str(scraper_path),
                    self.url,
                    '--state', self.state_file,
                    '--diff-only'
                ],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for scraping
            )

            # Parse the output
            if result.returncode == 0 or result.returncode == 2:  # 0 = success, 2 = partial scrape
                data = json.loads(result.stdout)

                # Save diff to output directory if there are changes
                if data.get('summary', {}).get('new_count', 0) > 0:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    diff_file = Path(self.output_dir) / f"diff_{timestamp}.json"
                    with open(diff_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self.log(f"New entries detected! Saved to: {diff_file}")

                # Get total current entry count from summary
                total_entries = data.get('summary', {}).get('total_current', -1)

                if total_entries >= 0:
                    self.log(f"Current entry count: {total_entries}")
                    return total_entries
                else:
                    self.log("Warning: Could not determine entry count from scraper output")
                    return -1
            else:
                self.log(f"Scraper failed with exit code {result.returncode}")
                if result.stderr:
                    self.log(f"Error: {result.stderr[:500]}")  # Log first 500 chars
                return -1

        except subprocess.TimeoutExpired:
            self.log("Error: Scraper timeout after 2 minutes")
            return -1
        except json.JSONDecodeError as e:
            self.log(f"Error: Failed to parse scraper output: {e}")
            return -1
        except Exception as e:
            self.log(f"Error: Unexpected error during scraping: {e}")
            return -1

    def run(self):
        """Main worker loop."""
        self.log("Starting scraper worker loop...")

        iteration = 0

        while self.running:
            iteration += 1
            self.log(f"--- Scrape iteration #{iteration} ---")

            entry_count = self.get_entry_count()

            if entry_count == -1:
                # Scraping failed
                self.consecutive_failures += 1
                if MAX_CONSECUTIVE_FAILURES is not None:
                    self.log(f"Scraping failed ({self.consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})")
                    if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        self.log(f"Too many consecutive failures ({MAX_CONSECUTIVE_FAILURES}). Shutting down.")
                        break
                else:
                    self.log(f"Scraping failed (attempt #{self.consecutive_failures}) - will keep retrying indefinitely")

            elif entry_count == 0:
                # Thread has been merged - shut down
                self.log("Entry count is 0 - thread has been merged. Shutting down worker.")
                break

            else:
                # Success - reset failure counter
                self.consecutive_failures = 0
                self.log(f"Thread is active with {entry_count} entries. Continuing to monitor...")

            # Wait for next iteration (unless shutting down)
            if self.running:
                self.log(f"Sleeping for {SCRAPE_INTERVAL} seconds until next scrape...")

                # Sleep in small chunks to allow for responsive shutdown
                sleep_chunks = SCRAPE_INTERVAL // 10
                for _ in range(10):
                    if not self.running:
                        break
                    time.sleep(sleep_chunks)

        self.log("Worker shutting down.")
        self.log(f"Total iterations completed: {iteration}")


def main():
    """Main entry point."""
    if len(sys.argv) != 4:
        print("Usage: python scraper_worker.py <url> <state_file> <output_dir>", file=sys.stderr)
        print("\nArguments:", file=sys.stderr)
        print("  url          The Ekşi Sözlük thread URL to scrape", file=sys.stderr)
        print("  state_file   Path to state file for diff tracking", file=sys.stderr)
        print("  output_dir   Directory to save diff outputs", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  python scraper_worker.py https://eksisozluk.com/deprem--123456 \\", file=sys.stderr)
        print("         data/thread_123456_state.json data/thread_123456/", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    state_file = sys.argv[2]
    output_dir = sys.argv[3]

    worker = ScraperWorker(url, state_file, output_dir)
    worker.run()

    sys.exit(0)


if __name__ == '__main__':
    main()
