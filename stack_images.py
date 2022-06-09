#!/usr/bin/python3

from PIL import Image
import os
import sys
import multiprocessing
from typing import Tuple


def main() -> None:
    file1 = [l.strip() for l in open(sys.argv[2])]
    file2 = [l.strip() for l in open(sys.argv[3])]

    with multiprocessing.Pool(processes=32) as pool:
        pool.map(
            handle_file,
            [(idx, top, bottom) for idx, (top, bottom) in enumerate(zip(file1, file2))],
        )


def handle_file(op: Tuple[int, str, str]) -> None:
    idx, top, bottom = op
    top_img = Image.open(top)
    bottom_img = Image.open(bottom)
    new_size = (top_img.size[0], top_img.size[1] + bottom_img.size[1])

    output_dir = sys.argv[1]
    output_name = f"{output_dir}/output{idx:04d}.png"
    print(f"Writing {output_name} from {top} and {bottom}...")

    try:
        output_img = Image.new("RGBA", new_size)
        output_img.paste(top_img)
        output_img.paste(bottom_img, (0, top_img.size[1]))
        output_img.save(output_name)
    except Exception as e:
        print(f"Skipping {output_name} -> {e}")
        try:
            os.unlink(output_name)
        except:
            pass


if __name__ == "__main__":
    main()
