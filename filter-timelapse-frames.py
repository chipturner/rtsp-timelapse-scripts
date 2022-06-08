#!/usr/bin/python3

import astral  # type: ignore
import astral.geocoder  # type: ignore
import astral.sun  # type: ignore

import fileinput
import argparse
import datetime
import os
import pathlib
import pytz
import random
import re
import sys
from typing import List


# Simple arg namespace so we get typing of our arguments.  Awkward but
# adds type safety.
class ArgNamespace:
    skip_weekends: bool
    sample_rate: int
    supersample_ranges: str  # R:YYYYMMDD-YYYYMMDD, ...


class TimeBucket:
    start_time: int
    sample_scale: int
    files: List[str]

    def __init__(self, s, r):
        self.start_time = s
        self.sample_scale = r
        self.files = []

    def __repr__(self):
        return f"TimeBucket({self.start_time}, {self.sample_scale}, {len(self.files)})"

    def select(self, sample_rate):
        stride = int(sample_rate / self.sample_scale)
        return sorted(self.files[::stride])


# read all files
# snapshot file list?  maybe take from stdin?  yeah use fdfind not walk
# start with (-inf, inf) and walk timeline, splitting at each bucket start/stop
# select() picks n entries from range (TODO: select ones near-ish noon)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grab timelapse frames from an RTSP source"
    )
    parser.add_argument(
        "--skip-weekends",
        type=bool,
        default=True,
    )
    parser.add_argument("--sample", type=int, default=1)
    parser.add_argument("--supersample_ranges", type=str)
    args = parser.parse_args(namespace=ArgNamespace)

    split_points = []
    if args.supersample_ranges:
        ss_re = re.compile(r"^(\d{8})-(\d{8}):(\d+)$")
        for bucket in args.supersample_ranges.split(","):
            m = ss_re.match(bucket)
            if not m:
                continue
            start, stop, rate = map(int, m.groups())
            split_points.append((int(start), int(stop), int(rate)))

    # Look for files with name components YYYY-MM-DD_HHMMSS
    filename_regex = re.compile(
        r"\D(\d\d\d\d)-(\d\d)-(\d\d)_(\d\d)(\d\d)(\d\d)\D.*png$"
    )

    # Use Astral to lookup dawn and dusk for the dates of files we
    # find, relative to a specific city.
    astral_db = astral.geocoder.database()
    camera_city = astral.geocoder.lookup("Seattle", astral_db)
    timezone = pytz.timezone(camera_city.timezone)

    seen_count = 0  # for sampling
    sorted_files = []
    for filename in fileinput.input(files=[]):
        filename = filename.strip()

        sorted_files.append(filename)
    sorted_files.sort()

    buckets = {}
    for filename in sorted_files:
        # Skip names that don't match our patterh
        match = filename_regex.search(filename)
        if match is None:
            continue

        # Localize the time in the filename string
        yy, mm, dd, h, m, s = (int(x) for x in match.groups())
        bucket_key = dd + 100 * mm + 100 * 100 * yy
        if bucket_key not in buckets:
            bucket = TimeBucket(bucket_key, 1)
            buckets[bucket_key] = bucket
        else:
            bucket = buckets[bucket_key]

        for (start, stop, scale) in split_points:
            if start <= bucket_key <= stop:
                bucket.sample_scale = max(scale, bucket.sample_scale)

        image_datetime = datetime.datetime(yy, mm, dd, h, m, s, tzinfo=timezone)

        # Skip weekends if requested.
        if args.skip_weekends and image_datetime.weekday() >= 5:
            continue

        # Only print filenames when the sun is up and that meet our sampling requirement.
        sun_info = astral.sun.sun(
            camera_city.observer, date=image_datetime, tzinfo=timezone
        )
        if sun_info["dawn"] <= image_datetime <= sun_info["dusk"]:
            numeric_time = dd + 100 * mm + 100 * 100 * yy
            buckets[numeric_time].files.append(filename)

    for bucket in buckets.values():
        if len(bucket.files) > 0:
            print("\n".join(bucket.select(args.sample)))


if __name__ == "__main__":
    main()
