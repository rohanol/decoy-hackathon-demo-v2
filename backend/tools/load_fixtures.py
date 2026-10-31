"""Post a fixture file to a running backend (dev only, replay data).

Run from dg-soc/:
    python -m backend.tools.load_fixtures                       # contracts/examples/events_p3.json
    python -m backend.tools.load_fixtures --file other.json --url http://127.0.0.1:8000
Files with more than 100 events are sent in batches of 100.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_FILE = Path(__file__).resolve().parents[2] / "contracts" / "examples" / "events_p3.json"
BATCH = 100


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Post a fixture file to a running backend.")
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE, help='JSON file with {"events": [...]}')
    ap.add_argument("--url", default=DEFAULT_URL, help="backend base URL")
    args = ap.parse_args(argv)

    events = json.loads(args.file.read_text(encoding="utf-8"))["events"]
    url = args.url.rstrip("/") + "/api/ingest/events"
    for start in range(0, len(events), BATCH):
        req = urllib.request.Request(
            url, data=json.dumps({"events": events[start:start + BATCH]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(resp.status, resp.read().decode())
        except urllib.error.HTTPError as e:
            print(e.code, e.read().decode(), file=sys.stderr)
            return 1
        except OSError as e:
            print(f"could not reach {url}: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
