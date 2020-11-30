#!/usr/bin/python3

import astral  # type: ignore
import astral.geocoder  # type: ignore
import astral.sun  # type: ignore

import argparse
import datetime
import os
import pathlib
import pytz
import re
import sys


# Simple arg namespace so we get typing of our arguments.  Awkward but
# adds type safety.
class ArgNamespace:
    basedir: str
    skip_weekends: bool
    sample: int


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grab timelapse frames from an RTSP source"
    )
    parser.add_argument("basedir")
    parser.add_argument(
        "--skip-weekends",
        type=bool,
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument("--sample", type=int, default=1)
    args = parser.parse_args(namespace=ArgNamespace)

    # Look for files with name components YYYY-MM-DD_HHMMSS
    filename_regex = re.compile(r"\D(\d\d\d\d)-(\d\d)-(\d\d)_(\d\d)(\d\d)(\d\d)\D")

    # Use Astral to lookup dawn and dusk for the dates of files we
    # find, relative to a specific city.
    astral_db = astral.geocoder.database()
    camera_city = astral.geocoder.lookup("Seattle", astral_db)
    timezone = pytz.timezone(camera_city.timezone)

    seen_count = 0  # for sampling
    # Walk!
    for root, dirs, files in os.walk(args.basedir):
        for filename in files:
            # Skip names that don't match our patterh
            match = filename_regex.search(filename)
            if match is None:
                continue

            # Localize the time in the filename string
            yy, mm, dd, h, m, s = (int(x) for x in match.groups())
            image_datetime = datetime.datetime(yy, mm, dd, h, m, s)
            image_datetime = timezone.localize(image_datetime)

            # Skip weekends if requested.
            if args.skip_weekends and image_datetime.weekday() >= 5:
                continue

            # Only print filenames when the sun is up and that meet our sampling requirement.
            sun_info = astral.sun.sun(camera_city.observer, date=image_datetime)
            if sun_info["dawn"] <= image_datetime <= sun_info["dusk"]:
                if seen_count % args.sample == 0:
                    print(os.path.join(root, filename))
                seen_count += 1


if __name__ == "__main__":
    main()
