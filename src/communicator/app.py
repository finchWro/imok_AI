"""Communicator Application (SDD002, SDD004, SDD020).

Main application logic orchestrating the GUI, Soracom API,
world map, and message handling.
"""

import logging
import os
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from typing import Optional

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.communicator.gui import CommunicatorGUI
from src.communicator.soracom_api import SoracomAPI
from src.communicator.map_widget import WorldMapWidget
from src.common.message import LocationMessage

logger = logging.getLogger(__name__)

# Polling interval for Harvest Data (SDD029: every 5 seconds)
HARVEST_POLL_INTERVAL = 5


class CommunicatorApp:
    """Main Communicator Application controller."""

    def __init__(self):
        self.root = tk.Tk()
        self.gui = CommunicatorGUI(self.root)
        self.api = SoracomAPI()
        self.map_widget: Optional[WorldMapWidget] = None

        self._selected_sim_id: Optional[str] = None
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None

        self._setup()

    def _setup(self):
        """Initialize the application."""
        # Set up map widget
        self.map_widget = WorldMapWidget(self.gui.map_frame)

        # Set callbacks
        self.gui.set_callbacks(
            on_authenticate=self._on_authenticate,
            on_send=self._on_send,
            on_refresh_sims=self._on_refresh_sims,
            on_select_sim=self._on_select_sim,
            on_clear_log=lambda: logger.info("Log cleared"),
        )

        # Clean up on window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_authenticate(self, auth_id: str, auth_key: str):
        """Handle authentication (SDD021)."""
        if not auth_id or not auth_key:
            self.gui.add_chat_status("Error: Please enter Auth Key ID and Auth Key")
            return

        self.gui.add_chat_status("Authenticating...")

        def do_auth():
            success = self.api.authenticate(auth_id, auth_key)
            self.root.after(0, lambda: self._auth_complete(success))

        threading.Thread(target=do_auth, daemon=True).start()

    def _auth_complete(self, success: bool):
        """Handle authentication result."""
        self.gui.set_authenticated(success)
        if success:
            self.gui.add_chat_status("Authentication successful!")
            self._on_refresh_sims()
        else:
            self.gui.add_chat_status("Authentication failed. Check credentials.")

    def _on_refresh_sims(self):
        """Refresh SIM list (SDD023)."""
        self.gui.add_chat_status("Fetching SIM list...")

        def do_fetch():
            sims = self.api.list_sims()
            self.root.after(0, lambda: self._sims_loaded(sims))

        threading.Thread(target=do_fetch, daemon=True).start()

    def _sims_loaded(self, sims: list[dict]):
        """Handle SIM list result."""
        if sims:
            self.gui.set_sim_list(sims)
            self.gui.add_chat_status(f"Found {len(sims)} SIM(s)")
        else:
            self.gui.add_chat_status("No SIMs found or request failed")

    def _on_select_sim(self, sim_id: str):
        """Handle SIM selection (SDD024)."""
        self._selected_sim_id = sim_id
        logger.info(f"Selected SIM: {sim_id}")

        # Update status
        def check_status():
            status = self.api.get_sim_status(sim_id)
            self.root.after(0, lambda: self.gui.update_sim_status(status))
            # Start polling if online
            if status:
                self._start_polling()

        threading.Thread(target=check_status, daemon=True).start()

    def _on_send(self, message: str):
        """Handle send message (SDD025)."""
        if not self._selected_sim_id:
            self.gui.add_chat_status("Error: No SIM selected")
            return

        self.gui.add_chat_message(message, "SEND", status="sending...")

        def do_send():
            success, status_msg = self.api.send_downlink_udp(
                self._selected_sim_id, message
            )
            status = "success" if success else f"failure: {status_msg}"
            self.root.after(0, lambda: self.gui.add_chat_message(
                message, "SEND", status=status
            ))

        threading.Thread(target=do_send, daemon=True).start()

    def _start_polling(self):
        """Start polling Soracom Harvest Data for new messages (SDD029)."""
        if self._polling:
            return

        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        logger.info("Started Harvest Data polling")

    def _stop_polling(self):
        """Stop polling."""
        self._polling = False
        if self._poll_thread:
            self._poll_thread.join(timeout=10)
            self._poll_thread = None

    def _poll_loop(self):
        """Polling loop for Harvest Data (SDD029: every 5 seconds)."""
        while self._polling and self._selected_sim_id:
            try:
                messages = self.api.get_harvest_data(self._selected_sim_id)
                for msg in messages:
                    content = msg["content"]
                    timestamp = msg["time"]

                    # Convert timestamp
                    try:
                        ts = datetime.fromtimestamp(timestamp / 1000)
                    except (ValueError, OSError):
                        ts = datetime.now()

                    # Check for location message (SDD046/SDD047)
                    loc = LocationMessage.decode(content)
                    if loc:
                        try:
                            lat = float(loc.latitude)
                            lon = float(loc.longitude)
                            self.root.after(0, lambda la=lat, lo=lon: self.map_widget.update_location(la, lo))
                            self.root.after(0, lambda la=lat, lo=lon: self.gui.add_chat_status(
                                f"Location update: {la:.6f}, {lo:.6f}"
                            ))
                        except ValueError:
                            pass
                    else:
                        # Regular message — display in chat (SDD029)
                        self.root.after(0, lambda c=content, t=ts: self.gui.add_chat_message(
                            c, "RECV", timestamp=t
                        ))

            except Exception as e:
                logger.error(f"Polling error: {e}")

            time.sleep(HARVEST_POLL_INTERVAL)

    def _on_close(self):
        """Handle window close."""
        self._stop_polling()
        self.root.destroy()

    def run(self):
        """Start the application."""
        self.root.mainloop()


def main():
    """Entry point for the Communicator Application."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = CommunicatorApp()
    app.run()


if __name__ == "__main__":
    main()
