"""
Sentinel Watchdog — Process Protection & Persistence.

A lightweight secondary process that monitors the health of the main
Sentinel backend. If the main process is terminated, the watchdog
attempts to restart it, providing basic protection against user-space tampering.
"""

import os
import time
import subprocess
import sys
import logging
import threading
import psutil

logger = logging.getLogger("sentinel.watchdog")

class SentinelWatchdog:
    """
    Ensures the main Port Sentinel process remains running.
    """
    def __init__(self, main_pid: int):
        self.main_pid = main_pid
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the background monitor thread."""
        self._monitor_thread = threading.Thread(target=self._run, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Watchdog started for main process (PID={self.main_pid})")

    def _run(self):
        """Monitoring loop."""
        while not self._stop_event.is_set():
            try:
                # Check if main process exists
                if not psutil.pid_exists(self.main_pid):
                    logger.warning("MAIN PROCESS LOST! Attempting emergency restart...")
                    self._restart_sentinel()
                    break # Exit watchdog as a new one will be spawned
                
                # Check if it's responsive (optional: check health endpoint)
                # For now, just PID check is enough for "tamper resistance"
                
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
            
            time.sleep(5)

    def _restart_sentinel(self):
        """Launch a new instance of the sentinel backend."""
        try:
            # Re-run the current entry point
            executable = sys.executable
            args = [executable, "-m", "backend.main"]
            env = os.environ.copy()
            
            # Start in new session to decouple from the dying process
            if os.name == 'nt':
                # Windows: DETACHED_PROCESS to survive parent termination
                subprocess.Popen(args, env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
            else:
                # Unix: start_new_session
                subprocess.Popen(args, env=env, start_new_session=True)
                
            logger.info("Sentinel backend restart signal sent.")
        except Exception as e:
            logger.error(f"Critical: Failed to restart Sentinel: {e}")

    def stop(self):
        """Stop the watchdog monitor."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)

def spawn_watchdog():
    """Surgical hook to start watchdog from main.py."""
    watchdog = SentinelWatchdog(os.getpid())
    watchdog.start()
    return watchdog
