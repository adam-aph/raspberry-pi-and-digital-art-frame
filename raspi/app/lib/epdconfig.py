# /*****************************************************************************
# * | File        :	  epdconfig.py
# * | Function    :   Hardware underlying interface
# * | Info        :
# *----------------
# * |	This version:   V1.1
# * | Author      :   adam_aph
# * | Date        :   2026-01-21
# * | Info        :   Updated to use SPIDEV only (requires dtparam=spi=on in config)
# * |             :   Changed EPD_RST_PIN = 27 (Physical 13) to avoid Witty Pi 4 conflict
# *----------------
# * |	This version:   V1.0
# * | Author      :   Waveshare electrices
# * | Date        :   2019-11-01
# * | Info        :   
# ******************************************************************************/
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
import time
import RPi.GPIO as GPIO
import spidev
import os

# ==============================
# BCM PIN ASSIGNMENTS (Hardware Pinout)
# ==============================
# SCLK: BCM 11 (Physical 23)
# MOSI: BCM 10 (Physical 19)
EPD_CS_M_PIN  = 8     # Master CS (Physical 24)
EPD_CS_S_PIN  = 7     # Slave CS (Physical 26)
EPD_DC_PIN    = 25    # Data/Command (Physical 22)
EPD_RST_PIN   = 27    # Reset (Physical 13) - MODIFIED to avoid Witty Pi conflict
EPD_BUSY_PIN  = 24    # Busy (Physical 18)
EPD_PWR_PIN   = 18    # Power control (Physical 12)

MT_SWITCH_PIN = 26    # Maintenance Switch (Physical 37)
MT_LED_PIN    = 6     # Maintenance LED (Physical 31)


class EPDConfig:
    def __init__(self):
        self.spi = spidev.SpiDev()
        
    def digital_write(self, pin, value):
        GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)

    def digital_read(self, pin):
        return GPIO.input(pin)

    def delay_ms(self, ms):
        time.sleep(ms / 1000.0)

    def spi_write_cmd_byte(self, data):
        """Used for Commands (DC Low)"""
        self.digital_write(EPD_DC_PIN, 0)
        time.sleep(0.000001)  # 1μs setup time
        # Hardware SPI handles the transfer
        self.spi.writebytes([data])

    def spi_write_data_byte(self, data):
        """Used for Data (DC High)."""
        self.digital_write(EPD_DC_PIN, 1)
        time.sleep(0.000001)  # 1μs setup time
        # Hardware SPI handles the transfer
        self.spi.writebytes([data])

    def spi_writebyte2(self, buf, length=None):
        """Used for Data (DC High). Optimized for large buffers."""
        self.digital_write(EPD_DC_PIN, 1)
        time.sleep(0.000001)  # 1μs setup time
        if isinstance(buf, list):
            buf = bytearray(buf)
        # Use memoryview to avoid slicing/copying large bytearrays
        self.spi.writebytes2(memoryview(buf)[:length] if length else memoryview(buf))
        # Ensure SPI transfer completes
        time.sleep(0.000005)  # 5µs safety margin

    def check_if_maintenance(self):
        if self.digital_read(MT_SWITCH_PIN) == GPIO.LOW:
            self.digital_write(MT_LED_PIN, 1)
            return True
        else:
            self.digital_write(MT_LED_PIN, 0)
            return False

    def module_init_1(self):
        # Configure GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # EPD
        GPIO.setup(EPD_CS_M_PIN, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(EPD_CS_S_PIN, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(EPD_DC_PIN,   GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(EPD_RST_PIN,  GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(EPD_PWR_PIN,  GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(EPD_BUSY_PIN, GPIO.IN)

        # MT
        GPIO.setup(MT_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(MT_LED_PIN, GPIO.OUT, initial=GPIO.LOW)

        self.delay_ms(10)
        return 0

    def module_init_2(self):
        # SPI SETTINGS (matching BCM2835 config):
        self.spi.open(0, 0)
        self.spi.mode = 0b00  # Mode 0: CPOL=0, CPHA=0
        self.spi.max_speed_hz = 4000000
        self.spi.bits_per_word = 8
        self.spi.lsbfirst = False  # MSB first

        # Disable hardware CS - we manage it manually
        self.spi.no_cs = True

        # Optional: These improve performance on Pi Zero
        # self.spi.threewire = False  # Full duplex
        # self.spi.loop = False       # No loopback

        # Power up the display
        self.digital_write(EPD_PWR_PIN, 1)

        self.delay_ms(10)
        return 0

    def module_exit(self):
        try:
            # 1. Flush Filesystem: Insurance against Witty Pi power-cuts
            os.sync()
            time.sleep(0.05)

            self.digital_write(EPD_RST_PIN, 1) # Set display to safe state BEFORE power-down
            time.sleep(0.01)
            self.digital_write(EPD_DC_PIN, 0)  # DC low = command mode (safe state)
            time.sleep(0.01)

            self.spi.close() # Close SPI WHILE display is still powered
            time.sleep(0.2)  # Wait for display charge pumps to discharge

            self.digital_write(EPD_PWR_PIN, 0) # Power down display
            time.sleep(0.2) # Final safety delay for OS buffers

            # DO NOT call GPIO.cleanup(). It unmaps memory and causes SIGBUS. 
            # GPIO.cleanup([EPD_DC_PIN, EPD_RST_PIN, EPD_PWR_PIN, EPD_BUSY_PIN])

        except Exception as e:
            print(f"Cleanup error: {e}")
            try:
                GPIO.output(EPD_PWR_PIN, GPIO.LOW)
            except:
                pass

# Export functions for epd12in48.py compatibility
config = EPDConfig()
digital_write = config.digital_write
digital_read = config.digital_read
delay_ms = config.delay_ms
spi_write_cmd_byte = config.spi_write_cmd_byte
spi_write_data_byte = config.spi_write_data_byte
spi_writebyte2 = config.spi_writebyte2
module_init_1 = config.module_init_1
module_init_2 = config.module_init_2
module_exit = config.module_exit
check_if_maintenance = config.check_if_maintenance

