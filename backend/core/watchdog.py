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
from typing import Optional
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
                    restarts = int(os.environ.get("SENTINEL_RESTARTS", "0"))
                    if restarts >= 5:
                        logger.critical("Maximum restart limit (5) reached. Watchdog giving up.")
                        break
                    
                    # Exponential backoff
                    backoff = min(60, 2 ** restarts)
                    logger.warning(f"MAIN PROCESS LOST! Attempting emergency restart {restarts + 1}/5 in {backoff}s...")
                    time.sleep(backoff)
                    
                    self._restart_sentinel(restarts + 1)
                    break # Exit watchdog as a new one will be spawned
                
                # Check if it's responsive (optional: check health endpoint)
                # For now, just PID check is enough for "tamper resistance"
                
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
            
            time.sleep(5)

    def _restart_sentinel(self, new_count: int):
        """Launch a new instance of the sentinel backend."""
        try:
            # Re-run the current entry point with realpath to prevent spoofing
            executable = os.path.realpath(sys.executable)
            args = [executable, "-m", "backend"]
            
            # Use explicit allowlist for environment to prevent privilege escalation
            safe_keys = {
                "PATH", "PYTHONPATH", "HOST", "PORT", "DATABASE_URL", 
                "VIGILANT_JWT_SECRET", "VIGILANT_CORS_ORIGINS", 
                "INFLUXDB_URL", "INFLUXDB_TOKEN", "INFLUXDB_ORG", "INFLUXDB_BUCKET",
                "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"
            }
            
            safe_env = {k: os.environ[k] for k in safe_keys if k in os.environ}
            safe_env["SENTINEL_RESTARTS"] = str(new_count)
            
            # Start in new session to decouple from the dying process
            if os.name == 'nt':
                # Windows: DETACHED_PROCESS to survive parent termination
                subprocess.Popen(args, env=safe_env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
            else:
                # Unix: start_new_session
                subprocess.Popen(args, env=safe_env, start_new_session=True)
                
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
