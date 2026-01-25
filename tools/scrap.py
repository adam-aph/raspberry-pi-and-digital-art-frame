#!/usr/bin/python
# -*- coding:utf-8 -*-
# /*****************************************************************************
# * | File        :	  scrap.py
# * | Function    :   Upload images based on configuration JSON file
# * | Info        :
# * | This version:   V1.0
# * | Author      :   adam_aph
# * | Date        :   2026-01-21
# * | Info        :   Initial release
# *----------------
# ******************************************************************************/

import json
import os
import time
import requests
from datetime import datetime, timedelta

MAX_RPS = 4
MAX_RPH = 400
SECONDS_PER_HOUR = 3600

WORKLIST_FILE = "worklist.txt"
PROGRESS_FILE = "progress.txt"
OUTPUT_DIR = "images"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_worklist(data):
    with open(WORKLIST_FILE, "w", encoding="utf-8") as f:
        for idx, obj in enumerate(data, start=1):
            url = obj["image"].split("!")[0]
            f.write(f"{idx},{url}\n")

def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return set(int(line.strip()) for line in f if line.strip().isdigit())


def save_progress(index):
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{index}\n")


def rate_limited_sleep(request_times):
    now = time.time()

    # RPS control
    request_times[:] = [t for t in request_times if now - t < 1]
    if len(request_times) >= MAX_RPS:
        time.sleep(1 - (now - request_times[0]))

    # RPH control
    request_times[:] = [t for t in request_times if now - t < SECONDS_PER_HOUR]
    if len(request_times) >= MAX_RPH:
        sleep_time = SECONDS_PER_HOUR - (now - request_times[0])
        time.sleep(max(0, sleep_time))


def main(json_file):
    data = load_json(json_file)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(WORKLIST_FILE):
        create_worklist(data)

    with open(WORKLIST_FILE, "r", encoding="utf-8") as wf:
        total = sum(1 for _ in wf)

    completed = load_progress()
    request_times = []
    session = requests.Session()

    start_time = time.time()

    with open(WORKLIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            idx_str, url = line.strip().split(",", 1)
            idx = int(idx_str)

            if idx in completed:
                continue

            rate_limited_sleep(request_times)

            try:
                response = session.get(url, timeout=30)
                request_times.append(time.time())

                if response.status_code == 200:
                    ext = os.path.splitext(url)[1].split("!")[0]
                    filename = f"{idx:04d}{ext or '.jpg'}"
                    path = os.path.join(OUTPUT_DIR, filename)

                    with open(path, "wb") as img:
                        img.write(response.content)

                    save_progress(idx)
                    completed.add(idx)

                else:
                    time.sleep(5)
                    continue

            except Exception:
                time.sleep(10)
                continue

            # Progress display
            elapsed = time.time() - start_time
            percent = (len(completed) / total) * 100
            avg_time = elapsed / max(1, len(completed))
            eta = timedelta(seconds=int(avg_time * (total - len(completed))))

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"{len(completed)}/{total} "
                f"({percent:.2f}%) "
                f"Elapsed: {timedelta(seconds=int(elapsed))} "
                f"ETA: {eta}"
            )


if __name__ == "__main__":
    # import sys
    # if len(sys.argv) != 2:
    #     print("Usage: python download_images.py <json_file>")
    #     sys.exit(1)

    main("MostViewedPaintings.json")
