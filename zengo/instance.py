"""One running Zengo at a time, with a hand-off when a different version starts.

The running app listens on a random localhost port (authenticated with a per-run secret) and
records it in %APPDATA%\\Zengo\\instance.json. A second launch reads that file and:
  - same version, same folder  -> asks the running app to show its window, then exits;
  - different version/folder   -> asks the running app to quit, waits, then takes over;
  - `--quit`                   -> asks it to quit (used by update.bat before files change).
Without this, two copies would both listen for Ctrl+C twice and both sit in the tray.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import threading
from multiprocessing.connection import Client, Listener
from pathlib import Path
from typing import Callable

APP_DIR = Path(os.getenv("APPDATA") or Path.home()) / "Zengo"
INFO = APP_DIR / "instance.json"


def _read_info() -> dict | None:
    try:
        return json.loads(INFO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def contact(msg: dict, timeout: float = 3.0) -> dict | None:
    """Send one message to the running instance. None if nothing is running (or it's stale)."""
    from .win import wait_process_exit
    info = _read_info()
    if not info or wait_process_exit(int(info.get("pid", 0)), 0):
        return None  # nothing recorded, or that process is gone (crash, reboot)
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)  # Client() has no timeout of its own
    try:
        with Client(("127.0.0.1", int(info["port"])), authkey=bytes.fromhex(info["key"])) as c:
            c.send(msg)
            reply = c.recv() if c.poll(timeout) else {}
            return {**info, **(reply or {})}
    except Exception:  # refused, auth failure, timeout, stale file
        return None
    finally:
        socket.setdefaulttimeout(old)


class InstanceServer:
    def __init__(self, version: str, root: Path, handlers: dict[str, Callable[[dict], None]]):
        self.version, self.root, self.handlers = version, str(root), handlers
        key = secrets.token_bytes(16)
        self._listener = Listener(("127.0.0.1", 0), authkey=key)
        self._info = {"port": self._listener.address[1], "key": key.hex(), "pid": os.getpid(),
                      "version": version, "root": self.root}
        APP_DIR.mkdir(parents=True, exist_ok=True)
        tmp = INFO.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._info), encoding="utf-8")
        os.replace(tmp, INFO)
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn = self._listener.accept()
            except OSError:
                return  # closed
            except Exception:
                continue  # bad handshake from something else on the port
            try:
                msg = conn.recv() if conn.poll(3) else {}
                conn.send({"version": self.version, "root": self.root, "pid": os.getpid()})
                conn.close()
            except Exception:
                continue
            fn = self.handlers.get((msg or {}).get("cmd"))
            if fn:
                threading.Thread(target=fn, args=(msg,), daemon=True).start()

    def close(self):
        try:
            self._listener.close()
        except Exception:
            pass
        if (_read_info() or {}).get("pid") == os.getpid():
            try:
                INFO.unlink()
            except OSError:
                pass
