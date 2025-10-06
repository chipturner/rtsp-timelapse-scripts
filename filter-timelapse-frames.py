#!/usr/bin/python3

from __future__ import annotations

import astral  # type: ignore
import astral.geocoder  # type: ignore
import astral.sun  # type: ignore

import fileinput
import argparse
import datetime
import os
import pathlib
import pytz
import re
import sys
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Iterator, Optional


@dataclass
class Args:
    """Command line arguments for the program."""
    skip_weekends: bool = True
    sample: int = 1
    supersample_ranges: Optional[str] = None  # Format: YYYYMMDD-YYYYMMDD:rate,...
    city: str = "Seattle"


@dataclass
class TimeBucket:
    """A bucket representing a single day of images."""
    start_time: int
    sample_scale: int = 1
    files: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"TimeBucket({self.start_time}, {self.sample_scale}, {len(self.files)})"

    def select(self, sample_rate: int) -> List[str]:
        """
        Select files from the bucket using the given sample rate.
        Returns files with appropriate stride based on sample rate and scale.
        """
        stride = max(1, int(sample_rate / self.sample_scale))
        return sorted(self.files[::stride])


def parse_supersample_ranges(ranges_str: str) -> List[Tuple[int, int, int]]:
    """
    Parse supersample range string into a list of (start, stop, rate) tuples.
    Format: YYYYMMDD-YYYYMMDD:rate,...
    """
    if not ranges_str:
        return []
        
    split_points = []
    ss_re = re.compile(r"^(\d{8})-(\d{8}):(\d+)$")
    
    for bucket in ranges_str.split(","):
        m = ss_re.match(bucket)
        if not m:
            logging.warning(f"Invalid supersample range format: {bucket}")
            continue
        
        start, stop, rate = map(int, m.groups())
        split_points.append((start, stop, rate))
    
    return split_points


def process_files(
    filenames: Iterator[str], 
    args: Args, 
    split_points: List[Tuple[int, int, int]],
    city: str
) -> Dict[int, TimeBucket]:
    """
    Process files and organize them into time buckets.
    Returns a dictionary of buckets keyed by date.
    """
    # Look for files with name components YYYY-MM-DD_HHMMSS
    filename_regex = re.compile(
        r"\D(\d\d\d\d)-(\d\d)-(\d\d)_(\d\d)(\d\d)(\d\d)\D.*png$"
    )

    # Use Astral to lookup dawn and dusk for the dates of files we
    # find, relative to a specific city.
    astral_db = astral.geocoder.database()
    camera_city = astral.geocoder.lookup(city, astral_db)
    timezone = pytz.timezone(camera_city.timezone)

    buckets: Dict[int, TimeBucket] = {}
    
    for filename in filenames:
        filename = filename.strip()
        
        # Skip names that don't match our pattern
        match = filename_regex.search(filename)
        if match is None:
            continue

        # Localize the time in the filename string
        yy, mm, dd, h, m, s = (int(x) for x in match.groups())
        bucket_key = dd + 100 * mm + 100 * 100 * yy
        
        # Create bucket if it doesn't exist
        if bucket_key not in buckets:
            buckets[bucket_key] = TimeBucket(start_time=bucket_key)
            
        bucket = buckets[bucket_key]

        # Apply supersample ranges
        for (start, stop, scale) in split_points:
            if start <= bucket_key <= stop:
                bucket.sample_scale = max(scale, bucket.sample_scale)

        # Create datetime object for the image
        image_datetime = datetime.datetime(yy, mm, dd, h, m, s, tzinfo=timezone)

        # Skip weekends if requested
        if args.skip_weekends and image_datetime.weekday() >= 5:
            continue

        # Only include files when the sun is up
        try:
            sun_info = astral.sun.sun(
                camera_city.observer, date=image_datetime, tzinfo=timezone
            )
            if sun_info["dawn"] <= image_datetime <= sun_info["dusk"]:
                buckets[bucket_key].files.append(filename)
        except Exception as e:
            logging.error(f"Error getting sun info for {image_datetime}: {e}")
            
    return buckets


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    
    parser = argparse.ArgumentParser(
        description="Filter and select timelapse frames based on time and daylight"
    )
    parser.add_argument(
        "--skip-weekends",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip frames captured on weekends",
    )
    parser.add_argument(
        "--sample", 
        type=int, 
        default=1,
        help="Sample rate - only include every Nth frame",
    )
    parser.add_argument(
        "--supersample-ranges", 
        type=str,
        help="Comma-separated list of date ranges with custom sample rates: YYYYMMDD-YYYYMMDD:rate,...",
    )
    parser.add_argument(
        "--city",
        type=str,
        default="Seattle",
        help="City name for daylight calculations",
    )
    
    # Parse args
    namespace = parser.parse_args()
    args = Args(
        skip_weekends=namespace.skip_weekends,
        sample=namespace.sample,
        supersample_ranges=namespace.supersample_ranges,
        city=namespace.city,
    )

    # Parse supersample ranges
    split_points = parse_supersample_ranges(args.supersample_ranges or "")

    # Process files from standard input
    sorted_files = sorted(line.strip() for line in fileinput.input(files=[]))
    buckets = process_files(iter(sorted_files), args, split_points, args.city)

    # Output selected files
    output_files = []
    for bucket in buckets.values():
        if bucket.files:
            output_files.extend(bucket.select(args.sample))
    
    print("\n".join(output_files))


if __name__ == "__main__":
    main()
