"""World Map Widget for the Communicator Application (SDD002, SDD046).

Displays an outline map of the world using GeoPandas with Natural Earth dataset,
with markers for Remote Client locations.
"""

import logging
from typing import Optional

import matplotlib
matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import geopandas as gpd
import geodatasets
import tkinter as tk

logger = logging.getLogger(__name__)


class WorldMapWidget:
    """Embeddable world map widget using GeoPandas + Natural Earth."""

    def __init__(self, parent: tk.Frame):
        self.parent = parent
        self._fig, self._ax = plt.subplots(1, 1, figsize=(8, 3.5), dpi=80)
        self._fig.patch.set_facecolor("#f0f0f0")
        self._canvas = FigureCanvasTkAgg(self._fig, master=parent)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self._location_marker = None
        self._location_text = None
        self._location: Optional[tuple] = None

        self._draw_base_map()

    def _draw_base_map(self):
        """Draw the base world map using Natural Earth dataset."""
        try:
            world = gpd.read_file(geodatasets.data.naturalearth.land["url"])
            world.plot(
                ax=self._ax,
                color="#d4e6b5",
                edgecolor="#666666",
                linewidth=0.5,
            )
            self._ax.set_facecolor("#aadaff")
            self._ax.set_xlim([-180, 180])
            self._ax.set_ylim([-90, 90])
            self._ax.set_xlabel("Longitude")
            self._ax.set_ylabel("Latitude")
            self._ax.set_title("Remote Client Location")
            self._fig.tight_layout()
            self._canvas.draw()
            logger.info("World map loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load world map: {e}")
            self._ax.text(
                0.5, 0.5, "Map unavailable",
                transform=self._ax.transAxes, ha="center", va="center",
                fontsize=14, color="red",
            )
            self._canvas.draw()

    def update_location(self, latitude: float, longitude: float):
        """Update the Remote Client location marker on the map (SDD046).

        Args:
            latitude: Latitude with 6-decimal precision.
            longitude: Longitude with 6-decimal precision.
        """
        self._location = (latitude, longitude)

        # Remove old marker
        if self._location_marker:
            self._location_marker.remove()
        if self._location_text:
            self._location_text.remove()

        # Add new marker
        self._location_marker = self._ax.plot(
            longitude, latitude, "ro", markersize=10, markeredgecolor="darkred",
            markeredgewidth=1.5, zorder=5
        )[0]

        # Add label with full precision (SDD002)
        self._location_text = self._ax.annotate(
            f"  {latitude:.6f}, {longitude:.6f}",
            xy=(longitude, latitude),
            fontsize=8, color="darkred",
            fontweight="bold",
            zorder=6,
        )

        self._canvas.draw()
        logger.info(f"Map updated: {latitude:.6f}, {longitude:.6f}")

    def clear_location(self):
        """Remove the location marker."""
        if self._location_marker:
            self._location_marker.remove()
            self._location_marker = None
        if self._location_text:
            self._location_text.remove()
            self._location_text = None
        self._location = None
        self._canvas.draw()
