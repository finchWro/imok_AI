"""Remote Client Application GUI (SDD001, SDD003).

Tkinter-based GUI with connection status, chat area, and message log.
"""

import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class RemoteClientGUI:
    """GUI for the Remote Client Application."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("IMOK - Remote Client Application")
        self.root.geometry("800x700")
        self.root.minsize(600, 500)

        # Callbacks
        self._on_connect: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._on_send: Optional[Callable] = None
        self._on_clear_log: Optional[Callable] = None

        # Log filter state
        self._log_filter = "ALL"  # ALL, SEND, RECV

        self._build_gui()

    def _build_gui(self):
        """Build the complete GUI layout per SDD001."""
        # Main container
        main_frame = ttk.Frame(self.root, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === Connection Status Section (REQ004 / SDD006) ===
        self._build_connection_section(main_frame)

        # === Chat Area (REQ005 send / REQ006 receive) ===
        self._build_chat_section(main_frame)

        # === Message Log Section (REQ007 / SDD012) ===
        self._build_log_section(main_frame)

    def _build_connection_section(self, parent):
        """Build connection status indicator and controls."""
        conn_frame = ttk.LabelFrame(parent, text="Connection Status (REQ004)", padding=5)
        conn_frame.pack(fill=tk.X, pady=(0, 5))

        top_row = ttk.Frame(conn_frame)
        top_row.pack(fill=tk.X)

        # Status indicator canvas
        self._status_canvas = tk.Canvas(top_row, width=30, height=30, highlightthickness=0)
        self._status_canvas.pack(side=tk.LEFT, padx=5)
        self._status_circle = self._status_canvas.create_oval(5, 5, 25, 25, fill="red")

        self._status_label = ttk.Label(top_row, text="Disconnected", font=("Arial", 10, "bold"))
        self._status_label.pack(side=tk.LEFT, padx=5)

        # RSRP indicator
        self._rsrp_label = ttk.Label(top_row, text="RSRP: --", font=("Arial", 9))
        self._rsrp_label.pack(side=tk.RIGHT, padx=10)

        # Device selection and serial config
        config_row = ttk.Frame(conn_frame)
        config_row.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(config_row, text="Device:").pack(side=tk.LEFT, padx=(0, 5))
        self._device_var = tk.StringVar()
        self._device_combo = ttk.Combobox(
            config_row, textvariable=self._device_var, state="readonly", width=22
        )
        self._device_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(config_row, text="Port:").pack(side=tk.LEFT, padx=(0, 5))
        self._port_var = tk.StringVar()
        self._port_combo = ttk.Combobox(
            config_row, textvariable=self._port_var, width=10
        )
        self._port_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(config_row, text="Baud:").pack(side=tk.LEFT, padx=(0, 5))
        self._baud_var = tk.StringVar(value="9600")
        self._baud_combo = ttk.Combobox(
            config_row, textvariable=self._baud_var, width=8,
            values=["9600", "115200", "460800"]
        )
        self._baud_combo.pack(side=tk.LEFT, padx=(0, 10))

        self._connect_btn = ttk.Button(config_row, text="Connect", command=self._handle_connect)
        self._connect_btn.pack(side=tk.LEFT, padx=5)

        self._disconnect_btn = ttk.Button(
            config_row, text="Disconnect", command=self._handle_disconnect, state=tk.DISABLED
        )
        self._disconnect_btn.pack(side=tk.LEFT, padx=5)

    def _build_chat_section(self, parent):
        """Build chat area for sent and received messages."""
        chat_frame = ttk.LabelFrame(parent, text="Chat Area (REQ005 / REQ006)", padding=5)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Chat display
        self._chat_text = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, state=tk.DISABLED, height=12, font=("Consolas", 10)
        )
        self._chat_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Configure tags for message styling
        self._chat_text.tag_configure("sent", foreground="#0066cc")
        self._chat_text.tag_configure("received", foreground="#009933")
        self._chat_text.tag_configure("status", foreground="#999999", font=("Consolas", 9, "italic"))

        # Message input
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill=tk.X)

        self._msg_entry = ttk.Entry(input_frame, font=("Consolas", 10))
        self._msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self._msg_entry.bind("<Return>", lambda e: self._handle_send())

        self._send_btn = ttk.Button(
            input_frame, text="Send", command=self._handle_send, state=tk.DISABLED
        )
        self._send_btn.pack(side=tk.RIGHT)

    def _build_log_section(self, parent):
        """Build message log section (SDD012)."""
        log_frame = ttk.LabelFrame(parent, text="Message Log (REQ007)", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        # Filter controls
        filter_frame = ttk.Frame(log_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))

        self._filter_var = tk.StringVar(value="ALL")
        for text, value in [("All", "ALL"), ("Sent", "SEND"), ("Received", "RECV")]:
            rb = ttk.Radiobutton(
                filter_frame, text=text, value=value, variable=self._filter_var,
                command=self._apply_log_filter
            )
            rb.pack(side=tk.LEFT, padx=5)

        self._clear_log_btn = ttk.Button(
            filter_frame, text="Clear Log", command=self._handle_clear_log
        )
        self._clear_log_btn.pack(side=tk.RIGHT)

        # Log display
        self._log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, state=tk.DISABLED, height=8, font=("Consolas", 9)
        )
        self._log_text.pack(fill=tk.BOTH, expand=True)
        self._log_text.tag_configure("send_log", foreground="#0066cc")
        self._log_text.tag_configure("recv_log", foreground="#009933")

        # Internal log storage for filtering
        self._log_entries: list[tuple[str, str]] = []  # (direction, formatted_text)

    # === Public API ===

    def set_device_options(self, devices: list[dict]):
        """Set available devices in the dropdown."""
        self._device_combo["values"] = [d["name"] for d in devices]
        if devices:
            self._device_combo.current(0)

    def set_port_options(self, ports: list[str]):
        """Set available COM ports."""
        self._port_combo["values"] = ports
        if ports:
            self._port_combo.current(0)

    def set_callbacks(self, on_connect=None, on_disconnect=None,
                      on_send=None, on_clear_log=None):
        """Set callback functions for GUI events."""
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_send = on_send
        self._on_clear_log = on_clear_log

    def update_connection_status(self, status: str):
        """Update connection status indicator (SDD006).

        Args:
            status: 'connected', 'disconnected', or 'connecting'.
        """
        colors = {
            "connected": ("green", "Connected"),
            "disconnected": ("red", "Disconnected"),
            "connecting": ("yellow", "Connecting..."),
        }
        color, text = colors.get(status, ("red", "Unknown"))
        self._status_canvas.itemconfig(self._status_circle, fill=color)
        self._status_label.config(text=text)

        is_connected = status == "connected"
        self._connect_btn.config(state=tk.DISABLED if is_connected else tk.NORMAL)
        self._disconnect_btn.config(state=tk.NORMAL if is_connected else tk.DISABLED)
        self._send_btn.config(state=tk.NORMAL if is_connected else tk.DISABLED)
        self._device_combo.config(state="disabled" if is_connected else "readonly")
        self._port_combo.config(state="disabled" if is_connected else "normal")
        self._baud_combo.config(state="disabled" if is_connected else "normal")

    def update_rsrp(self, rsrp_dbm):
        """Update RSRP signal quality display."""
        if rsrp_dbm is None:
            self._rsrp_label.config(text="RSRP: --")
        else:
            self._rsrp_label.config(text=f"RSRP: {rsrp_dbm} dBm")

    def add_chat_message(self, text: str, direction: str, timestamp: datetime = None,
                         status: str = ""):
        """Add a message to the chat area.

        Args:
            text: Message content.
            direction: 'SEND' or 'RECV'.
            timestamp: Message timestamp.
            status: Status string for sent messages.
        """
        ts = (timestamp or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
        tag = "sent" if direction == "SEND" else "received"

        if direction == "SEND":
            status_str = f" ({status})" if status else ""
            formatted = f"[{ts}] [SEND] {text}{status_str}\n"
        else:
            formatted = f"[{ts}] [RECV] {text}\n"

        self._chat_text.config(state=tk.NORMAL)
        self._chat_text.insert(tk.END, formatted, tag)
        self._chat_text.see(tk.END)
        self._chat_text.config(state=tk.DISABLED)

        # Also add to log
        self._add_log_entry(direction, f"[{ts}] [{direction}] {text}")

    def add_chat_status(self, text: str):
        """Add a status message to the chat area."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{ts}] {text}\n"
        self._chat_text.config(state=tk.NORMAL)
        self._chat_text.insert(tk.END, formatted, "status")
        self._chat_text.see(tk.END)
        self._chat_text.config(state=tk.DISABLED)

    def add_raw_log(self, text: str):
        """Add raw serial data to the message log."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{ts}] {text}"
        tag = "send_log" if text.startswith("TX:") else "recv_log"
        self._log_entries.append(("RAW", entry))
        if self._log_filter == "ALL":
            self._log_text.config(state=tk.NORMAL)
            self._log_text.insert(tk.END, entry + "\n", tag)
            self._log_text.see(tk.END)
            self._log_text.config(state=tk.DISABLED)

    def get_selected_device(self) -> str:
        """Get currently selected device name."""
        return self._device_var.get()

    def get_selected_port(self) -> str:
        """Get currently selected COM port."""
        return self._port_var.get()

    def get_selected_baudrate(self) -> int:
        """Get currently selected baud rate."""
        try:
            return int(self._baud_var.get())
        except ValueError:
            return 9600

    # === Private Methods ===

    def _add_log_entry(self, direction: str, text: str):
        """Add structured entry to the message log."""
        self._log_entries.append((direction, text))
        tag = "send_log" if direction == "SEND" else "recv_log"

        if self._log_filter == "ALL" or self._log_filter == direction:
            self._log_text.config(state=tk.NORMAL)
            self._log_text.insert(tk.END, text + "\n", tag)
            self._log_text.see(tk.END)
            self._log_text.config(state=tk.DISABLED)

    def _apply_log_filter(self):
        """Apply log filter (SDD012)."""
        self._log_filter = self._filter_var.get()
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        for direction, text in self._log_entries:
            if self._log_filter == "ALL" or self._log_filter == direction:
                tag = "send_log" if direction == "SEND" else "recv_log"
                self._log_text.insert(tk.END, text + "\n", tag)
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    def _handle_connect(self):
        if self._on_connect:
            self._on_connect()

    def _handle_disconnect(self):
        if self._on_disconnect:
            self._on_disconnect()

    def _handle_send(self):
        msg = self._msg_entry.get().strip()
        if msg and self._on_send:
            self._on_send(msg)
            self._msg_entry.delete(0, tk.END)

    def _handle_clear_log(self):
        """Clear log with confirmation (SDD012)."""
        if messagebox.askyesno("Clear Log", "Are you sure you want to clear the message log?"):
            self._log_entries.clear()
            self._log_text.config(state=tk.NORMAL)
            self._log_text.delete("1.0", tk.END)
            self._log_text.config(state=tk.DISABLED)
            if self._on_clear_log:
                self._on_clear_log()
