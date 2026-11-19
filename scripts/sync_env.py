"""Bring .venv and data/ in line with this checkout. Safe to run any number of times.

Run with the venv's Python (setup.bat and update.bat do):
    .venv\\Scripts\\python.exe scripts\\sync_env.py [--always-install]

- Dependencies: reinstalled only when requirements.txt changed since the last sync
  (a hash is kept in .venv\\zengo-requirements.sha256), or always with --always-install.
- Dictionary: built if data\\zengo.db is missing, damaged, or older than zengo.DICT_SCHEMA.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from zengo import DICT_SCHEMA, __version__  # noqa: E402  (stdlib-only imports)
from zengo.dictionary import installed_schema  # noqa: E402

REQS = ROOT / "requirements.txt"
STAMP = Path(sys.prefix) / "zengo-requirements.sha256"


def sync_deps(always: bool) -> None:
    digest = hashlib.sha256(REQS.read_bytes()).hexdigest()
    if not always and STAMP.exists() and STAMP.read_text().strip() == digest:
        print("Dependencies: up to date.")
        return
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q",
                    "-r", str(REQS)], check=True)
    STAMP.write_text(digest)


def sync_dict() -> None:
    have = installed_schema()
    if have is not None and have >= DICT_SCHEMA:
        print("Dictionary: up to date.")
        return
    print("Building the dictionary" + (" (first run downloads about 13 MB)" if have is None else "") + "...")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_dict.py")], check=True)


if __name__ == "__main__":
    if sys.prefix == sys.base_prefix:
        sys.exit("Run this with the virtual environment's Python: .venv\\Scripts\\python.exe")
    try:
        sync_deps("--always-install" in sys.argv)
        sync_dict()
    except subprocess.CalledProcessError as e:
        sys.exit(f"Step failed (exit code {e.returncode}).")
    print(f"Zengo {__version__} is ready.")
