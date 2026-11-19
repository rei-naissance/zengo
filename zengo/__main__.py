import sys

if sys.platform != "win32":
    sys.exit("Zengo currently runs on Windows only (it uses WebView2 and Win32 APIs).")

if "--quit" in sys.argv:
    # Used by update.bat: close the running copy before its files change.
    # Exit code 0 = it was running and has quit, 1 = nothing was running, 2 = it didn't quit.
    from .instance import contact
    from .win import wait_process_exit

    r = contact({"cmd": "quit"})
    if not r:
        sys.exit(1)
    sys.exit(0 if wait_process_exit(int(r["pid"]), 15) else 2)

from .app import main

main()
