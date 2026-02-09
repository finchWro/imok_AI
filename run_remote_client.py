"""Entry point for the IMOK Remote Client Application."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.remote_client.app import main

if __name__ == "__main__":
    main()
