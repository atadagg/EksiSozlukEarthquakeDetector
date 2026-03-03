"""
Live Earthquake Detection System
Monitors Ekşi Sözlük gündem every 30 seconds for earthquake başlıks
"""
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import json
import os
import sys
import subprocess
from pathlib import Path
from earthquake_patterns import is_earthquake_baslik

# Configuration
GUNDEM_URL = "https://eksisozluk.com/basliklar/gundem"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
POLL_INTERVAL = 30  # seconds
HEARTBEAT_INTERVAL = 2  # Log heartbeat every N fetches (120 fetches = 1 hour with 30s polling)

# Data directories
DATA_DIR = "data"
LOGS_DIR = "logs"
SCRAPER_DATA_DIR = os.path.join(DATA_DIR, "scrapers")
DETECTED_EVENTS_FILE = os.path.join(DATA_DIR, "detected_events.jsonl")
GUNDEM_LOG_FILE = os.path.join(LOGS_DIR, "gundem_monitor.log")
SCRAPER_WORKER_PATH = os.path.join("scraper", "scraper_worker.py")


def setup_directories():
    """Create data and logs directories"""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(SCRAPER_DATA_DIR, exist_ok=True)


def log_message(message: str, to_file: bool = True):
    """Log message to console and optionally to file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    print(log_line)

    if to_file:
        with open(GUNDEM_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')


def spawn_scraper_worker(url: str, url_path: str):
    """
    Spawn a scraper worker process for the given URL.
    Worker will run independently and shut down when entry count reaches 0.

    Args:
        url: Full URL (e.g. https://eksisozluk.com/deprem--123456)
        url_path: URL path after .com/ (e.g. deprem--123456)
    """
    # Use URL path as directory name (e.g. deprem--123456)
    # Strip leading slash if present
    dir_name = url_path.lstrip('/')
    thread_dir = os.path.join(SCRAPER_DATA_DIR, dir_name)
    os.makedirs(thread_dir, exist_ok=True)

    state_file = os.path.join(thread_dir, "state.json")
    output_dir = os.path.join(thread_dir, "diffs")

    # Check if a worker is already running for this URL by checking lock file
    lock_file = f"{state_file}.lock"
    if os.path.exists(lock_file):
        log_message(f"⚠️  Worker already running for {dir_name} (lock file exists)")
        return False

    try:
        # Spawn worker process (fire and forget)
        subprocess.Popen(
            [
                sys.executable,
                SCRAPER_WORKER_PATH,
                url,
                state_file,
                output_dir
            ],
            stdout=open(os.path.join(thread_dir, "worker.log"), 'a'),
            stderr=subprocess.STDOUT,
            start_new_session=True  # Detach from parent process
        )

        log_message(f"✓ Spawned scraper worker for {dir_name}")
        log_message(f"   Worker output: {thread_dir}/worker.log")
        return True

    except Exception as e:
        log_message(f"❌ Failed to spawn scraper worker: {e}")
        return False


def save_earthquake_event(baslik_data: dict, pattern_match: dict, earthquake_id: str):
    """Save detected earthquake event to file and spawn scraper worker"""
    event = {
        'detected_at': datetime.now().isoformat(),
        'baslik': baslik_data,
        'earthquake_info': pattern_match,
        'earthquake_id': earthquake_id
    }

    with open(DETECTED_EVENTS_FILE, 'a', encoding='utf-8') as f:
        json.dump(event, f, ensure_ascii=False)
        f.write('\n')

    log_message(f"🚨 EARTHQUAKE DETECTED: {pattern_match['day']} {pattern_match['month_name']} "
                f"{pattern_match['year']} - {pattern_match['province'].upper()}")
    log_message(f"   Başlık: {baslik_data['title']}")
    log_message(f"   URL: https://eksisozluk.com{baslik_data['url']}")
    log_message(f"   Entry count: {baslik_data['entry_count']}")
    log_message(f"   Confidence: {pattern_match['confidence']}")

    # Spawn scraper worker to monitor this thread
    # Remove query parameters like ?a=popular before passing to scraper
    clean_url_path = baslik_data['url'].split('?')[0]
    full_url = f"https://eksisozluk.com{clean_url_path}"
    spawn_scraper_worker(full_url, clean_url_path)


def fetch_gundem():
    """Fetch gündem page and extract all başlıks"""
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(GUNDEM_URL, headers=headers, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        topic_list = soup.find('ul', class_='topic-list')

        if not topic_list:
            log_message("⚠️  Could not find topic-list")
            return []

        basliks = []
        for li in topic_list.find_all('li'):
            a_tag = li.find('a')
            if a_tag and a_tag.get('href'):
                title = a_tag.get_text(strip=True)
                small_tag = a_tag.find('small')
                if small_tag:
                    entry_count = small_tag.get_text(strip=True)
                    title = title.replace(entry_count, '').strip()
                else:
                    entry_count = "0"

                url = a_tag.get('href')
                basliks.append({
                    'title': title,
                    'url': url,
                    'entry_count': entry_count,
                    'timestamp': datetime.now().isoformat()
                })

        return basliks

    except requests.exceptions.RequestException as e:
        log_message(f"❌ HTTP error: {e}")
        return []
    except Exception as e:
        log_message(f"❌ Error: {e}")
        return []


def monitor_earthquakes():
    """Main monitoring loop"""
    setup_directories()

    log_message("=" * 50)
    log_message("    Ekşi Sözlük Earthquake Detection System STARTED")
    log_message(f"   Polling interval: {POLL_INTERVAL} seconds")
    log_message(f"   Heartbeat interval: every {HEARTBEAT_INTERVAL} fetches (~{HEARTBEAT_INTERVAL * POLL_INTERVAL // 60} minutes)")
    log_message(f"   Monitoring: {GUNDEM_URL}")
    log_message("=" * 50)

    detected_earthquakes = set()  # Track already detected earthquakes to avoid duplicates
    fetch_count = 0

    while True:
        try:
            basliks = fetch_gundem()
            fetch_count += 1

            if basliks:
                # Heartbeat: log every N fetches to show system is alive
                if fetch_count % HEARTBEAT_INTERVAL == 0:
                    log_message(f"System healthy: {fetch_count} checks completed, monitoring continues...")

                # Check each başlık for earthquake pattern
                for baslik in basliks:
                    pattern_match = is_earthquake_baslik(baslik['title'])

                    if pattern_match:
                        # Create unique ID for this earthquake event
                        earthquake_id = f"{pattern_match['day']}-{pattern_match['month']}-{pattern_match['year']}-{pattern_match['province']}"

                        # Only alert if we haven't seen this earthquake before
                        if earthquake_id not in detected_earthquakes:
                            save_earthquake_event(baslik, pattern_match, earthquake_id)
                            detected_earthquakes.add(earthquake_id)

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log_message("=" * 80)
            log_message(f"🛑 Monitoring stopped by user (completed {fetch_count} checks)")
            log_message("=" * 80)
            break
        except Exception as e:
            log_message(f"❌ Unexpected error in main loop: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    monitor_earthquakes()
