"""Serial port manager for AT command communication with IoT devices.

Handles low-level serial I/O, command/response separation, and URC handling.
Implements SDD017 (AT commands per ITU-T V.250).
"""

import logging
import threading
import time
from typing import Callable, Optional

import serial

logger = logging.getLogger(__name__)


class SerialManager:
    """Manages serial communication with IoT devices."""

    def __init__(self):
        self._serial: Optional[serial.Serial] = None
        self._read_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._response_buffer: list[str] = []
        self._response_event = threading.Event()
        self._urc_callbacks: list[Callable[[str], None]] = []
        self._raw_callbacks: list[Callable[[str], None]] = []
        self._expected_final: list[str] = ["OK", "ERROR"]
        self._command_timeout = 30  # seconds

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self, port: str, baudrate: int = 9600, timeout: float = 1.0) -> bool:
        """Open serial connection to the device."""
        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout,
            )
            self._running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            logger.info(f"Connected to {port} at {baudrate} baud")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {port}: {e}")
            return False

    def disconnect(self):
        """Close serial connection."""
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=2)
            self._read_thread = None
        if self._serial and self._serial.is_open:
            self._serial.close()
            self._serial = None
        logger.info("Disconnected from serial port")

    def register_urc_callback(self, callback: Callable[[str], None]):
        """Register a callback for unsolicited result codes (URCs)."""
        self._urc_callbacks.append(callback)

    def register_raw_callback(self, callback: Callable[[str], None]):
        """Register a callback for all raw serial data (for message log)."""
        self._raw_callbacks.append(callback)

    def send_command(self, command: str, timeout: float = None,
                     expected_final: list[str] = None) -> tuple[bool, list[str]]:
        """Send AT command and wait for response.

        Args:
            command: The AT command string.
            timeout: Response timeout in seconds.
            expected_final: List of strings indicating end of response.

        Returns:
            Tuple of (success: bool, response_lines: list[str]).
        """
        if not self.is_connected:
            logger.error("Cannot send command: not connected")
            return False, []

        timeout = timeout or self._command_timeout
        finals = expected_final or self._expected_final

        with self._lock:
            self._response_buffer.clear()
            self._response_event.clear()

            # Store finals for the read loop
            self._current_finals = finals

            # Send the command
            cmd = command.strip() + "\r\n"
            self._serial.write(cmd.encode("utf-8"))
            logger.debug(f"TX: {command}")
            for cb in self._raw_callbacks:
                cb(f"TX: {command}")

            # Wait for response
            if self._response_event.wait(timeout):
                lines = list(self._response_buffer)
                success = any(
                    any(f in line for f in ["OK"]) for line in lines
                ) or any(
                    any(f in line for f in finals if f != "ERROR") for line in lines
                )
                # Check for explicit error
                if any("ERROR" in line for line in lines):
                    success = False
                return success, lines
            else:
                logger.warning(f"Timeout waiting for response to: {command}")
                return False, list(self._response_buffer)

    def send_command_wait_urc(self, command: str, urc_prefix: str,
                               timeout: float = 60) -> tuple[bool, list[str], str]:
        """Send AT command and wait for a specific URC.

        Returns:
            Tuple of (success, response_lines, urc_line).
        """
        urc_received = threading.Event()
        urc_line_holder = [None]

        def urc_catcher(line: str):
            if urc_prefix in line:
                urc_line_holder[0] = line
                urc_received.set()

        self._urc_callbacks.append(urc_catcher)
        try:
            success, lines = self.send_command(command, timeout=10)
            if urc_received.wait(timeout):
                return True, lines, urc_line_holder[0]
            else:
                logger.warning(f"Timeout waiting for URC: {urc_prefix}")
                return False, lines, ""
        finally:
            self._urc_callbacks.remove(urc_catcher)

    def wait_for_urc(self, urc_prefix: str, timeout: float = 60) -> tuple[bool, str]:
        """Wait for a specific URC without sending a command.

        Returns:
            Tuple of (received: bool, urc_line: str).
        """
        urc_received = threading.Event()
        urc_line_holder = [None]

        def urc_catcher(line: str):
            if urc_prefix in line:
                urc_line_holder[0] = line
                urc_received.set()

        self._urc_callbacks.append(urc_catcher)
        try:
            if urc_received.wait(timeout):
                return True, urc_line_holder[0]
            else:
                return False, ""
        finally:
            self._urc_callbacks.remove(urc_catcher)

    def _read_loop(self):
        """Background thread reading serial data."""
        buffer = ""
        while self._running:
            try:
                if self._serial and self._serial.is_open and self._serial.in_waiting:
                    data = self._serial.read(self._serial.in_waiting).decode("utf-8", errors="replace")
                    buffer += data

                    while "\r\n" in buffer or "\n" in buffer:
                        if "\r\n" in buffer:
                            line, buffer = buffer.split("\r\n", 1)
                        else:
                            line, buffer = buffer.split("\n", 1)

                        line = line.strip()
                        if not line:
                            continue

                        logger.debug(f"RX: {line}")
                        for cb in self._raw_callbacks:
                            cb(f"RX: {line}")

                        # Check if this is a final response
                        finals = getattr(self, '_current_finals', self._expected_final)
                        is_final = any(f in line for f in finals)

                        if is_final:
                            self._response_buffer.append(line)
                            self._response_event.set()
                        elif self._is_urc(line):
                            # Deliver URC to callbacks
                            for cb in self._urc_callbacks:
                                try:
                                    cb(line)
                                except Exception as e:
                                    logger.error(f"URC callback error: {e}")
                        else:
                            # Part of command response
                            self._response_buffer.append(line)
                else:
                    time.sleep(0.01)
            except Exception as e:
                if self._running:
                    logger.error(f"Serial read error: {e}")
                time.sleep(0.1)

    def _is_urc(self, line: str) -> bool:
        """Check if a line is an unsolicited result code."""
        urc_prefixes = [
            "+CEREG:", "+CSCON:", "%CESQ:", "%SOCKETEV:", "%SOCKETCMD:",
            "%BOOTEV:", "%IGNSSEVU:", "%NOTIFYEV:", "%MEAS:", "%PINGCMD:",
        ]
        return any(line.startswith(prefix) for prefix in urc_prefixes)
