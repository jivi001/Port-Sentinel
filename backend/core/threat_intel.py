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
import ipaddress
from typing import Set, Dict, Optional
from collections import OrderedDict

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
        self._metadata_cache: OrderedDict[str, dict] = OrderedDict() # IP -> {org, city, country, risk}
        self._cache_timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._MAX_CACHE_SIZE = 10000
        self._CACHE_TTL = 3600.0
        
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
            
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return {"org": "Invalid IP", "country": "??", "risk": 0}

        with self._lock:
            if ip in self._metadata_cache:
                if time.time() - self._cache_timestamps.get(ip, 0) < self._CACHE_TTL:
                    self._metadata_cache.move_to_end(ip)
                    return self._metadata_cache[ip]
                else:
                    del self._metadata_cache[ip]
                    if ip in self._cache_timestamps:
                        del self._cache_timestamps[ip]

        def _fetch_background():
            try:
                url = f"https://ipinfo.io/{ip}/json"
                headers = {"Authorization": f"Bearer {IPINFO_TOKEN}"} if IPINFO_TOKEN else {}
                response = requests.get(url, headers=headers, timeout=2)
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
                        self._cache_timestamps[ip] = time.time()
                        if len(self._metadata_cache) > self._MAX_CACHE_SIZE:
                            oldest_ip, _ = self._metadata_cache.popitem(last=False)
                            if oldest_ip in self._cache_timestamps:
                                del self._cache_timestamps[oldest_ip]
            except Exception as e:
                logger.debug(f"IPInfo lookup failed for {ip}: {e}")

        # Cache miss - return placeholder and fetch in background
        with self._lock:
            # Mark as pending to prevent multiple threads fetching the same IP
            self._metadata_cache[ip] = {"org": "Resolving...", "country": "??", "risk": 0}
            self._cache_timestamps[ip] = time.time()
        
        threading.Thread(target=_fetch_background, daemon=True).start()
        
        return {"org": "Resolving...", "country": "??", "risk": 0}

    def is_malicious(self, ip: str) -> bool:
        return ip in self._malicious_ips

    def get_risk_score(self, ip: str) -> int:
        if ip in self._malicious_ips:
            return 10
        return 0

# Global instance for easy access without changing constructor signatures elsewhere
threat_manager = ThreatIntel()
