#!/usr/bin/python3

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
from typing import Tuple


# Check if the sun is currently "out" in the specified city based on
# today's dawn and dusk in that city.
def sun_is_out(city: str, buffer_minutes: int) -> bool:
    astral_db = astral.geocoder.database()
    camera_city = astral.geocoder.lookup(city, astral_db)
    timezone = pytz.timezone(camera_city.timezone)
    sun_info = astral.sun.sun(camera_city.observer, tzinfo=timezone)
    delta = datetime.timedelta(minutes=buffer_minutes)

    now = datetime.datetime.now(tz=timezone)
    lower = sun_info["dawn"] - delta
    upper = sun_info["dusk"] + delta
    return lower <= now <= upper


# Simple arg namespace so we get typing of our arguments.  Awkward but
# adds type safety.
class ArgNamespace:
    output_directory: str
    output_filenames: str
    url: str
    interval: int
    duration: int
    daylight_only: bool
    daylight_buffer_minutes: int
    city: str


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
    )
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
#    parser.add_argument(
#        "--daylight-only",
#        type=bool,
#        default=True,
#        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument("--daylight-buffer-minutes", type=int, default=15)
    parser.add_argument("--city", type=str, default="Seattle")
    args = parser.parse_args(namespace=ArgNamespace)

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
        res = subprocess.call(
            f"ffmpeg -y -loglevel fatal -rtsp_transport tcp -i {args.url} -frames:v 1 {output}",
            shell=True,
        )
        if res == 0:
            succeeded += 1
        else:
            failed += 1
        end = time.time()
        time.sleep(max(1, int(args.interval) - (end - begin)))

    logging.info(f"Succeeded: {succeeded}, failed: {failed}")
    if failed >= args.duration / args.interval / 2:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
