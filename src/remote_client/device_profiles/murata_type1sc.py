"""Murata Type 1SC-NTN device profile (SDD030 §3).

Implements AT command sequences for Murata's Type 1SC-NTN module
with AT shell firmware.
"""

import logging
import re
from typing import Optional

from .base_profile import BaseDeviceProfile

logger = logging.getLogger(__name__)


class MurataType1SCProfile(BaseDeviceProfile):
    """Device profile for Murata Type 1SC-NTN."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._location: Optional[tuple] = None
        self._location_sent = False
        self._recv_socket_id: Optional[int] = None

    def get_device_info(self) -> dict:
        return {
            "name": "Murata Type 1SC-NTN",
            "manufacturer": "Murata",
            "type": "murata_type1sc_ntng",
        }

    def connect_device(self, serial_manager) -> bool:
        """Connect to Murata Type 1SC-NTN — send ATZ and wait for %BOOTEV:0 (SDD032)."""
        logger.info("Connecting to Murata Type 1SC-NTN...")
        success, lines, urc = serial_manager.send_command_wait_urc(
            "ATZ", "%BOOTEV:0", timeout=30
        )
        if success:
            logger.info("Connected to Murata Type 1SC-NTN")
        else:
            logger.error("Failed to connect to Murata Type 1SC-NTN")
        return success

    def initialize_network(self, serial_manager) -> bool:
        """NTN network initialization sequence (SDD034).

        Full NTN initialization including GNSS fix, satellite detection,
        and network registration.
        """
        # Step 1: Check SIM state
        logger.info("  Checking SIM state...")
        success, resp = serial_manager.send_command("AT+CPIN?", timeout=10)
        if not success:
            logger.error("  SIM not ready")
            return False

        # Step 2: Set error reporting
        logger.info("  Setting error reporting...")
        serial_manager.send_command(
            'AT%SETACFG="manager.urcBootEv.enabled","true"', timeout=10
        )

        # Step 3: Set SIM init policy
        serial_manager.send_command(
            'AT%SETCFG="SIM_INIT_SELECT_POLICY","0"', timeout=10
        )

        # Step 4: Reset modem
        logger.info("  Resetting modem...")
        success, _, urc = serial_manager.send_command_wait_urc(
            "ATZ", "%BOOTEV:0", timeout=30
        )
        if not success:
            logger.error("  Failed to reset modem")
            return False

        # Step 5: Set NTN parameters
        ntn_params = [
            'AT%SETACFG="radiom.config.multi_rat_enable","true"',
            'AT%SETACFG="radiom.config.preferred_rat_list","none"',
            'AT%SETACFG="radiom.config.auto_preference_mode","none"',
            'AT%SETACFG="locsrv.operation.locsrv_enable","true"',
            'AT%SETACFG="locsrv.internal_gnss.auto_restart","enable"',
            'AT%SETACFG="modem_apps.Mode.AutoConnectMode","true"',
        ]
        for cmd in ntn_params:
            logger.info(f"  Setting: {cmd}")
            serial_manager.send_command(cmd, timeout=10)

        # Step 6: Reset again
        logger.info("  Resetting modem again...")
        success, _, urc = serial_manager.send_command_wait_urc(
            "ATZ", "%BOOTEV:0", timeout=30
        )
        if not success:
            return False

        # Step 7: Switch to NTN plan
        logger.info("  Switching to NTN SIM plan...")
        serial_manager.send_command(
            'AT+CSIM=52,"80C2000015D613190103820282811B0100130799F08900010001"',
            timeout=10,
        )

        # Step 8: RAT image selection
        logger.info("  Selecting NTN RAT image...")
        serial_manager.send_command("AT%RATIMGSEL=2", timeout=10)

        # Step 9: Activate NTN RAT
        serial_manager.send_command('AT%RATACT="NBNTN","1"', timeout=10)

        # Step 10: Lock to band
        ntn_band = self.config.get("network", {}).get("ntn_band", "256")
        serial_manager.send_command(f'AT%SETCFG="BAND","{ntn_band}"', timeout=10)

        # Step 11: Disable modem
        serial_manager.send_command("AT+CFUN=0", timeout=10)

        # Step 12: Enable GNSS and NTN reception notification
        serial_manager.send_command('AT%IGNSSEV="FIX",1', timeout=10)
        serial_manager.send_command('AT%NOTIFYEV="SIB31",1', timeout=10)

        # Step 13: Disable then enable iGNSS
        serial_manager.send_command("AT%IGNSSACT=0", timeout=10)
        serial_manager.send_command("AT%IGNSSACT=1", timeout=10)

        # Step 14: Wait for GNSS fix
        logger.info("  Waiting for GNSS fix...")
        gnss_ok, gnss_urc = serial_manager.wait_for_urc('%IGNSSEVU:"FIX"', timeout=300)
        if gnss_ok:
            self._parse_gnss_fix(gnss_urc)
            logger.info(f"  GNSS fix acquired: {self._location}")
        else:
            logger.warning("  GNSS fix timeout - continuing without location")

        # Step 15: Enable CEREG
        serial_manager.send_command("AT+CEREG=2", timeout=10)

        # Step 16: Enable radio
        serial_manager.send_command("AT+CFUN=1", timeout=10)

        # Step 17: Wait for SIB31 (satellite detection)
        logger.info("  Waiting for satellite detection...")
        serial_manager.wait_for_urc('%NOTIFYEV: "SIB31"', timeout=120)

        # Step 18: Wait for network registration
        logger.info("  Waiting for network registration...")
        registered, urc = serial_manager.wait_for_urc("+CEREG:", timeout=120)
        if registered:
            parsed = self.parse_network_registration_urc(urc)
            if parsed and parsed.get("stat") in [1, 5]:
                logger.info(f"  Registered on NTN network (stat={parsed['stat']})")
                return True
        logger.error("  Failed to register on NTN network")
        return False

    def configure_pdp_context(self, serial_manager) -> bool:
        """Configure PDP context for Murata (SDD036).

        Includes ping test to verify connectivity.
        """
        logger.info("  Configuring PDP context...")
        serial_manager.send_command('AT+CGDCONT=1,"IP","soracom.io"', timeout=10)

        # Ping test
        logger.info("  Pinging Soracom server...")
        success, _, urc = serial_manager.send_command_wait_urc(
            'AT%PINGCMD=0,"100.127.100.127",1,50,30',
            "%PINGCMD:",
            timeout=60,
        )
        if success:
            logger.info(f"  Ping successful: {urc}")
            return True
        logger.error("  Ping failed")
        return False

    def open_udp_socket(self, serial_manager) -> bool:
        """Open UDP socket for Murata (SDD038).

        1. Enable socket events
        2. Allocate UDP socket
        3. Activate socket
        """
        logger.info("  Enabling socket events...")
        serial_manager.send_command("AT%SOCKETEV=0,1", timeout=10)

        logger.info("  Allocating UDP socket...")
        endpoint = self.config.get("network", {}).get("harvest_endpoint", "harvest.soracom.io")
        port = self.config.get("network", {}).get("harvest_port", 8514)
        cmd = f'AT%SOCKETCMD="ALLOCATE",1,"UDP","OPEN","{endpoint}",{port}'
        success, resp = serial_manager.send_command(cmd, timeout=15)
        if not success:
            return False

        logger.info("  Activating socket...")
        success, resp = serial_manager.send_command('AT%SOCKETCMD="ACTIVATE",1', timeout=15)
        return success

    def send_to_harvest(self, serial_manager, data: str) -> bool:
        """Send data to Soracom Harvest Data (SDD040).

        Converts ASCII to HEX and uses AT%SOCKETDATA command.
        Before first message, sends location (SDD040 exception).
        """
        # Send location before first message (SDD040 exception)
        if not self._location_sent and self._location:
            from src.common.message import LocationMessage
            loc_msg = LocationMessage(str(self._location[0]), str(self._location[1]))
            loc_data = loc_msg.encode()
            self._send_hex_data(serial_manager, loc_data)
            self._location_sent = True

        return self._send_hex_data(serial_manager, data)

    def _send_hex_data(self, serial_manager, data: str) -> bool:
        """Send HEX-encoded data via socket (SDD040)."""
        hex_data = data.encode().hex().upper()
        size = len(data)
        cmd = f'AT%SOCKETDATA="SEND",1,{size},"{hex_data}"'
        logger.info(f"  Sending: {cmd}")

        success, lines, urc = serial_manager.send_command_wait_urc(
            cmd, "%SOCKETEV:1,1", timeout=30
        )
        return success

    def receive_udp(self, serial_manager, buffer_size: int) -> Optional[tuple]:
        """Receive UDP message for Murata (SDD042).

        Reads data from the allocated listen socket.
        """
        socket_id = self._recv_socket_id or 1
        cmd = f'AT%SOCKETDATA="RECEIVE",{socket_id},1500'
        success, resp = serial_manager.send_command(cmd, timeout=10)
        if not success:
            return None

        for line in resp:
            match = re.match(
                r'%SOCKETDATA:(\d+),(\d+),(\d+),"([^"]*)",?"?([^"]*)"?,?(\d*)',
                line,
            )
            if match:
                rlength = int(match.group(2))
                rdata_hex = match.group(4)
                src_ip = match.group(5)
                src_port = int(match.group(6)) if match.group(6) else 0

                # Decode HEX to ASCII
                try:
                    payload = bytes.fromhex(rdata_hex).decode("utf-8")
                except (ValueError, UnicodeDecodeError):
                    payload = rdata_hex

                return (src_ip, src_port, payload)
        return None

    def bind_udp_port(self, serial_manager, port: int) -> bool:
        """Not applicable for Murata — uses LISTEN socket instead."""
        return True

    def setup_receive_listener(self, serial_manager, port: int, callback) -> bool:
        """Set up receive listener for Murata (SDD042).

        1. Allocate LISTEN socket
        2. Wait for %SOCKETCMD notification
        3. Activate socket
        4. Listen for %SOCKETEV data notifications
        """
        logger.info("  Setting up receive listener...")

        # Allocate listen socket
        cmd = f'AT%SOCKETCMD="ALLOCATE",1,"UDP","LISTEN","0.0.0.0",,{port}'
        success, resp = serial_manager.send_command(cmd, timeout=15)
        if not success:
            return False

        # Wait for SOCKETCMD notification
        ok, urc = serial_manager.wait_for_urc("%SOCKETCMD:", timeout=15)
        if ok:
            match = re.search(r'%SOCKETCMD:(\d+)', urc)
            if match:
                self._recv_socket_id = int(match.group(1))

        socket_id = self._recv_socket_id or 1

        # Activate listen socket
        success, resp = serial_manager.send_command(
            f'AT%SOCKETCMD="ACTIVATE",{socket_id}', timeout=15
        )
        if not success:
            return False

        # Register handler for incoming data
        buffer_size = self.config.get("network", {}).get("udp_buffer_size", 256)

        def socketev_handler(urc_line: str):
            if "%SOCKETEV:" in urc_line:
                result = self.receive_udp(serial_manager, buffer_size)
                if result:
                    callback(result)

        serial_manager.register_urc_callback(socketev_handler)
        logger.info("  Receive listener active")
        return True

    def subscribe_signal_quality(self, serial_manager) -> bool:
        """Subscribe to signal quality monitoring (SDD045)."""
        logger.info("  Subscribing to signal quality...")
        success, resp = serial_manager.send_command('AT%MEAS="8"', timeout=10)
        return success

    def get_signal_quality(self, serial_manager) -> dict:
        return {}

    def parse_signal_quality_urc(self, urc: str) -> dict:
        """Parse %MEAS signal quality notification (SDD045).

        Format: %%MEAS:Signal Quality:RSRP=<RSRP>,RSRQ=<RSRQ>,SINR=<SINR>,RSSI=<RSSI>
        """
        match = re.search(
            r'RSRP=\s*(-?\d+).*RSRQ=\s*(-?\d+).*SINR=\s*(-?\d+).*RSSI=\s*(-?\d+)',
            urc,
        )
        if match:
            return {
                "rsrp_dbm": int(match.group(1)),
                "rsrq": int(match.group(2)),
                "sinr": int(match.group(3)),
                "rssi": int(match.group(4)),
            }
        return {}

    def parse_network_registration_urc(self, urc: str) -> Optional[dict]:
        """Parse +CEREG URC."""
        match = re.match(r'\+?CEREG:\s*(\d+)', urc)
        if match:
            return {"stat": int(match.group(1))}
        return None

    def get_location(self) -> Optional[tuple]:
        """Return stored GNSS location."""
        return self._location

    def _parse_gnss_fix(self, urc: str):
        """Parse GNSS fix notification (SDD034).

        Format: %IGNSSEVU:"FIX",1,"time","date","altitude","latitude","longitude",...
        """
        match = re.search(
            r'%IGNSSEVU:"FIX",\d+,"[^"]*","[^"]*","([^"]*)","([^"]*)","([^"]*)"',
            urc,
        )
        if match:
            latitude = match.group(2)
            longitude = match.group(3)
            try:
                self._location = (float(latitude), float(longitude))
            except ValueError:
                self._location = None
