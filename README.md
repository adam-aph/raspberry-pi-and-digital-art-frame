# E-Ink Digital Art Frame

## Purpose

This mini project implements a battery-powered, wall-mounted digital art frame using a large color E-Ink panel.
System wakes once per day, renders one artwork, then powers off completely.
Display retains image without power.

## Project Goals

- Create a low-power digital art frame that displays a different famous painting each day
- Utilize e-ink technology for paper-like viewing experience with minimal power consumption
- Implement battery operation with scheduled wake-up for daily refresh cycles
- Overcome hardware compatibility challenges between E-ink display and RTC power management

## Hardware Components

- **Display**: 13.3" E-Ink Spectra 6 (E6) Full Color E-Paper Display (1600×1200 pixels)
- **Controller**: Raspberry Pi Zero 2 W (1GHz quad-core ARM Cortex-A53, 512MB RAM)
- **Power Management**: Witty Pi 4 (Real-time clock with scheduled power control)
- **Battery**: 4× INR18650-32M Akyga batteries (4S configuration)
- **Controls**:
   - Restart button (wake-up trigger)
   - Maintenance switch (GPIO26, prevents auto-shutdown for SSH access)

## Project Structure

```
├── media/
│   ├── e6.jpg              # E-Ink Spectra 6 display photo
│   ├── pinout.jpg          # GPIO connection diagram
│   ├── r1.jpg              # Example artwork on frame
│   ├── r2.jpg              # Frame mounted on wall
│   └── r3.jpg              # Internal hardware setup
│
├── raspi/
│   ├── app/
│   │   ├── font/           # TrueType fonts (Arial variants)
│   │   ├── pic/            # Artwork BMP files + index.json
│   │   ├── lib/            # E6 display driver (SPI + GPIO)
│   │   ├── clear.py        # Display clear utility
│   │   └── refresh.py      # Main display refresh application
│   │
│   └── config/
│       ├── cmdline.txt     # Raspberry Pi boot parameters
│       ├── config.txt      # Raspberry Pi hardware configuration
│       ├── daily_update.wpi # Witty Pi schedule (2 AM daily wake)
│       ├── eink-update.service # Systemd service definition
│       └── os.txt          # Installation commands reference
│
└── tools/
   ├── scrap.py            # Download artwork from WikiArt
   ├── transform-json.py   # Generate index.json metadata
   └── convert.py          # Convert images to E6-compatible BMP
```

## Hardware Assembly

### E-Ink Display

<img src="https://github.com/adam-aph/raspberry-pi-and-digital-art-frame/blob/main/media/e6.jpg" width=50% height=50%>

### GPIO Pinout

<img src="https://github.com/adam-aph/raspberry-pi-and-digital-art-frame/blob/main/media/pinout.jpg" width=50% height=50%>

### Artwork Example

<img src="https://github.com/adam-aph/raspberry-pi-and-digital-art-frame/blob/main/media/r1.jpg" width=50% height=50%>

### Wall Mounted

<img src="https://github.com/adam-aph/raspberry-pi-and-digital-art-frame/blob/main/media/r2.jpg" width=50% height=50%>

### Internal Setup

<img src="https://github.com/adam-aph/raspberry-pi-and-digital-art-frame/blob/main/media/r3.jpg" width=50% height=50%>

## GPIO Connection Modifications

Due to GPIO conflicts between Witty Pi 4 and E6 HAT:

- **Issue**: Both devices use GPIO17 (Witty Pi control, E6 RST signal)
- **Solution**: Remapped E6 RST to GPIO27 in `lib/epdconfig.py`
- **Connection Method**: JST connector cables instead of stacking HAT directly
- **Maintenance Mode**: GPIO26 switch with LED indicator

## Python Application (`refresh.py`)

The main refresh script performs the following operations:

### Daily Cycle Logic

1. **Wake-up**: Raspberry Pi boots at 2 AM (Witty Pi schedule)
2. **Image Selection**: Calculates daily index based on days elapsed since January 2, 2026
3. **Data Caching**: Pre-loads artwork metadata and bitmap into memory before SPI operations
4. **Display Rendering**:
   - Loads 1600×1200 BMP artwork (pre-converted to 7-color Spectra 6 palette)
   - Draws vertical date text on right margin (rotated 90°, color-coded by index)
   - Draws vertical footer on left margin with:
      - Artwork metadata (number, artist, title, year)
      - Battery status (SOC% calculated from voltage via I2C)
5. **E-Ink Refresh**: Full display update via SPI interface
6. **Shutdown**: Automatic power-off (unless maintenance mode enabled)

### Battery Monitoring

- Reads 4S battery pack voltage via Witty Pi I2C interface (address 0x08)
- Estimates State of Charge using INR18650 discharge curve lookup table
- Applies temperature compensation (-3mV/°C per cell)
- Displays battery percentage in footer

### Maintenance Mode

- Activated via physical switch (GPIO26 LOW)
- Prevents automatic shutdown after refresh
- Enables SSH access for troubleshooting
- LED indicator shows maintenance mode active

## Artwork Preparation Pipeline

Source: <br>
https://www.wikiart.org/en/App/Painting/MostViewedPaintings

Steps:
1. Save metadata JSON as `MostViewedPaintings.json`
2. `scrap.py` downloads JPG images
3. `transform-json.py` creates index.json
4. `convert.py`:
   - resizes to 1600×1200
   - quantizes to Spectra 6 palette
   - outputs BMP files

Final assets stored in:
- raspi/app/pic/


## Technical Challenges & Solutions

### SIGBUS (Bus Error) & Filesystem Corruption

**Problem**: After display refresh, system encountered bus errors and filesystem corruption, requiring hard reset.

**Suspected Root Cause**: Kernel starvation and MMIO/IRQ livelock caused by long, non-yielding SPI + GPIO operations on PREEMPT kernel with active I2C device (Witty Pi).

**Attempted Solutions**:
1. Switched from BCM2835 low-level library to standard kernel SPI driver (`spidev`)
2. Reduced GPIO toggling frequency

**Final Workaround**:
- Pre-load all data (artwork, fonts, metadata) into memory before SPI initialization
- Execute display refresh without filesystem access
- **Immediate shutdown** after refresh completes

## OS Configuration

Documented in raspi/config/os.txt

Includes:
- SPI enabled
- Python dependencies:
   - pillow
   - numpy
   - spidev
   - RPi.GPIO
   - smbus2
- Witty Pi installation and I²C verification
- systemd service:
   - eink-update.service
   - runs refresh.py at boot
- boot parameter tuning via config.txt and cmdline.txt


## Daily Cycle

1. Witty Pi powers Raspberry Pi
2. Linux boots
3. eink-update.service runs
4. Display refreshed
5. Raspberry Pi shuts down
6. Image remains visible indefinitely

## License

Apache-2.0 license
<br>  
Artwork copyrights remain with original owners.
