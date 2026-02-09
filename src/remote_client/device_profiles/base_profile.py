"""Abstract base class for device profiles (SDD030)."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseDeviceProfile(ABC):
    """Abstract interface for IoT device profiles.

    Defines the common interface for all supported IoT devices,
    allowing the Remote Client Application to support multiple
    device types without code duplication.
    """

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def initialize_network(self, serial_manager) -> bool:
        """Complete network initialization sequence.

        Includes RAT selection, band configuration, and PDP context.
        """
        pass

    @abstractmethod
    def send_to_harvest(self, serial_manager, data: str) -> bool:
        """Send data to Soracom Harvest Data.

        Handles encoding and multi-step operations.
        """
        pass

    @abstractmethod
    def receive_udp(self, serial_manager, buffer_size: int) -> Optional[tuple]:
        """Receive UDP downlink data.

        Returns:
            (ip_addr, port, payload) tuple or None.
        """
        pass

    @abstractmethod
    def bind_udp_port(self, serial_manager, port: int) -> bool:
        """Bind UDP port for downlink reception."""
        pass

    @abstractmethod
    def get_signal_quality(self, serial_manager) -> dict:
        """Query signal quality metrics (RSRP, RSRQ, SINR, RSSI)."""
        pass

    @abstractmethod
    def parse_network_registration_urc(self, urc: str) -> Optional[dict]:
        """Parse network registration URCs (+CEREG, etc.)."""
        pass

    @abstractmethod
    def get_device_info(self) -> dict:
        """Return device metadata (name, manufacturer, supported features)."""
        pass

    @abstractmethod
    def connect_device(self, serial_manager) -> bool:
        """Establish initial connection to the device."""
        pass

    @abstractmethod
    def setup_receive_listener(self, serial_manager, port: int, callback) -> bool:
        """Set up listener for incoming UDP messages."""
        pass

    def get_location(self) -> Optional[tuple]:
        """Get device GPS location if available. Returns (lat, lon) or None."""
        return None

    def send_initial_location(self, serial_manager) -> bool:
        """Send location to Harvest immediately after connection. No-op by default."""
        return True
