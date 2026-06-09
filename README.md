# Rocket Engine Testing Tool

Desktop application to read real-time thrust measurements from an Arduino + HX711 load cell, display live charts, and review saved test sessions.

## Stack

- **Python 3.10+**
- **Dear PyGui** — UI and charts
- **PySerial** — serial communication
- **SQLite3** — session storage (stdlib)

## Hardware

- Arduino with HX711 load cell amplifier
- DOUT = pin 3, CLK = pin 2
- Scale factor: -105.1428
- Arduino sends one float per line at 9600 baud

## Installation

```bash
pip install dearpygui pyserial
```

## Usage

```bash
python main.py
```

The app connects automatically to the port saved in `config.json`. If no Arduino is detected, it starts without serial and you can connect manually.

## Features

- **Live chart** — real-time thrust plot with sliding window
- **Tare** — sets the current reading as the zero reference
- **Start** — tares, clears the buffer, and begins recording
- **Stop / Resume** — pause and resume streaming without disconnecting
- **Save** — saves the current session to the SQLite database
- **Auto-save** — triggers automatically after reaching the configured sample limit
- **Saved sessions** — browse, view, and delete past test runs

## Configuration (`config.json`)

| Key | Default | Description |
|-----|---------|-------------|
| `serial_port` | `/dev/ttyUSB0` | Serial port (e.g. `COM3` on Windows) |
| `baud_rate` | `9600` | Serial baud rate |
| `data_samples` | `3000` | Samples before auto-save |
| `max_chart_points` | `100` | Points shown in the live chart |
| `db_path` | `./measures.db` | Path to the SQLite database |

## Project structure

```
rocket-measuring/
├── main.py               # entry point and UI
├── serial_reader.py      # serial reading thread
├── data_manager.py       # SQLite save/load
├── config.json           # persisted settings
├── measures.db           # created on first run
└── DejaVuSansMono.ttf    # bundled font (DejaVu license)
```
