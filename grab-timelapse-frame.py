#!/usr/bin/python3

from __future__ import annotations

import astral  # type: ignore
import astral.geocoder  # type: ignore
import astral.sun  # type: ignore

import argparse
import datetime
import logging
import pathlib
import pytz
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import List


def sun_is_out(city: str, buffer_minutes: int) -> bool:
    """
    Check if the sun is currently "out" in the specified city based on
    today's dawn and dusk in that city.
    """
    astral_db = astral.geocoder.database()
    camera_city = astral.geocoder.lookup(city, astral_db)
    timezone = pytz.timezone(camera_city.timezone)
    sun_info = astral.sun.sun(camera_city.observer, tzinfo=timezone)
    delta = datetime.timedelta(minutes=buffer_minutes)

    now = datetime.datetime.now(tz=timezone)
    lower = sun_info["dawn"] - delta
    upper = sun_info["dusk"] + delta
    return lower <= now <= upper


@dataclass
class Args:
    """Command line arguments for the program."""
    output_directory: str
    output_filenames: str
    url: str
    interval: int = 10
    duration: int = 60
    daylight_only: bool = True
    daylight_buffer_minutes: int = 15
    city: str = "Seattle"


def parse_args() -> Args:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Grab timelapse frames from an RTSP source"
    )
    parser.add_argument("--output-directory", type=str, required=True)
    parser.add_argument(
        "--output-filenames",
        type=str,
        required=True,
        default="cam-%Y-%m-%d_%H%M%S.png",
    )
    parser.add_argument("--url", type=str, required=True)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument(
        "--daylight-only",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--daylight-buffer-minutes", type=int, default=15)
    parser.add_argument("--city", type=str, default="Seattle")
    
    # Parse args into a namespace and convert to dataclass
    namespace = parser.parse_args()
    return Args(
        output_directory=namespace.output_directory,
        output_filenames=namespace.output_filenames,
        url=namespace.url,
        interval=namespace.interval,
        duration=namespace.duration,
        daylight_only=namespace.daylight_only,
        daylight_buffer_minutes=namespace.daylight_buffer_minutes,
        city=namespace.city,
    )


def capture_frame(url: str, output_path: pathlib.Path) -> bool:
    """Capture a single frame from RTSP stream to the specified output path."""
    try:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "fatal", 
            "-rtsp_transport", "tcp", 
            "-i", url, 
            "-frames:v", "1", 
            str(output_path)
        ]
        result = subprocess.run(cmd, check=False, capture_output=True)
        return result.returncode == 0
    except Exception as e:
        logging.error(f"Error capturing frame: {e}")
        return False


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    
    args = parse_args()

    if args.daylight_only:
        if not sun_is_out(args.city, args.daylight_buffer_minutes):
            logging.info("Skipping snapshot outside of daylight hours")
            sys.exit(0)

    output_filenames = args.output_filenames
    if "%Y" not in output_filenames:
        output_filenames += "-%Y-%m-%d_%H%M%S.png"

    basedir = pathlib.Path(time.strftime(args.output_directory))
    if "%Y" not in args.output_directory:
        basedir /= pathlib.Path(time.strftime("%Y/%m/%d/%H"))

    basedir.mkdir(mode=0o755, parents=True, exist_ok=True)
    end_time = time.time() + args.duration

    failed = 0
    succeeded = 0
    while time.time() < end_time:
        output = basedir / time.strftime(output_filenames)
        begin = time.time()
        logging.info(f"Capturing image {succeeded + failed + 1}...")
        
        if capture_frame(args.url, output):
            succeeded += 1
        else:
            failed += 1
            logging.error(f"Failed to capture frame to {output}")
            
        end = time.time()
        sleep_time = max(1, args.interval - int(end - begin))
        time.sleep(sleep_time)

    logging.info(f"Succeeded: {succeeded}, failed: {failed}")
    if failed >= args.duration / args.interval / 2:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
