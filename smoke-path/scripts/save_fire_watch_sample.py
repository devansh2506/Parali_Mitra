"""Save a real fire watch response as the sample (GET /fires?sample=true, and the map
without ?api=), so the demo still works if NASA or Open-Meteo is down.

    python3.12 scripts/save_fire_watch_sample.py

Calls NASA FIRMS (FIRMS_MAP_KEY from smoke-path/.env) and Open-Meteo once, uses the saved
places snapshot, and writes:
  fixtures/fire_watch_sample.json
  src/smoke_path/fire_watch_sample.json   (packaged with the Lambda)
  frontend/data/sample-fires.js            (what the web app shows with no server; made by save_frontend_samples.py)
"""

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from _env import load_env  # noqa: E402

import save_frontend_samples  # noqa: E402
from smoke_path import firewatch  # noqa: E402
from smoke_path.apis import LiveApi  # noqa: E402

NAME = "fire_watch_sample.json"


def main():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    load_env()
    try:
        result = firewatch.run(firewatch.FireWatchRequest(hours=24), LiveApi.from_env(), budget_s=60)
    except (firewatch.NoFiresKey, firewatch.FiresUnavailable, firewatch.WindUnavailable) as err:
        print(f"Could not build the fire watch: {err}")
        return 2
    doc = result.report
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"  # compact: 1-2 MB of places
    (ROOT / "fixtures" / NAME).write_text(text, encoding="utf-8")
    (ROOT / "src" / "smoke_path" / NAME).write_text(text, encoding="utf-8")
    save_frontend_samples.main(["--offline"])
    for line in doc["summary"]:
        print("  " + line)
    for note in doc["notes"]:
        print("  note: " + note)
    print(f"  stats: {doc['stats']}")
    print(f"\nWrote fixtures/{NAME}, src/smoke_path/{NAME} and frontend/data/sample-fires.js")
    return 0


if __name__ == "__main__":
    sys.exit(main())
