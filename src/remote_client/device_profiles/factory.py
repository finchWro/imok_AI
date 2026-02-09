"""Device Profile Factory (SDD030 §5).

Instantiates the correct device profile based on device type.
"""

from .base_profile import BaseDeviceProfile
from .nordic_thingy91x import NordicThingy91XProfile
from .murata_type1sc import MurataType1SCProfile


class DeviceProfileFactory:
    """Factory to create device profiles based on device type."""

    @staticmethod
    def create(device_type: str, config: dict) -> BaseDeviceProfile:
        """Create a device profile instance.

        Args:
            device_type: One of 'nordic_thingy91x' or 'murata_type1sc_ntng'.
            config: Device configuration dictionary loaded from YAML.

        Returns:
            BaseDeviceProfile instance.

        Raises:
            ValueError: If device_type is not supported.
        """
        if device_type == "nordic_thingy91x":
            return NordicThingy91XProfile(config)
        elif device_type == "murata_type1sc_ntng":
            return MurataType1SCProfile(config)
        else:
            raise ValueError(f"Unsupported device type: {device_type}")

    @staticmethod
    def get_supported_devices() -> list[dict]:
        """Return list of supported device types and names."""
        return [
            {"type": "nordic_thingy91x", "name": "Nordic Thingy:91 X"},
            {"type": "murata_type1sc_ntng", "name": "Murata Type 1SC-NTN"},
        ]
