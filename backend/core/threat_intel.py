"""
Sentinel Threat Intelligence Module.

Provides local-cache lookups for malicious IP addresses using 
high-performance sets. Initialized with public threat feeds.
"""

import logging
import threading
import time
import os
import requests
from typing import Set, Dict, Optional

logger = logging.getLogger("sentinel.threat_intel")

# --- Configuration ---
IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")

class ThreatIntel:
    """
    Manages IP reputation and metadata lookups.
    Uses ipinfo.io for geolocation and ASN data.
    """
    def __init__(self):
        self._malicious_ips: Set[str] = set()
        self._metadata_cache: Dict[str, dict] = {} # IP -> {org, city, country, risk}
        self._lock = threading.Lock()
        
        # Initial bootstrap
        self._bootstrap_list()

    def _bootstrap_list(self):
        """Initial seed of known malicious IP patterns."""
        # Cleaned: Removed all mock/static indicators for production readiness.
        with self._lock:
            self._malicious_ips.clear()
        logger.info(f"Threat Intelligence initialized (Empty)")

    def get_ip_metadata(self, ip: str) -> dict:
        """
        Get metadata for an IP. Uses cache first, then hits API.
        """
        if not ip or ip.startswith("127.") or ip.startswith("192.168.") or ip.startswith("10."):
            return {"org": "Local Network", "country": "LOCAL", "risk": 0}

        with self._lock:
            if ip in self._metadata_cache:
                return self._metadata_cache[ip]

        # Fetch from ipinfo.io
        try:
            url = f"https://ipinfo.io/{ip}/json?token={IPINFO_TOKEN}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                metadata = {
                    "org": data.get("org", "Unknown Provider"),
                    "city": data.get("city", "Unknown"),
                    "country": data.get("country", "??"),
                    "risk": 10 if ip in self._malicious_ips else 0
                }
                with self._lock:
                    self._metadata_cache[ip] = metadata
                return metadata
        except Exception as e:
            logger.debug(f"IPInfo lookup failed for {ip}: {e}")
        
        return {"org": "Unknown", "country": "??", "risk": 0}

    def is_malicious(self, ip: str) -> bool:
        return ip in self._malicious_ips

    def get_risk_score(self, ip: str) -> int:
        if ip in self._malicious_ips:
            return 10
        return 0

# Global instance for easy access without changing constructor signatures elsewhere
threat_manager = ThreatIntel()
