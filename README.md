# IMOK - I'm OK

A two-way communication system using IoT devices via the Soracom API.

## Overview

IMOK consists of two applications:

1. **Remote Client Application** — Connects to an IoT device (Nordic Thingy:91 X or Murata Type 1SC-NTN) via serial port and communicates with the Communicator Application through Soracom Harvest Data.

2. **Communicator Application** — Desktop application that sends and receives messages to/from the Remote Client via the Soracom cloud API, displays the remote client's GPS location on a world map.

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`
- Soracom account with API access
- Supported IoT device (Nordic Thingy:91 X or Murata Type 1SC-NTN)

## Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running

### Remote Client Application
```bash
python run_remote_client.py
```

### Communicator Application
```bash
python run_communicator.py
```

## Architecture

```
src/
├── remote_client/          # Remote Client Application
│   ├── app.py              # Main application controller
│   ├── gui.py              # Tkinter GUI
│   ├── serial_manager.py   # Serial port management & AT commands
│   └── device_profiles/    # Device Profile Pattern (SDD030)
│       ├── base_profile.py # Abstract base class
│       ├── nordic_thingy91x.py  # Nordic Thingy:91 X profile
│       ├── murata_type1sc.py    # Murata Type 1SC-NTN profile
│       └── factory.py      # Device profile factory
├── communicator/           # Communicator Application
│   ├── app.py              # Main application controller
│   ├── gui.py              # Tkinter GUI
│   ├── soracom_api.py      # Soracom REST API client
│   └── map_widget.py       # World map (GeoPandas)
└── common/                 # Shared utilities
    └── message.py          # Message types & location format
config/
├── nordic_thingy91x.yaml   # Nordic device configuration
└── murata_type1sc_ntng.yaml # Murata device configuration
```

## Supported Devices

| Device | Manufacturer | Connection | RAT |
|--------|-------------|------------|-----|
| Thingy:91 X | Nordic Semiconductor | LTE-M | CAT-M1 |
| Type 1SC-NTN | Murata | NB-NTN | Satellite |

## Communication Flow

1. Remote Client connects to IoT device via serial port
2. IoT device registers on cellular/satellite network
3. Remote Client sends messages through Soracom Harvest Data (UDP)
4. Communicator polls Soracom Harvest Data API for new messages
5. Communicator sends downlink messages via Soracom API (UDP)
6. Remote Client receives downlink messages on UDP port 55555
