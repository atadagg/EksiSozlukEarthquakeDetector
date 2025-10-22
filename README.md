# Ekşi Sözlük Earthquake Detection System

Real-time earthquake detection by monitoring Ekşi Sözlük user activity.

## Concept

When earthquakes occur in Turkey, Ekşi Sözlük users immediately create başlıks following a consistent pattern:
- Format: `[day] [month] [year] [province] deprem`
- Example: `6 şubat 2025 kahramanmaraş depremi`

This system monitors the gündem (trending) page every 30 seconds to detect these başlıks as they appear.

## Features

- **Real-time Monitoring**: Polls gündem page every 30 seconds
- **Pattern Matching**: Detects earthquake başlıks using date + province pattern
- **Automatic Logging**: Saves detected events to JSON format
- **Low Bandwidth**: ~8 GB/month data usage
- **False Positive Prevention**: Uses word-boundary matching to avoid misidentification

## Project Structure

```
EksiSozlukEarthquakeDetector/
├── earthquake_detector.py      # Main monitoring system
├── earthquake_patterns.py      # Pattern matching logic
├── gundem_monitor.py          # Basic gündem poller
├── test_fetch.py              # Test script for gündem fetching
├── data/                      # Detected earthquake events (auto-created)
│   └── detected_events.jsonl
└── logs/                      # System logs (auto-created)
    └── gundem_monitor.log
```

## Requirements

```bash
pip install requests beautifulsoup4
```

## Usage

### Start Live Monitoring

```bash
python3 earthquake_detector.py
```

This will:
1. Poll https://eksisozluk.com/basliklar/gundem every 30 seconds
2. Check each başlık for earthquake patterns
3. Log detected earthquakes to `data/detected_events.jsonl`
4. Display alerts in console and save to `logs/gundem_monitor.log`

### Test Pattern Matching

```bash
python3 earthquake_patterns.py
```

### Test Gündem Fetching

```bash
python3 test_fetch.py
```

## Detection Pattern

The system looks for başlıks matching:
- **Day**: 1-31
- **Month**: Turkish month names (ocak, şubat, mart, etc.)
- **Year**: 2000-2099
- **Province**: One of 81 official Turkish provinces
- **Keywords** (optional): deprem, depremi, sarsıntı, zelzele

**Confidence Levels:**
- `high`: All components + earthquake keyword present
- `medium`: All components but no earthquake keyword

## Output Format

Detected events are saved to `data/detected_events.jsonl`:

```json
{
  "detected_at": "2025-10-21T23:50:45.585544",
  "baslik": {
    "title": "21 ekim 2023 izmir depremi",
    "url": "/21-ekim-2023-izmir-depremi--7730143?a=popular",
    "entry_count": "19",
    "timestamp": "2025-10-21T23:50:45.582252"
  },
  "earthquake_info": {
    "day": 21,
    "month": 10,
    "month_name": "ekim",
    "year": 2023,
    "province": "izmir",
    "has_earthquake_keyword": true,
    "confidence": "high"
  }
}
```

## Research Goals

1. **Speed Benchmark**: Compare detection time vs official alerts (AFAD/KOERI)
2. **Spatial Resolution**: Map earthquake impact at neighborhood level
3. **Damage Assessment**: Real-time reports from affected areas
4. **Historical Validation**: Test against past earthquakes (2000-2024)

## Next Steps

- [ ] Integrate with existing scraper for full entry collection
- [ ] Add NER for location extraction from entries
- [ ] Implement severity assessment using vocabulary analysis
- [ ] Build spike detection algorithm
- [ ] Collect historical data for validation
- [ ] Create validation framework

## Bandwidth Usage

- **30-second polling**: ~284 MB/day, ~8.3 GB/month
- **60-second polling**: ~142 MB/day, ~4.2 GB/month

## Notes

- Respects Ekşi Sözlük servers with reasonable polling intervals
- Uses word-boundary regex matching to prevent false positives
- Avoids duplicate alerts for the same earthquake event
- Logs all activity for later analysis
