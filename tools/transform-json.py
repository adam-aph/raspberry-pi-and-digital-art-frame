#!/usr/bin/python
# -*- coding:utf-8 -*-
# /*****************************************************************************
# * | File        :	  transform-json.py
# * | Function    :   Create final index.json file
# * | Info        :
# * | This version:   V1.0
# * | Author      :   adam_aph
# * | Date        :   2026-01-21
# * | Info        :   Initial release
# *----------------
# ******************************************************************************/

import json
import sys


def transform(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    output = []
    for idx, record in enumerate(data, start=1):
        output.append({
            "index": idx,
            "title": record.get("title"),
            "artistName": record.get("artistName"),
            "completitionYear": record.get("completitionYear"),
            "width": record.get("width"),
            "height": record.get("height"),
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # if len(sys.argv) != 3:
    #     print("Usage: python transform.py <input.json> <output.json>")
    #     sys.exit(1)

    transform("MostViewedPaintings.json", "index.json")
