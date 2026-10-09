"""Load smoke-path/.env into the environment for the local scripts.

Standard library only. Lines look like `FIRMS_MAP_KEY=abc123` (quotes, `export`
and `# comments` are fine). Variables already set in the shell win over the
file. Lambda does not use this: it gets FIRMS_MAP_KEY from the SAM parameter.
"""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_env(path=ENV_FILE):
    """Set variables from `path` that are not set yet. Returns the names loaded (never values)."""
    path = Path(path)
    if not path.exists():
        return []
    loaded = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key.isidentifier():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
