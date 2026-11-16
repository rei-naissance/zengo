import sys

if sys.platform != "win32":
    sys.exit("Zengo currently runs on Windows only (it uses WebView2 and Win32 APIs).")

from .app import main

main()
