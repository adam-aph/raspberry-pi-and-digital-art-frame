#!/usr/bin/python
# -*- coding:utf-8 -*-
# /*****************************************************************************
# * | File        :	  clear.py
# * | Function    :   Clear EPD display
# * | Info        :
# * | This version:   V1.0
# * | Author      :   adam_aph
# * | Date        :   2026-01-21
# * | Info        :   Initial release
# *----------------
# ******************************************************************************/

import sys
import os
import traceback


current_dir = os.path.dirname(os.path.realpath(__file__))
libdir = os.path.join(current_dir, 'lib')
sys.path.append(libdir)

import epd13in3E

epd = epd13in3E.EPD()
epd.lockit()

def clear():
    try:
        epd.Init()
        epd.Clear()
        epd.sleep()
    except Exception:
        epd.sleep()
        traceback.print_exc()

if __name__ == "__main__":
    if epd.check_if_maintenance():
        print("MAINTENANCE MODE DETECTED")
    else:
        try:
            clear()
        finally:
            epd.shutdown()

