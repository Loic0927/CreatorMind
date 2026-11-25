"""Export FastAPI's schema and refresh the checked-in TypeScript schema artifact.

This intentionally uses the backend application as the source of truth. The
web and mobile applications keep their small client-session/view aliases in
``shared/api.ts`` and consume the same contract instead of declaring copies.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "shared" / "openapi.json"
TYPES_PATH = ROOT / "shared" / "openapi.ts"


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from backend.main import app

    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    subprocess.run(
        [
            "npx.cmd" if os.name == "nt" else "npx",
            "--yes",
            "openapi-typescript@7.9.1",
            str(SCHEMA_PATH),
            "-o",
            str(TYPES_PATH),
        ],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
