#!/usr/bin/env python3
"""
Demo showing diff tracking output with mock data
"""

import json
from datetime import datetime

# Simulate "previous state" (3 entries)
previous_entries = [
    {
        "id": "001",
        "author": "user1",
        "timestamp": "09.11.2025 15:30",
        "content": "deprem hissettim istanbul'da",
        "scraped_at": "2025-11-09T15:35:00"
    },
    {
        "id": "002",
        "author": "user2",
        "timestamp": "09.11.2025 15:31",
        "content": "çok şiddetli bir sarsıntı oldu",
        "scraped_at": "2025-11-09T15:35:00"
    },
    {
        "id": "003",
        "author": "user3",
        "timestamp": "09.11.2025 15:32",
        "content": "kandilli açıklama yapacak mı acaba",
        "scraped_at": "2025-11-09T15:35:00"
    }
]

# Simulate "current state" (5 entries - with changes!)
current_entries = [
    {
        "id": "001",
        "author": "user1",
        "timestamp": "09.11.2025 15:30",
        "content": "deprem hissettim istanbul'da",
        "scraped_at": "2025-11-09T15:40:00"
    },
    # Entry 002 was EDITED (content changed)
    {
        "id": "002",
        "author": "user2",
        "timestamp": "09.11.2025 15:31",
        "content": "çok şiddetli bir sarsıntı oldu. edit: 5.8 büyüklüğündeymiş",
        "scraped_at": "2025-11-09T15:40:00"
    },
    # Entry 003 was DELETED (not in current_entries)
    # Entry 004 is NEW
    {
        "id": "004",
        "author": "user4",
        "timestamp": "09.11.2025 15:38",
        "content": "merkez üssü ege denizi açıkları",
        "scraped_at": "2025-11-09T15:40:00"
    },
    # Entry 005 is NEW
    {
        "id": "005",
        "author": "user5",
        "timestamp": "09.11.2025 15:39",
        "content": "artçı sarsıntılar devam ediyor",
        "scraped_at": "2025-11-09T15:40:00"
    }
]

def compute_diff(current, previous):
    """Same algorithm as in scraper.py"""
    current_by_id = {e['id']: e for e in current}
    previous_by_id = {e['id']: e for e in previous}

    current_ids = set(current_by_id.keys())
    previous_ids = set(previous_by_id.keys())

    # New entries
    new_ids = current_ids - previous_ids
    new_entries = [current_by_id[eid] for eid in new_ids]

    # Deleted entries
    deleted_ids = previous_ids - current_ids
    deleted_entries = [previous_by_id[eid] for eid in deleted_ids]

    # Edited entries
    common_ids = current_ids & previous_ids
    edited_entries = []

    for eid in common_ids:
        curr = current_by_id[eid]
        prev = previous_by_id[eid]

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
            'total_current': len(current),
            'total_previous': len(previous)
        }
    }

# Compute diff
diff = compute_diff(current_entries, previous_entries)

# Pretty print
print("=" * 70)
print("DIFF TRACKING DEMONSTRATION")
print("=" * 70)
print()
print(f"Previous scrape: {diff['summary']['total_previous']} entries")
print(f"Current scrape:  {diff['summary']['total_current']} entries")
print()
print(f"📝 NEW entries:     {diff['summary']['new_count']}")
print(f"✏️  EDITED entries:  {diff['summary']['edited_count']}")
print(f"🗑️  DELETED entries: {diff['summary']['deleted_count']}")
print()

if diff['new']:
    print("=" * 70)
    print("NEW ENTRIES:")
    print("=" * 70)
    for entry in diff['new']:
        print(f"\n[ID: {entry['id']}] by {entry['author']} at {entry['timestamp']}")
        print(f"Content: {entry['content']}")

if diff['edited']:
    print()
    print("=" * 70)
    print("EDITED ENTRIES:")
    print("=" * 70)
    for entry in diff['edited']:
        print(f"\n[ID: {entry['id']}] by {entry['author']}")
        print(f"BEFORE: {entry['previous']['content']}")
        print(f"AFTER:  {entry['current']['content']}")

if diff['deleted']:
    print()
    print("=" * 70)
    print("DELETED ENTRIES:")
    print("=" * 70)
    for entry in diff['deleted']:
        print(f"\n[ID: {entry['id']}] by {entry['author']}")
        print(f"Content: {entry['content']}")

print()
print("=" * 70)
print("FULL JSON OUTPUT:")
print("=" * 70)
print(json.dumps(diff, ensure_ascii=False, indent=2))
