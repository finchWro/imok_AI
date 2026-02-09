"""Communicator Application GUI (SDD002, SDD004).

Tkinter-based GUI with connection status, world map, chat area, and message log.
"""

import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class CommunicatorGUI:
    """GUI for the Communicator Application."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("IMOK - Communicator Application")
        self.root.geometry("900x850")
        self.root.minsize(700, 650)

        # Callbacks
        self._on_authenticate: Optional[Callable] = None
        self._on_send: Optional[Callable] = None
        self._on_refresh_sims: Optional[Callable] = None
        self._on_select_sim: Optional[Callable] = None
        self._on_clear_log: Optional[Callable] = None

        # Log filter
        self._log_filter = "ALL"

        self._build_gui()

    def _build_gui(self):
        """Build the complete GUI layout per SDD002."""
        main_frame = ttk.Frame(self.root, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === Connection Status Section (REQ008 / SDD024) ===
        self._build_connection_section(main_frame)

        # === World Map Section (REQ012 / SDD046) ===
        self._build_map_section(main_frame)

        # === Chat Area (REQ009 send / REQ010 receive) ===
        self._build_chat_section(main_frame)

        # === Message Log Section (REQ011) ===
        self._build_log_section(main_frame)

    def _build_connection_section(self, parent):
        """Build connection status and authentication controls."""
        conn_frame = ttk.LabelFrame(parent, text="Connection Status (REQ008)", padding=5)
        conn_frame.pack(fill=tk.X, pady=(0, 5))

        # Status row
        status_row = ttk.Frame(conn_frame)
        status_row.pack(fill=tk.X)

        self._status_canvas = tk.Canvas(status_row, width=30, height=30, highlightthickness=0)
        self._status_canvas.pack(side=tk.LEFT, padx=5)
        self._status_circle = self._status_canvas.create_oval(5, 5, 25, 25, fill="grey")

        self._status_label = ttk.Label(
            status_row, text="SIM Status: Unknown", font=("Arial", 10, "bold")
        )
        self._status_label.pack(side=tk.LEFT, padx=5)

        # Auth controls row
        auth_row = ttk.Frame(conn_frame)
        auth_row.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(auth_row, text="Auth Key ID:").pack(side=tk.LEFT, padx=(0, 5))
        self._auth_id_var = tk.StringVar()
        self._auth_id_entry = ttk.Entry(auth_row, textvariable=self._auth_id_var, width=25)
        self._auth_id_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(auth_row, text="Auth Key:").pack(side=tk.LEFT, padx=(0, 5))
        self._auth_key_var = tk.StringVar()
        self._auth_key_entry = ttk.Entry(auth_row, textvariable=self._auth_key_var, width=25, show="*")
        self._auth_key_entry.pack(side=tk.LEFT, padx=(0, 10))

        self._auth_btn = ttk.Button(auth_row, text="Authenticate", command=self._handle_auth)
        self._auth_btn.pack(side=tk.LEFT, padx=5)

        # SIM selection row
        sim_row = ttk.Frame(conn_frame)
        sim_row.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(sim_row, text="SIM:").pack(side=tk.LEFT, padx=(0, 5))
        self._sim_var = tk.StringVar()
        self._sim_combo = ttk.Combobox(
            sim_row, textvariable=self._sim_var, state="readonly", width=50
        )
        self._sim_combo.pack(side=tk.LEFT, padx=(0, 10))
        self._sim_combo.bind("<<ComboboxSelected>>", lambda e: self._handle_sim_select())

        self._refresh_sims_btn = ttk.Button(
            sim_row, text="Refresh SIMs", command=self._handle_refresh_sims, state=tk.DISABLED
        )
        self._refresh_sims_btn.pack(side=tk.LEFT, padx=5)

    def _build_map_section(self, parent):
        """Build world map section for remote client location."""
        self._map_frame = ttk.LabelFrame(
            parent, text="Remote Client Location (REQ012)", padding=5
        )
        self._map_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        # Map widget will be added by the app controller

    def _build_chat_section(self, parent):
        """Build chat area for sent and received messages."""
        chat_frame = ttk.LabelFrame(parent, text="Chat Area (REQ009 / REQ010)", padding=5)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self._chat_text = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 10)
        )
        self._chat_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

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
        """Build message log section."""
        log_frame = ttk.LabelFrame(parent, text="Message Log (REQ011)", padding=5)
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
            log_frame, wrap=tk.WORD, state=tk.DISABLED, height=6, font=("Consolas", 9)
        )
        self._log_text.pack(fill=tk.BOTH, expand=True)
        self._log_text.tag_configure("send_log", foreground="#0066cc")
        self._log_text.tag_configure("recv_log", foreground="#009933")

        self._log_entries: list[tuple[str, str]] = []

    # === Public API ===

    @property
    def map_frame(self) -> ttk.LabelFrame:
        """Get the map frame for embedding the map widget."""
        return self._map_frame

    def set_callbacks(self, on_authenticate=None, on_send=None,
                      on_refresh_sims=None, on_select_sim=None, on_clear_log=None):
        self._on_authenticate = on_authenticate
        self._on_send = on_send
        self._on_refresh_sims = on_refresh_sims
        self._on_select_sim = on_select_sim
        self._on_clear_log = on_clear_log

    def update_sim_status(self, status: Optional[bool]):
        """Update SIM status indicator (SDD024).

        Args:
            status: True=online, False=offline, None=unknown.
        """
        if status is True:
            color = "green"
            text = "SIM Status: Online"
        elif status is False:
            color = "red"
            text = "SIM Status: Offline"
        else:
            color = "grey"
            text = "SIM Status: Unknown"

        self._status_canvas.itemconfig(self._status_circle, fill=color)
        self._status_label.config(text=text)

        # Enable/disable send button based on status
        self._send_btn.config(state=tk.NORMAL if status is True else tk.DISABLED)

    def set_authenticated(self, success: bool):
        """Update UI after authentication."""
        if success:
            self._auth_btn.config(state=tk.DISABLED)
            self._refresh_sims_btn.config(state=tk.NORMAL)
            self._auth_id_entry.config(state=tk.DISABLED)
            self._auth_key_entry.config(state=tk.DISABLED)
        else:
            self._auth_btn.config(state=tk.NORMAL)

    def set_sim_list(self, sims: list[dict]):
        """Update SIM dropdown with inventory (SDD023)."""
        sim_names = []
        self._sim_data = sims
        for sim in sims:
            status_str = "online" if sim["online"] else "offline"
            sim_names.append(
                f"{sim['simId']} | IMSI: {sim['imsi']} | {status_str}"
            )
        self._sim_combo["values"] = sim_names
        if sim_names:
            self._sim_combo.current(0)
            self._handle_sim_select()

    def get_selected_sim_id(self) -> Optional[str]:
        """Get the simId of the currently selected SIM."""
        idx = self._sim_combo.current()
        if idx >= 0 and hasattr(self, '_sim_data') and idx < len(self._sim_data):
            return self._sim_data[idx]["simId"]
        return None

    def add_chat_message(self, text: str, direction: str, timestamp: datetime = None,
                         status: str = ""):
        """Add message to chat area (not to log area per SDD002 note)."""
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

        # Add to log
        self._add_log_entry(direction, f"[{ts}] [{direction}] {text}")

    def add_chat_status(self, text: str):
        """Add status message to chat area."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{ts}] {text}\n"
        self._chat_text.config(state=tk.NORMAL)
        self._chat_text.insert(tk.END, formatted, "status")
        self._chat_text.see(tk.END)
        self._chat_text.config(state=tk.DISABLED)

    # === Private Methods ===

    def _add_log_entry(self, direction: str, text: str):
        self._log_entries.append((direction, text))
        tag = "send_log" if direction == "SEND" else "recv_log"
        if self._log_filter == "ALL" or self._log_filter == direction:
            self._log_text.config(state=tk.NORMAL)
            self._log_text.insert(tk.END, text + "\n", tag)
            self._log_text.see(tk.END)
            self._log_text.config(state=tk.DISABLED)

    def _apply_log_filter(self):
        self._log_filter = self._filter_var.get()
        self._log_text.config(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        for direction, text in self._log_entries:
            if self._log_filter == "ALL" or self._log_filter == direction:
                tag = "send_log" if direction == "SEND" else "recv_log"
                self._log_text.insert(tk.END, text + "\n", tag)
        self._log_text.see(tk.END)
        self._log_text.config(state=tk.DISABLED)

    def _handle_auth(self):
        if self._on_authenticate:
            self._on_authenticate(self._auth_id_var.get(), self._auth_key_var.get())

    def _handle_send(self):
        msg = self._msg_entry.get().strip()
        if msg and self._on_send:
            self._on_send(msg)
            self._msg_entry.delete(0, tk.END)

    def _handle_refresh_sims(self):
        if self._on_refresh_sims:
            self._on_refresh_sims()

    def _handle_sim_select(self):
        if self._on_select_sim:
            sim_id = self.get_selected_sim_id()
            if sim_id:
                self._on_select_sim(sim_id)

    def _handle_clear_log(self):
        if messagebox.askyesno("Clear Log", "Are you sure you want to clear the message log?"):
            self._log_entries.clear()
            self._log_text.config(state=tk.NORMAL)
            self._log_text.delete("1.0", tk.END)
            self._log_text.config(state=tk.DISABLED)
            if self._on_clear_log:
                self._on_clear_log()
