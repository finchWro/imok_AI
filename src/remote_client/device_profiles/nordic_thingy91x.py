"""Nordic Thingy:91 X device profile (SDD030 §2).

Implements AT command sequences for Nordic Semiconductor's Thingy:91 X
with AT shell firmware.
"""

import logging
import re
from typing import Optional

from .base_profile import BaseDeviceProfile

logger = logging.getLogger(__name__)


class NordicThingy91XProfile(BaseDeviceProfile):
    """Device profile for Nordic Thingy:91 X."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._cscon_callbacks = []

    def get_device_info(self) -> dict:
        return {
            "name": "Nordic Thingy:91 X",
            "manufacturer": "Nordic Semiconductor",
            "type": "nordic_thingy91x",
        }

    def connect_device(self, serial_manager) -> bool:
        """Connect to Thingy:91 X — send AT and wait for OK (SDD031)."""
        logger.info("Connecting to Nordic Thingy:91 X...")
        success, response = serial_manager.send_command("AT", timeout=5)
        if success:
            logger.info("Connected to Nordic Thingy:91 X")
        else:
            logger.error("Failed to connect to Nordic Thingy:91 X")
        return success

    def initialize_network(self, serial_manager) -> bool:
        """Network initialization sequence for Thingy:91 X (SDD033).

        1. AT+CFUN=0 - Disable modem
        2. AT+CEREG=5 - Enable network registration URCs
        3. AT+CSCON=1 - Enable connection status notifications
        4. AT%XSYSTEMMODE=1,0,1,0 - Set LTE-M mode
        5. AT+CFUN=1 - Enable modem
        6. Wait for +CEREG URC with stat=1/5
        """
        steps = [
            ("AT+CFUN=0", "Disable modem"),
            ("AT+CEREG=5", "Enable network registration URCs"),
            ("AT+CSCON=1", "Enable connection status notifications"),
            ("AT%XSYSTEMMODE=1,0,1,0", "Set LTE-M mode"),
        ]

        for cmd, desc in steps:
            logger.info(f"  {desc}: {cmd}")
            success, resp = serial_manager.send_command(cmd, timeout=10)
            if not success:
                logger.error(f"  Failed: {desc}")
                return False

        # Enable modem
        logger.info("  Enable modem: AT+CFUN=1")
        success, resp = serial_manager.send_command("AT+CFUN=1", timeout=10)
        if not success:
            logger.error("  Failed to enable modem")
            return False

        # Wait for +CEREG with stat=1 or stat=5
        logger.info("  Waiting for network registration...")
        registered, urc = serial_manager.wait_for_urc("+CEREG:", timeout=120)
        if registered:
            parsed = self.parse_network_registration_urc(urc)
            if parsed and parsed.get("stat") in [1, 5]:
                logger.info(f"  Registered on network (stat={parsed['stat']})")
                return True
            else:
                logger.warning(f"  CEREG received but not registered: {urc}")
                return False
        else:
            logger.error("  Timeout waiting for network registration")
            return False

    def configure_pdp_context(self, serial_manager) -> bool:
        """Configure PDP context (SDD035)."""
        logger.info("  Configuring PDP context...")
        success, resp = serial_manager.send_command(
            'AT+CGDCONT=1,"IP","soracom.io"', timeout=10
        )
        return success

    def open_udp_socket(self, serial_manager) -> bool:
        """Open UDP socket (SDD037)."""
        logger.info("  Opening UDP socket...")
        success, resp = serial_manager.send_command("AT#XSOCKET=1,2,0", timeout=10)
        if success:
            logger.info("  UDP socket opened successfully")
        return success

    def bind_udp_port(self, serial_manager, port: int) -> bool:
        """Bind UDP port for reception (SDD041)."""
        logger.info(f"  Binding UDP port {port}...")
        success, resp = serial_manager.send_command(f"AT#XBIND={port}", timeout=10)
        return success

    def subscribe_signal_quality(self, serial_manager) -> bool:
        """Subscribe to signal quality notifications (SDD044)."""
        logger.info("  Subscribing to signal quality...")
        success, resp = serial_manager.send_command("AT%CESQ=1", timeout=10)
        return success

    def send_to_harvest(self, serial_manager, data: str) -> bool:
        """Send data to Soracom Harvest Data (SDD039).

        Uses AT#XSENDTO command with harvest.soracom.io:8514.
        """
        endpoint = self.config.get("network", {}).get("harvest_endpoint", "harvest.soracom.io")
        port = self.config.get("network", {}).get("harvest_port", 8514)

        cmd = f'AT#XSENDTO="{endpoint}",{port},"{data}"'
        logger.info(f"  Sending to harvest: {cmd}")
        success, resp = serial_manager.send_command(cmd, timeout=30)

        if success:
            # Parse #XSENDTO: <size> response
            for line in resp:
                if "#XSENDTO:" in line:
                    logger.info(f"  Send confirmed: {line}")
                    return True
            # If OK but no XSENDTO line, still consider success
            return True
        return False

    def receive_udp(self, serial_manager, buffer_size: int) -> Optional[tuple]:
        """Receive UDP message (SDD041).

        Uses AT#XRECVFROM command.
        Returns (ip_addr, port, payload) or None.
        """
        cmd = f"AT#XRECVFROM={buffer_size}"
        success, resp = serial_manager.send_command(cmd, timeout=10)
        if not success:
            return None

        ip_addr = None
        port = None
        data = None

        for i, line in enumerate(resp):
            match = re.match(r'#XRECVFROM:\s*(\d+),"([^"]+)",(\d+)', line)
            if match:
                size = int(match.group(1))
                ip_addr = match.group(2)
                port = int(match.group(3))
                # Data is on the next line
                if i + 1 < len(resp) and resp[i + 1] not in ["OK", "ERROR"]:
                    data = resp[i + 1]
                break

        if ip_addr and data is not None:
            # Filter by IP (SDD041 step 6)
            ip_filter = self.config.get("network", {}).get("ip_filter", "100.127.10.16")
            if ip_addr == ip_filter:
                return (ip_addr, port, data)
            else:
                logger.debug(f"  Filtered out message from {ip_addr}")
                return None
        return None

    def setup_receive_listener(self, serial_manager, port: int, callback) -> bool:
        """Set up receive listener for Thingy:91 X.

        Registers a +CSCON: 1 URC handler that triggers message reads.
        """
        ip_filter = self.config.get("network", {}).get("ip_filter", "100.127.10.16")
        buffer_size = self.config.get("network", {}).get("udp_buffer_size", 256)

        def cscon_handler(urc: str):
            if "+CSCON: 1" in urc:
                logger.info("  CSCON:1 received, reading UDP message...")
                result = self.receive_udp(serial_manager, buffer_size)
                if result:
                    callback(result)

        serial_manager.register_urc_callback(cscon_handler)
        self._cscon_callbacks.append(cscon_handler)
        return True

    def get_signal_quality(self, serial_manager) -> dict:
        """Parse %CESQ signal quality notification (SDD044)."""
        return {}

    def parse_signal_quality_urc(self, urc: str) -> dict:
        """Parse %CESQ notification.

        Format: %CESQ: <rsrp>,<rsrq>,<snr>,<rscp>
        RSRP dBm = value - 141
        """
        match = re.match(r'%CESQ:\s*(\d+),(\d+),(\d+),(\d+)', urc)
        if match:
            rsrp_raw = int(match.group(1))
            rsrp_dbm = rsrp_raw - 141 if rsrp_raw != 255 else None
            return {
                "rsrp_raw": rsrp_raw,
                "rsrp_dbm": rsrp_dbm,
                "rsrq": int(match.group(2)),
                "snr": int(match.group(3)),
                "rscp": int(match.group(4)),
            }
        return {}

    def parse_network_registration_urc(self, urc: str) -> Optional[dict]:
        """Parse +CEREG URC.

        Format: +CEREG: <stat>[,<tac>,<ci>,<AcT>,...]
        """
        match = re.match(r'\+CEREG:\s*(\d+)', urc)
        if match:
            return {"stat": int(match.group(1))}
        return None
