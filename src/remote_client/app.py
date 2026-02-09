"""Remote Client Application (SDD001, SDD003, SDD009, SDD016).

Main application logic orchestrating the GUI, serial communication,
device profiles, and message handling.
"""

import logging
import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from typing import Optional

import yaml
import serial.tools.list_ports

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.remote_client.gui import RemoteClientGUI
from src.remote_client.serial_manager import SerialManager
from src.remote_client.device_profiles.factory import DeviceProfileFactory
from src.remote_client.device_profiles.base_profile import BaseDeviceProfile
from src.common.message import LocationMessage

logger = logging.getLogger(__name__)

# Device type mapping (display name -> config key)
DEVICE_MAP = {
    "Nordic Thingy:91 X": "nordic_thingy91x",
    "Murata Type 1SC-NTN": "murata_type1sc_ntng",
}


class RemoteClientApp:
    """Main Remote Client Application controller."""

    def __init__(self):
        self.root = tk.Tk()
        self.gui = RemoteClientGUI(self.root)
        self.serial = SerialManager()
        self.device_profile: Optional[BaseDeviceProfile] = None
        self.config: dict = {}
        self._connected = False
        self._config_dir = os.path.join(os.path.dirname(__file__), "..", "..", "config")

        self._setup()

    def _setup(self):
        """Initialize the application."""
        # Set device options
        devices = DeviceProfileFactory.get_supported_devices()
        self.gui.set_device_options(devices)

        # Scan COM ports
        self._refresh_ports()

        # Set callbacks
        self.gui.set_callbacks(
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
            on_send=self._on_send,
            on_clear_log=lambda: logger.info("Log cleared"),
        )

        # Register raw serial callback for message log
        self.serial.register_raw_callback(self._on_raw_serial)

    def _refresh_ports(self):
        """Refresh available COM ports."""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.gui.set_port_options(ports)

    def _load_device_config(self, device_type: str) -> dict:
        """Load device configuration from YAML file."""
        config_files = {
            "nordic_thingy91x": "nordic_thingy91x.yaml",
            "murata_type1sc_ntng": "murata_type1sc_ntng.yaml",
        }
        filename = config_files.get(device_type)
        if not filename:
            return {}

        filepath = os.path.join(self._config_dir, filename)
        try:
            with open(filepath, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {filepath}")
            return {}

    def _on_connect(self):
        """Handle connect button click (SDD016 configuration sequence)."""
        device_name = self.gui.get_selected_device()
        port = self.gui.get_selected_port()
        baudrate = self.gui.get_selected_baudrate()

        if not port:
            self.gui.add_chat_status("Error: No COM port selected")
            return

        device_type = DEVICE_MAP.get(device_name)
        if not device_type:
            self.gui.add_chat_status("Error: No device selected")
            return

        # Load config and create profile
        self.config = self._load_device_config(device_type)
        self.device_profile = DeviceProfileFactory.create(device_type, self.config)

        # Update GUI to connecting state
        self.gui.update_connection_status("connecting")
        self.gui.add_chat_status(f"Connecting to {device_name} on {port}...")

        # Run connection in background thread
        thread = threading.Thread(
            target=self._connect_sequence, args=(port, baudrate), daemon=True
        )
        thread.start()

    def _connect_sequence(self, port: str, baudrate: int):
        """Execute the full IoT device configuration sequence (SDD016).

        1. Connect to IoT device (SDD007)
        2. Establish cellular connection (SDD013)
        3. If successful: start signal quality monitoring (SDD015)
        4. If successful: activate PDP context (SDD014)
        5. If PDP successful: open UDP socket (SDD018)
        6. If socket successful: enable receive messages (SDD027)
        """
        try:
            # Step 1: Connect to serial device (SDD007)
            self._update_status("Connecting to serial port...")
            if not self.serial.connect(port, baudrate):
                self._connection_failed("Failed to open serial port")
                return

            # Step 2: Connect to device (SDD031/SDD032)
            self._update_status("Verifying device connection...")
            if not self.device_profile.connect_device(self.serial):
                self._connection_failed("Device not responding")
                return

            # Step 3: Establish cellular connection (SDD013/SDD033/SDD034)
            self._update_status("Establishing cellular connection...")

            # Register URC handlers
            self.serial.register_urc_callback(self._handle_urc)

            if not self.device_profile.initialize_network(self.serial):
                self._connection_failed("Failed to register on cellular network")
                return

            # Step 4: Signal quality monitoring (SDD015/SDD044/SDD045)
            self._update_status("Starting signal quality monitoring...")
            self.device_profile.subscribe_signal_quality(self.serial)

            # Step 5: Configure PDP context (SDD014/SDD035/SDD036)
            self._update_status("Configuring PDP context...")
            if not self.device_profile.configure_pdp_context(self.serial):
                self._connection_failed("PDP context configuration failed")
                return

            # Step 6: Open UDP socket (SDD018/SDD037/SDD038)
            self._update_status("Opening UDP socket...")
            if not self.device_profile.open_udp_socket(self.serial):
                self._connection_failed("Failed to open UDP socket")
                return

            # Step 7: Enable receive messages (SDD027/SDD041/SDD042)
            self._update_status("Setting up message reception...")
            udp_port = self.config.get("network", {}).get("udp_port", 55555)
            self.device_profile.setup_receive_listener(
                self.serial, udp_port, self._on_message_received
            )

            # Bind UDP port (for Nordic)
            self.device_profile.bind_udp_port(self.serial, udp_port)

            # Connection successful
            self._connected = True
            self.root.after(0, lambda: self.gui.update_connection_status("connected"))
            self.root.after(0, lambda: self.gui.add_chat_status("Connected and ready!"))

            # Send location for Murata devices (SDD040 exception / SDD047)
            location = self.device_profile.get_location()
            if location:
                self.root.after(0, lambda: self.gui.add_chat_status(
                    f"GPS Location: {location[0]}, {location[1]}"
                ))

        except Exception as e:
            logger.exception("Connection sequence failed")
            self._connection_failed(f"Error: {e}")

    def _on_disconnect(self):
        """Handle disconnect button click."""
        self._connected = False
        self.serial.disconnect()
        self.gui.update_connection_status("disconnected")
        self.gui.add_chat_status("Disconnected")
        self.gui.update_rsrp(None)

    def _on_send(self, message: str):
        """Handle send button click (SDD010/SDD039/SDD040)."""
        if not self._connected or not self.device_profile:
            self.gui.add_chat_status("Cannot send: not connected")
            return

        # Show sending status
        self.gui.add_chat_message(message, "SEND", status="sending...")

        # Send in background
        def do_send():
            success = self.device_profile.send_to_harvest(self.serial, message)
            status = "success" if success else "failure"
            self.root.after(0, lambda: self.gui.add_chat_message(
                message, "SEND", status=status
            ))

        thread = threading.Thread(target=do_send, daemon=True)
        thread.start()

    def _on_message_received(self, result: tuple):
        """Handle received UDP message (SDD011/SDD041/SDD042)."""
        ip_addr, port, payload = result
        logger.info(f"Received message from {ip_addr}:{port}: {payload}")

        # Check for location message (these are outbound only, shouldn't appear here)
        loc = LocationMessage.decode(payload)
        if loc:
            logger.info(f"Location update received: {loc.latitude}, {loc.longitude}")
            return

        # Display in chat (SDD011 - no AT command responses in chat)
        self.root.after(0, lambda: self.gui.add_chat_message(
            payload, "RECV", timestamp=datetime.now()
        ))

    def _handle_urc(self, urc: str):
        """Handle unsolicited result codes."""
        # Signal quality (SDD044/SDD045)
        if "%CESQ:" in urc:
            parsed = self.device_profile.parse_signal_quality_urc(urc)
            if parsed and "rsrp_dbm" in parsed:
                self.root.after(0, lambda: self.gui.update_rsrp(parsed["rsrp_dbm"]))
        elif "%MEAS:" in urc:
            parsed = self.device_profile.parse_signal_quality_urc(urc)
            if parsed and "rsrp_dbm" in parsed:
                self.root.after(0, lambda: self.gui.update_rsrp(parsed["rsrp_dbm"]))

        # Network registration changes
        elif "+CEREG:" in urc:
            parsed = self.device_profile.parse_network_registration_urc(urc)
            if parsed:
                stat = parsed.get("stat")
                if stat in [1, 5]:
                    self.root.after(0, lambda: self.gui.update_connection_status("connected"))
                elif stat in [0, 2, 3, 4]:
                    self.root.after(0, lambda: self.gui.add_chat_status(
                        f"Network status changed: stat={stat}"
                    ))

    def _on_raw_serial(self, data: str):
        """Handle raw serial data for message log (SDD012)."""
        self.root.after(0, lambda: self.gui.add_raw_log(data))

    def _update_status(self, text: str):
        """Thread-safe status update."""
        self.root.after(0, lambda: self.gui.add_chat_status(text))

    def _connection_failed(self, reason: str):
        """Handle connection failure."""
        logger.error(f"Connection failed: {reason}")
        self.serial.disconnect()
        self.root.after(0, lambda: self.gui.update_connection_status("disconnected"))
        self.root.after(0, lambda: self.gui.add_chat_status(f"Connection failed: {reason}"))

    def run(self):
        """Start the application."""
        self.root.mainloop()


def main():
    """Entry point for the Remote Client Application."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = RemoteClientApp()
    app.run()


if __name__ == "__main__":
    main()
