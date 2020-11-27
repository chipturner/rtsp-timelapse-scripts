# Overview

These scripts are basically (slightly) cleaned up versions of personal
scripts I used to turn an RTSP stream into a timelapse video.  I
capture video to a NAS via UniFi cameras with
`grab-timelapse-frame.py` via cron and periodically use `ffmpeg` with
the files provided by `filter-timelapse-frames.py` to produce an
actual video.

## Interesting, Motivating Details

My project was backyard construction.  This means I am only interested
in weekday work when there is daylight, hence defaults that are tuned
to that (e.g. using `astral` to determine when sunrise and sunset are
to avoid capturing frames, and skipping weekends).

I want to capture roughly one image every 10 seconds so I can have a
smooth video per day but also can then sample over longer periods.
Hence:

- `grab-timelapse-frame.py` passes filename and directory names to `strftime` so as to avoid too many files in a single directory.
- `grab-timelapse-frame.py` is made robust by intentionally being short lived and run from cron; no complexities from `systemd` though you do lose some monitoring/management.  Oh well, it works for me and seems worth it.
- `filter-timelapse-frames.py` supports a `--sample` parameter to only print every Nth matching file for when you want to produce faster videos by not including every frame.  (TODO: eventually process images directly with ML to filter in/out people, animals, bitcoins, etc).
- Sunrise and sunset are relative to wherever you are, so `grab-timelapse-frame.py` accepts a `--city` parameter (full list of cities is provided by `astral`'s [`geocoder.py`](https://github.com/sffjunkie/astral/blob/master/src/astral/geocoder.py) module.

## Basic Usage

First, install `ffmpeg` with whatever libraries are most approriate
for output formats you want.  I like x264 for speed and compression
ratio.

### Capturing

First, you need to capture frames.  `grab-timelapse-frame.py` is
designed to be run in a cron.  It is a short-running script that,
ideally, you invoke every minute and let it run for one minute.
During that time it will produce N evenly spaced out frames into the
specified output directory.  Example cronjob:

```
* * * * *	/path/to/grab-timelapse-frame.py --output-directory /path/to/outputs --output-filenames cam1 --url rtsp://HOST:PORT/PATH
```

**NOTE**: If you use `strftime` in the output strings, don't forget to
backslash `%` in your crontab -- cron translates them to newlines..

### Creating a video

Congratulations, you have a pile of png files.  To make a video, you
need to use `ffmpeg` with a list of files.  Since you likely have too
many files, you want to filter:

```
$ ./filter-timelapse-frames.py /path/to/pile --sample 10 > /tmp/filelist
$ ffmpeg -r 30 -f concat -safe 0 -i <(sed 's/^/file /' /tmp/filelist) -c:v libx264rgb -preset veryslow -crf 21 -vf fps=30 /path/to/output.mp4
```

You can google for what the `ffmpeg` line does and learn how to
produce other output file formats, but the above works well for me.
Note it will be slow.  The `<(sed ...)`  bit is to prefix each line
with 'file ' to produce an instruction file that `ffmpeg` likes.

And you're done!  Enjoy your fun video.  VLC is probably the best tool
to view it in.
