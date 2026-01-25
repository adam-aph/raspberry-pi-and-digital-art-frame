#!/usr/bin/python
# -*- coding:utf-8 -*-
# /*****************************************************************************
# * | File        :	  convert.py
# * | Function    :   Convert and adjust images to better fit for E-Ink display
# * | Info        :
# * | This version:   V1.0
# * | Author      :   adam_aph
# * | Date        :   2026-01-21
# * | Info        :   Initial release
# *----------------
# ******************************************************************************/

import os
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import numpy as np

DISPLAY_W = 1600
DISPLAY_H = 1200

RIGHT_MARGIN = 80   # physical top after rotation
LEFT_MARGIN = 50     # physical bottom after rotation

IMAGE_AREA_W = DISPLAY_W - LEFT_MARGIN - RIGHT_MARGIN
IMAGE_AREA_H = DISPLAY_H


INPUT_DIR = "images"
OUTPUT_DIR = "images-enhanced-bmp11"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define the exact Spectra 6 Palette (Black, White, Yellow, Red, Blue, Green, Orange)
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

def process_image(path, output_path):
    with Image.open(path) as img:
        img = img.convert("RGB")

        # 1. Rotate
        img = img.rotate(-90, expand=True)

        # 2. Resizing logic
        src_w, src_h = img.size
        scale = min(IMAGE_AREA_W / src_w, IMAGE_AREA_H / src_h)
        new_w, new_h = int(round(src_w * scale)), int(round(src_h * scale))
        img = img.resize((new_w, new_h), resample=Image.LANCZOS)

        # --- SPECTRA 6–AWARE ENHANCEMENTS ---

        # A. Custom S-curve tone mapping using LUT (FAST)
        lut = np.arange(256, dtype=np.float32) / 255.0
        lut = 0.5 * (1 + np.tanh(1.2 * (lut - 0.5)))

        # --- WHITE DEAD-ZONE COMPRESSION ---
        white_start = 0.92  # where flattening begins
        white_end = 0.97  # fully flat white

        mask = lut >= white_start
        lut[mask] = white_start + (lut[mask] - white_start) * ((white_end - white_start) / (1.0 - white_start))

        # Final hard clamp
        lut[lut >= white_end] = 1.0

        lut = np.clip(lut * 255, 0, 255).astype(np.uint8)
        lut_rgb = np.concatenate([lut, lut, lut]).tolist()
        img = img.point(lut_rgb)

        # B. Controlled saturation + pigment bias
        img = ImageEnhance.Color(img).enhance(1.25)

        np_img = np.array(img).astype(float)
        np_img[..., 0] *= 1.05  # Red → Orange/Yellow support
        np_img[..., 1] *= 1.05  # Green → Yellow separation
        np_img[..., 2] *= 0.95  # Suppress blue noise
        img = Image.fromarray(np.clip(np_img, 0, 255).astype(np.uint8), "RGB")

        # C. Local contrast (kept conservative)
        img = ImageOps.autocontrast(img, cutoff=0.5)
        img = ImageEnhance.Contrast(img).enhance(1.10)

        # D. Edge sharpening tuned to avoid dither amplification
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=130, threshold=6))

        # 6. Create Canvas
        canvas = Image.new("RGB", (DISPLAY_W, DISPLAY_H), (255, 255, 255))
        canvas.paste(img,(LEFT_MARGIN + (IMAGE_AREA_W - img.width) // 2,(DISPLAY_H - img.height) // 2))

        # 7. Pre-quantization stabilization
        canvas = ImageOps.posterize(canvas, bits=5)

        # --- WHITE SNAP (CRITICAL) ---
        np_canvas = np.array(canvas)

        # Any pixel that is perceptually white → force pure white
        white_thresh = 245  # aggressively high, but safe on E-Ink

        mask = ((np_canvas[..., 0] >= white_thresh) & (np_canvas[..., 1] >= white_thresh) & (np_canvas[..., 2] >= white_thresh))
        np_canvas[mask] = [255, 255, 255]

        canvas = Image.fromarray(np_canvas, "RGB")

        pal_image = Image.new("P", (1, 1))
        pal_image.putpalette(ACTUAL_PALETTE)

        # Final quantization (Spectra-6 compatible)
        canvas = canvas.quantize(palette=pal_image,dither=Image.FLOYDSTEINBERG)

        # 8. Save as uncompressed BMP
        canvas.save(output_path, format="BMP")

def main():
    for filename in os.listdir(INPUT_DIR):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        input_path = os.path.join(INPUT_DIR, filename)
        name, _ = os.path.splitext(filename)
        output_filename = f"{name}_1600x1200.bmp"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        process_image(input_path, output_path)
        print(f"Processed: {filename} -> {output_filename}")

if __name__ == "__main__":
    main()
