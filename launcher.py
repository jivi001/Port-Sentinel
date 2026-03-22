"""
Port Sentinel — PyInstaller Entry Point (launcher.py)

This is the single entry point used by PyInstaller to build the .exe.
It handles:
  1. multiprocessing.freeze_support() — required for frozen executables
  2. Resolving resource paths (_MEIPASS for onefile mode)
  3. Auto-opening the browser after a short delay
  4. Launching the FastAPI backend
"""

import sys
import os
import multiprocessing
import threading
import webbrowser
import time


def _get_base_dir():
    """Return the base directory for bundled resources."""
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _open_browser(url: str, delay: float = 3.0):
    """Open the browser after a delay (gives the server time to start)."""
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    # CRITICAL: must be called before any multiprocessing code in frozen exe
    multiprocessing.freeze_support()

    base_dir = _get_base_dir()

    # Set environment so backend modules can find bundled resources
    os.environ.setdefault("SENTINEL_BASE_DIR", base_dir)

    # Load .env from the bundled location if it exists
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            pass

    # Ensure the data directory exists for SQLite
    data_dir = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    os.environ.setdefault("SENTINEL_DATA_DIR", data_dir)

    # Auto-open browser
    port = int(os.environ.get("PORT", "8600"))
    _open_browser(f"http://localhost:{port}")

    # Import and run the backend
    from backend.main import main as backend_main
    backend_main()


if __name__ == "__main__":
    main()
