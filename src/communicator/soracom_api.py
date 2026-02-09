"""Soracom API Client (SDD021, SDD023, SDD025, SDD029, SDD043).

Handles authentication, SIM management, message sending/receiving
via the Soracom REST API.
"""

import base64
import json
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SORACOM_API_BASE = "https://g.api.soracom.io/v1"


class SoracomAPI:
    """Client for the Soracom REST API."""

    def __init__(self):
        self._api_key: Optional[str] = None
        self._token: Optional[str] = None
        self._operator_id: Optional[str] = None
        self._last_harvest_timestamp: Optional[int] = None

    @property
    def is_authenticated(self) -> bool:
        return self._api_key is not None and self._token is not None

    def authenticate(self, auth_key_id: str, auth_key: str) -> bool:
        """Authenticate with Soracom API using auth key (SDD021).

        Args:
            auth_key_id: The Soracom Auth Key ID or email.
            auth_key: The Soracom Auth Key or password.

        Returns:
            True if authentication was successful.
        """
        try:
            # Try auth key authentication first
            payload = {
                "authKeyId": auth_key_id,
                "authKey": auth_key,
            }
            response = requests.post(
                f"{SORACOM_API_BASE}/auth",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code != 200:
                # Try email/password authentication
                payload = {
                    "email": auth_key_id,
                    "password": auth_key,
                }
                response = requests.post(
                    f"{SORACOM_API_BASE}/auth",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )

            if response.status_code == 200:
                data = response.json()
                self._api_key = data.get("apiKey")
                self._token = data.get("token")
                self._operator_id = data.get("operatorId")
                logger.info("Soracom authentication successful")
                return True
            else:
                logger.error(
                    f"Authentication failed: {response.status_code} - {response.text}"
                )
                return False
        except requests.RequestException as e:
            logger.error(f"Authentication request failed: {e}")
            return False

    def _get_headers(self) -> dict:
        """Get authenticated API headers."""
        return {
            "X-Soracom-API-Key": self._api_key,
            "X-Soracom-Token": self._token,
            "Content-Type": "application/json",
        }

    def list_sims(self) -> list[dict]:
        """List SIMs associated with the user account (SDD023).

        Returns:
            List of SIM dictionaries with simId, imsi, and online status.
        """
        if not self.is_authenticated:
            logger.error("Not authenticated")
            return []

        try:
            response = requests.get(
                f"{SORACOM_API_BASE}/sims",
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 200:
                sims_raw = response.json()
                sims = []
                for sim in sims_raw:
                    sim_id = sim.get("simId", "")
                    # Extract session status
                    session_status = sim.get("sessionStatus", {})
                    imsi = session_status.get("imsi", "N/A") if session_status else "N/A"
                    online = session_status.get("online", False) if session_status else False

                    sims.append({
                        "simId": sim_id,
                        "imsi": imsi,
                        "online": online,
                    })
                logger.info(f"Retrieved {len(sims)} SIMs")
                return sims
            else:
                logger.error(f"Failed to list SIMs: {response.status_code}")
                return []
        except requests.RequestException as e:
            logger.error(f"List SIMs request failed: {e}")
            return []

    def send_downlink_udp(self, sim_id: str, message: str, port: int = 55555) -> tuple[bool, str]:
        """Send downlink UDP message to a SIM (SDD025).

        Args:
            sim_id: Target SIM ID.
            message: Message text to send.
            port: UDP port (default 55555 per SDD026).

        Returns:
            Tuple of (success: bool, status_message: str).
        """
        if not self.is_authenticated:
            return False, "Not authenticated"

        try:
            # Encode message as base64 for the payload
            encoded = base64.b64encode(message.encode("utf-8")).decode("utf-8")
            payload = {
                "port": port,
                "payloadType": "base64",
                "payload": encoded,
            }

            response = requests.post(
                f"{SORACOM_API_BASE}/sims/{sim_id}/downlink/udp",
                json=payload,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 204:
                logger.info(f"Message sent successfully to SIM {sim_id}")
                return True, "success"
            else:
                error_msg = f"Code {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = f"Code {response.status_code}: {error_data.get('message', '')}"
                except Exception:
                    pass
                logger.error(f"Send failed: {error_msg}")
                return False, error_msg
        except requests.RequestException as e:
            logger.error(f"Send request failed: {e}")
            return False, str(e)

    def get_harvest_data(self, sim_id: str) -> list[dict]:
        """Get data from Soracom Harvest Data (SDD029).

        Retrieves only new messages since the last fetch.

        Args:
            sim_id: SIM ID to get data for.

        Returns:
            List of data entries with decoded content.
        """
        if not self.is_authenticated:
            return []

        try:
            params = {
                "sort": "asc",
                "limit": 100,
            }
            if self._last_harvest_timestamp:
                params["from"] = self._last_harvest_timestamp + 1

            response = requests.get(
                f"{SORACOM_API_BASE}/sims/{sim_id}/data",
                headers=self._get_headers(),
                params=params,
                timeout=30,
            )

            if response.status_code == 200:
                entries = response.json()
                messages = []
                for entry in entries:
                    timestamp = entry.get("time", 0)
                    content = entry.get("content", {})

                    # Track last timestamp to avoid duplicates
                    if timestamp > (self._last_harvest_timestamp or 0):
                        self._last_harvest_timestamp = timestamp

                    # Decode payload from base64 (SDD029)
                    payload_b64 = ""
                    if isinstance(content, dict):
                        payload_b64 = content.get("payload", "")
                    elif isinstance(content, str):
                        try:
                            content_dict = json.loads(content)
                            payload_b64 = content_dict.get("payload", "")
                        except json.JSONDecodeError:
                            payload_b64 = content

                    try:
                        decoded = base64.b64decode(payload_b64).decode("utf-8")
                    except Exception:
                        decoded = payload_b64

                    messages.append({
                        "time": timestamp,
                        "content": decoded,
                    })

                return messages
            else:
                logger.error(f"Harvest data fetch failed: {response.status_code}")
                return []
        except requests.RequestException as e:
            logger.error(f"Harvest data request failed: {e}")
            return []

    def get_sim_status(self, sim_id: str) -> Optional[bool]:
        """Get online status of a specific SIM.

        Returns:
            True if online, False if offline, None if unknown.
        """
        if not self.is_authenticated:
            return None

        try:
            response = requests.get(
                f"{SORACOM_API_BASE}/sims/{sim_id}",
                headers=self._get_headers(),
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                session = data.get("sessionStatus", {})
                return session.get("online", False) if session else False
            return None
        except requests.RequestException:
            return None
