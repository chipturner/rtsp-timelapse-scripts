#!/usr/bin/python3

import astral  # type: ignore
import astral.geocoder  # type: ignore
import astral.sun  # type: ignore

import argparse
import datetime
import pathlib
import pytz
import subprocess
import sys
import time
from typing import Tuple


# Check if the sun is currently "out" in the specified city based on
# today's sunrise and sunset in that city.
def sun_is_out(city: str, buffer_minutes: int) -> bool:
    astral_db = astral.geocoder.database()
    sunrise_city = astral.geocoder.lookup(city, astral_db)
    timezone = pytz.timezone(sunrise_city.timezone)
    sun_info = astral.sun.sun(sunrise_city.observer)
    delta = datetime.timedelta(minutes=buffer_minutes)

    now = datetime.datetime.now(tz=timezone)
    lower = sun_info["sunrise"] - delta
    upper = sun_info["sunset"] + delta
    return lower <= now <= upper


# Simple arg namespace so we get typing of our arguments.  Awkward but
# adds type safety.
class ArgNamespace:
    directory_strftime_pattern: str
    filename_strftime_pattern: str
    url: str
    interval: int
    duration: int
    daylight_only: bool
    daylight_buffer_minutes: int
    city: str


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grab timelapse frames from an RTSP source"
    )
    parser.add_argument("--directory-strftime-pattern", type=str, required=True)
    parser.add_argument(
        "--filename-strftime-pattern",
        type=str,
        required=True,
        default="cam-%Y-%m-%d_%H%M%S.png",
    )
    parser.add_argument("--url", type=str, required=True)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--daylight-only", type=bool, default=True)
    parser.add_argument("--daylight-buffer-minutes", type=int, default=15)
    parser.add_argument("--city", type=str, default="Seattle")
    args = parser.parse_args(namespace=ArgNamespace)

    if args.daylight_only:
        if not sun_is_out(args.city, args.daylight_buffer_minutes):
            print("Skipping snapshot outside of daylight hours")
            sys.exit(0)

    basedir = pathlib.Path(time.strftime(args.directory_strftime_pattern))
    basedir.mkdir(mode=0o755, parents=True, exist_ok=True)
    end_time = time.time() + args.duration

    failed = 0
    succeeded = 0
    while time.time() < end_time:
        output = basedir / time.strftime(args.filename_strftime_pattern)
        begin = time.time()
        print(f"Capturing image {succeeded + failed + 1}...")
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

    print(f"Succeeded: {succeeded}, failed: {failed}")
    if failed >= args.duration / args.interval / 2:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
