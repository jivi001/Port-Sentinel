import abc
from typing import List, Dict, Any

class OSBridgeAdapter(abc.ABC):
    """
    Abstract Base Class for OS-specific adapters.
    Ensures a unified interface for Windows, macOS, and Linux bridges.
    """

    @abc.abstractmethod
    def get_port_pid_map(self) -> List[Dict[str, Any]]:
        """
        Build a live Port -> PID -> AppName map.
        
        Returns:
            List of dictionaries containing:
            {
                "port": int,
                "pid": int,
                "app_name": str,
                "protocol": str,
                "status": str
            }
        """
        pass

    @abc.abstractmethod
    def block_port(self, port: int, protocol: str = "tcp") -> bool:
        """
        Add a firewall rule to hard block traffic on a specific port.
        
        Args:
            port (int): Port number to block.
            protocol (str): Protocol (tcp/udp).
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @abc.abstractmethod
    def unblock_port(self, port: int) -> bool:
        """
        Remove the firewall rule for a specific port.
        
        Args:
            port (int): Port number to unblock.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @abc.abstractmethod
    def cleanup_all_rules(self) -> int:
        """
        Remove ALL Sentinel-created firewall rules.
        
        Returns:
            int: The number of rules removed.
        """
        pass
