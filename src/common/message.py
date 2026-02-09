"""Common message types and utilities shared between Remote Client and Communicator."""

import json
from datetime import datetime


class Message:
    """Represents a chat message with metadata."""

    def __init__(self, text: str, direction: str, timestamp: datetime = None, status: str = ""):
        """
        Args:
            text: The message content.
            direction: 'SEND' or 'RECV'.
            timestamp: When the message was created/received.
            status: Message status (e.g., 'success', 'failure', 'received').
        """
        self.text = text
        self.direction = direction
        self.timestamp = timestamp or datetime.now()
        self.status = status

    def format_for_chat(self) -> str:
        """Format message for display in chat area."""
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        if self.direction == "SEND":
            status_str = f" ({self.status})" if self.status else ""
            return f"[{ts}] [SEND] {self.text}{status_str}"
        else:
            return f"[{ts}] [RECV] {self.text}"

    def format_for_log(self) -> str:
        """Format message for display in message log."""
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return f"[{ts}] [{self.direction}] {self.text}"


class LocationMessage:
    """Represents a location message per SDD047."""

    def __init__(self, latitude: str, longitude: str):
        self.latitude = latitude
        self.longitude = longitude

    def encode(self) -> str:
        """Encode location to JSON format per SDD047."""
        return json.dumps(["LOCATION", self.latitude, self.longitude])

    @staticmethod
    def decode(data: str):
        """Decode a location message. Returns LocationMessage or None."""
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list) and len(parsed) == 3 and parsed[0] == "LOCATION":
                return LocationMessage(parsed[1], parsed[2])
        except (json.JSONDecodeError, IndexError):
            pass
        return None
