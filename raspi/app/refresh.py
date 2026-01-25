#!/usr/bin/python
# -*- coding:utf-8 -*-
# /*****************************************************************************
# * | File        :       refresh.py
# * | Function    :   Refresh EPD display
# * | Info        :
# * | This version:   V1.0
# * | Author      :   adam_aph
# * | Date        :   2026-01-21
# * | Info        :   Initial release
# *----------------
# ******************************************************************************/

import sys
import os
import io
import traceback

current_dir = os.path.dirname(os.path.realpath(__file__))
picdir = os.path.join(current_dir, 'pic')
libdir = os.path.join(current_dir, 'lib')
fontdir = os.path.join(current_dir, 'font')
sys.path.append(libdir)

import epd13in3E
import time
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import json
from typing import Tuple
from smbus2 import SMBus

epd = epd13in3E.EPD()
json_cache = []
image_cache = None

NBR_IMAGES = 600

DISPLAY_W = 1600
DISPLAY_H = 1200

RIGHT_MARGIN = 80   # physical top after rotation
LEFT_MARGIN = 50     # physical bottom after rotation

IMAGE_AREA_W = DISPLAY_W - LEFT_MARGIN - RIGHT_MARGIN
IMAGE_AREA_H = DISPLAY_H

DATE_FONT_SIZE = 60
FOOTER_FONT_SIZE = 30
FOOTER_FONT_SIZE_SMALL = 18

I2C_BUS = 1
I2C_MC_ADDRESS = 0x08
I2C_VOLTAGE_IN_I = 1
I2C_VOLTAGE_IN_D = 2
I2C_LM75B_TEMPERATURE = 50

try:
    font_regular = ImageFont.truetype(os.path.join(fontdir, "arial.ttf"), FOOTER_FONT_SIZE)
    font_regular_small = ImageFont.truetype(os.path.join(fontdir, "arial.ttf"), FOOTER_FONT_SIZE_SMALL)
    font_bold = ImageFont.truetype(os.path.join(fontdir, "arialbd.ttf"), DATE_FONT_SIZE)
    font_italic = ImageFont.truetype(os.path.join(fontdir, "ariali.ttf"), FOOTER_FONT_SIZE)
except Exception:
    font_regular = ImageFont.truetype(os.path.join(fontdir, "Font.ttc"), FOOTER_FONT_SIZE)
    font_regular_small = ImageFont.truetype(os.path.join(fontdir, "Font.ttc"), FOOTER_FONT_SIZE_SMALL)
    font_bold = ImageFont.truetype(os.path.join(fontdir, "Font.ttc"), DATE_FONT_SIZE)
    font_italic = ImageFont.truetype(os.path.join(fontdir, "Font.ttc"), FOOTER_FONT_SIZE)

def get_input_voltage():
    """
    Reads the integer and decimal parts of the input voltage 
    from the Witty Pi 4 micro-controller.
    """
    try:
        # We use a context manager to ensure the bus is closed properly
        with SMBus(I2C_BUS) as bus:
            # Read the integer part (Index 1)
            volt_i = bus.read_byte_data(I2C_MC_ADDRESS, I2C_VOLTAGE_IN_I)
            
            # Read the decimal part (Index 2)
            volt_d = bus.read_byte_data(I2C_MC_ADDRESS, I2C_VOLTAGE_IN_D)
            
            # Calculate the total voltage: Integer + (Decimal / 100)
            voltage = volt_i + (volt_d / 100.0)
            return round(voltage, 2)
            
    except Exception as e:
        print(f"Error reading from I2C bus: {e}")
        return None

def soc_from_voltage(v_pack):
    """
    Estimate State of Charge (%) for a 4S INR18650 pack.

    Based on typical INR18650 (e.g., Samsung 25R, LG HG2, Sony VTC6)
    discharge characteristics at ~0.2C rate, 25°C, and Open Circuit Voltage.

    Args:
        v_pack: Pack voltage in volts (measured at rest, OCV)

    Returns:
        float: Estimated SOC in percentage (0-100)

    Notes:
        - Voltage must be measured after 30+ min rest for accurate OCV
        - Temperature significantly affects voltage readings
        - Cell imbalance can cause errors in pack-level estimation
        - Aging shifts the curve downward
    """
    # Voltage breakpoints (4S pack) - 5% granularity
    # Based on typical INR18650 OCV curve (3.6V nominal per cell)
    points = [
        (16.80, 100),  # 4.20V/cell - fully charged
        (16.60, 95),   # 4.15V/cell
        (16.44, 90),   # 4.11V/cell
        (16.28, 85),   # 4.07V/cell
        (16.12, 80),   # 4.03V/cell
        (15.96, 75),   # 3.99V/cell
        (15.80, 70),   # 3.95V/cell - beginning of plateau
        (15.64, 65),   # 3.91V/cell
        (15.48, 60),   # 3.87V/cell
        (15.32, 55),   # 3.83V/cell
        (15.16, 50),   # 3.79V/cell - mid-plateau
        (15.00, 45),   # 3.75V/cell
        (14.84, 40),   # 3.71V/cell
        (14.68, 35),   # 3.67V/cell - end of plateau
        (14.48, 30),   # 3.62V/cell - knee begins
        (14.24, 25),   # 3.56V/cell
        (13.96, 20),   # 3.49V/cell - steeper decline
        (13.64, 15),   # 3.41V/cell
        (13.28, 10),   # 3.32V/cell
        (12.80, 5),    # 3.20V/cell - critical low
        (12.00, 0)     # 3.00V/cell - cutoff (protect cells)
    ]

    # Clamp to valid range
    if v_pack >= points[0][0]:
        return 100
    if v_pack <= points[-1][0]:
        return 0

    # Linear interpolation between breakpoints
    for i in range(len(points) - 1):
        v1, soc1 = points[i]
        v2, soc2 = points[i + 1]
        if v2 <= v_pack <= v1:
            # Linear interpolation formula
            soc = soc2 + (soc1 - soc2) * (v_pack - v2) / (v1 - v2)
            return round(soc)

    return 0

def soc_from_voltage_compensated(v_pack, temp_c=25.0):
    """
    Temperature-compensated SOC estimation.

    Args:
        v_pack: Pack voltage in volts (OCV)
        temp_c: Battery temperature in Celsius

    Returns:
        float: Estimated SOC in percentage
    """
    # Temperature compensation: ~-3mV/°C per cell for Li-ion
    temp_offset_per_cell = -0.003 * (temp_c - 25.0)
    v_compensated = v_pack - (4 * temp_offset_per_cell)

    return soc_from_voltage(v_compensated)

def get_temperature():
    """
    Reads the LM75B temperature sensor on the Witty Pi 4.
    Returns a tuple of (Celsius, Fahrenheit).
    """
    try:
        with SMBus(I2C_BUS) as bus:
            # Read a 16-bit word from register 50
            # smbus2 read_word_data returns little-endian (LSB, MSB)
            raw_data = bus.read_word_data(I2C_MC_ADDRESS, I2C_LM75B_TEMPERATURE)

            # 1. Byte Swap: The LM75B provides MSB first.
            # We need to swap the bytes to match the sensor's internal alignment.
            swapped = ((raw_data & 0xFF) << 8) | (raw_data >> 8)

            # 2. Shift: The 11-bit temperature value is left-justified.
            # We shift right by 5 bits to get the actual 11-bit integer.
            temp_raw = swapped >> 5

            # 3. Handle Negative Values (Two's Complement):
            # If the 11th bit (0x400) is set, the temperature is negative.
            if temp_raw & 0x400:
                temp_raw -= 2048

            # 4. Scale: Each LSB represents 0.125 degrees Celsius.
            celsius = temp_raw * 0.125
            fahrenheit = (celsius * 1.8) + 32

            return round(celsius, 2), round(fahrenheit, 2)

    except Exception as e:
        print(f"Error reading temperature: {e}")
        return None, None

# the same which is used by original Waveshare library
ACTUAL_PALETTE = [
    0, 0, 0,        # Black
    255, 255, 255,  # White
    255, 255, 0,    # Green
    255, 0, 0,      # Blue
    0, 0, 0,        # Red
    0, 0, 255,      # Yellow
    0, 255, 0       # Orange
] + [0, 0, 0] * 249 # Fill remaining 256 slots

BLACK_IDX  = 0
WHITE_IDX  = 1
MASK_IDX   = WHITE_IDX   # safe background index

FONT_COLORS = [
    (0, 0, 0),      # Black
    (0, 0, 255),    # Blue
    (255, 0, 0),    # Red
    (0, 255, 0),    # Green
]

def waveshare_palette():
    pal = Image.new("P", (1, 1))
    pal.putpalette(ACTUAL_PALETTE)
    return pal

PALETTE_IMG = waveshare_palette()

def color_for_index(i: int) -> tuple[int, int, int]:
    """
    Deterministically maps index 1..600 to one of FONT_COLORS.
    Evenly distributed, no short cycles.
    """
    n = len(FONT_COLORS)
    permuted = (i * 3 + 1) % n   # 3 is coprime with 4 and non-trivial
    print("Color = ", permuted)
    return FONT_COLORS[permuted]

def get_day_index() -> int:
    # Reference date: January 2, 2026 (index 1)
    reference_date = datetime(2026, 1, 2).date()

    current_date = datetime.now().date()
    days_elapsed = (current_date - reference_date).days
    index = (days_elapsed % NBR_IMAGES) + 1

    return index

MASK_COLOR = (255, 0, 255)  # Magenta — NOT in Spectra 6

def draw_date(canvas, number):
# =====================================================
# DATE — draw vertical text on RIGHT edge
# =====================================================
    date_str = datetime.now().strftime("%d %B %Y")
    date_text_img = Image.new("RGB", (DISPLAY_H, RIGHT_MARGIN), color=(255, 255, 255))   # exact palette white
    td = ImageDraw.Draw(date_text_img)

    bbox = td.textbbox((0, 0), date_str, font=font_bold)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    td.text((((DISPLAY_H - tw) // 2 ), ((RIGHT_MARGIN - th) // 2) - 10),
            date_str, fill=color_for_index(number), font=font_bold)

    date_text_img = date_text_img.quantize(palette=PALETTE_IMG,dither=Image.NONE)
    date_text_img = date_text_img.rotate(-90, expand=True, resample=Image.NEAREST, fillcolor=MASK_IDX)

    arr = np.array(date_text_img)
    mask = (arr != MASK_IDX).astype(np.uint8) * 255
    mask = Image.fromarray(mask, mode="L")
    canvas.paste(date_text_img, (DISPLAY_W - RIGHT_MARGIN, 0), mask)

def read_artwork_by_index(index) -> Tuple[str, str, int]:
    """
    Read a record by 1-based index from a JSON array file
    and return (title, artistName, completitionYear).
    """
    records = json_cache

    try:
        record = records[index - 1]
    except IndexError:
        raise ValueError(f"No record at position {index}")

    return (
        record["title"],
        record["artistName"],
        record["completitionYear"],
    )

def draw_footer(canvas, number):
# =====================================================
# FOOTER — draw vertical text on LEFT edge
# =====================================================
    c, f = get_temperature()
    if c is None:
        c = 25.0 # no compensation
    v = get_input_voltage()
    if v is None:
        battery_pct = "??%"
    else:
        soc = soc_from_voltage_compensated(v, c)
        battery_pct = f"{soc}%"

    title, artist, year = read_artwork_by_index(number)
    artist_text = f"{number}. {artist}: "
    title_text = title
    year_text = f" ({year:04d})"
    battery_text =  "Battery: " + battery_pct

    footer_img = Image.new("RGB", (DISPLAY_H, LEFT_MARGIN), MASK_COLOR)
    fd = ImageDraw.Draw(footer_img)

    bbox = fd.textbbox((0, 0), "Ag", font=font_regular)
    text_h = bbox[3] - bbox[1]
    baseline = LEFT_MARGIN - text_h - 10

    x = 10
    fd.text((x, baseline), artist_text, fill="black", font=font_regular)
    x += fd.textbbox((0, 0), artist_text, font=font_regular)[2]

    fd.text((x, baseline), title_text, fill="black", font=font_italic)
    x += fd.textbbox((0, 0), title_text, font=font_italic)[2]

    fd.text((x, baseline), year_text, fill="black", font=font_regular)

    # battery right-aligned
    bboxs = fd.textbbox((0, 0), "Ag", font=font_regular_small)
    text_hs = bboxs[3] - bboxs[1]
    bs = LEFT_MARGIN - text_hs - 10

    bw = fd.textbbox((0, 0), battery_text, font=font_regular_small)[2]
    fd.text((DISPLAY_H - bw - 10, bs), battery_text, fill="black", font=font_regular_small)

    footer_img = footer_img.rotate(-90, expand=True, resample=Image.NEAREST)

    arr = np.array(footer_img)
    mask = np.any(arr != MASK_COLOR, axis=2).astype(np.uint8) * 255
    mask = Image.fromarray(mask, mode="L")
    canvas.paste(footer_img, (0, 0), mask)

def cache_data(number):
    global json_cache
    global image_cache

    with open(os.path.join(picdir, "index.json"), "r", encoding="utf-8") as f:
        json_cache = json.load(f)

    formatted_number = f"{number:04d}"
    filename = f"{formatted_number}_1600x1200.bmp"
    image_cache = Image.open(os.path.join(picdir, filename))
    image_cache.load()

    epd.lockit()

def display(number):
    print("Display JPG #", number)

    try:
        epd.Init()
        epd.Clear()
        img = image_cache
        draw_date(img, number)
        draw_footer(img, number)
        epd.display(epd.getbuffer(img))
        epd.sleep()

    except Exception:
        epd.sleep()
        traceback.print_exc()

if __name__ == "__main__":
    num = 0

    if len(sys.argv) != 2:
        num = get_day_index()
    else:
        num = int(sys.argv[1])

    if epd.check_if_maintenance():
        print("MAINTENANCE MODE DETECTED")
    else:
        try:
            cache_data(num)
            display(num)
        finally:
            epd.shutdown()

