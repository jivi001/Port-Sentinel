# Sentinel Backend Core Exceptions

class SentinelError(Exception):
    """Base exception for all Sentinel errors."""
    pass


class SystemProcessProtectionError(SentinelError):
    """Raised when an operation targets a protected system process.

    System PIDs that are protected:
      - Windows: PID 4 (System)
      - macOS:   PID 0 (kernel_task), PID 1 (launchd)
    """

    def __init__(self, pid: int, operation: str):
        self.pid = pid
        self.operation = operation
        super().__init__(
            f"Operation '{operation}' blocked: PID {pid} is a protected system process. "
            f"This is a non-fatal warning."
        )


class SnifferError(SentinelError):
    """Raised when the packet sniffer encounters an unrecoverable error."""
    pass


class FirewallRuleError(SentinelError):
    """Raised when a firewall rule operation fails."""
    pass


class CleanupError(SentinelError):
    """Raised when cleanup of firewall rules fails (best-effort)."""
    pass


class DatabaseError(SentinelError):
    """Raised when a database operation fails."""
    pass
