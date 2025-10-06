#!/usr/bin/python3

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import sys
import multiprocessing
from typing import Tuple, List
from PIL import Image


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Stack pairs of images vertically"
    )
    parser.add_argument(
        "output_dir",
        help="Directory where output images will be saved"
    )
    parser.add_argument(
        "top_images_file",
        help="File containing list of paths to top images, one per line"
    )
    parser.add_argument(
        "bottom_images_file",
        help="File containing list of paths to bottom images, one per line"
    )
    parser.add_argument(
        "--processes",
        type=int,
        default=multiprocessing.cpu_count(),
        help="Number of parallel processes to use"
    )
    
    return parser.parse_args()


def read_image_list(filepath: str) -> List[str]:
    """Read a list of image paths from a file."""
    try:
        with open(filepath, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"Error reading file {filepath}: {e}")
        sys.exit(1)


def handle_file(op: Tuple[int, str, str, str]) -> None:
    """
    Process a pair of images by stacking them vertically.
    
    Args:
        op: Tuple containing (index, top_image_path, bottom_image_path, output_dir)
    """
    idx, top, bottom, output_dir = op
    output_name = f"{output_dir}/output{idx:04d}.png"
    
    try:
        # Open images
        with Image.open(top) as top_img, Image.open(bottom) as bottom_img:
            # Calculate new size
            new_size = (top_img.size[0], top_img.size[1] + bottom_img.size[1])
            
            # Create new image and paste the two images
            output_img = Image.new("RGBA", new_size)
            output_img.paste(top_img)
            output_img.paste(bottom_img, (0, top_img.size[1]))
            
            # Save the result
            output_img.save(output_name)
            logging.info(f"Wrote {output_name}")
    except Exception as e:
        logging.error(f"Error processing {top} and {bottom}: {e}")
        try:
            # Clean up partial output file if it exists
            if os.path.exists(output_name):
                os.unlink(output_name)
        except Exception as cleanup_error:
            logging.error(f"Error cleaning up {output_name}: {cleanup_error}")


def main() -> None:
    """Main entry point for stacking images."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    
    # Parse arguments
    args = parse_args()
    
    # Create output directory if it doesn't exist
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read image lists
    top_images = read_image_list(args.top_images_file)
    bottom_images = read_image_list(args.bottom_images_file)
    
    # Check if the lists have the same length
    if len(top_images) != len(bottom_images):
        logging.warning(
            f"Number of top images ({len(top_images)}) doesn't match "
            f"number of bottom images ({len(bottom_images)}). "
            f"Will process only the first {min(len(top_images), len(bottom_images))} pairs."
        )
    
    # Prepare task list
    tasks = [
        (idx, top, bottom, str(output_dir))
        for idx, (top, bottom) in enumerate(zip(top_images, bottom_images))
    ]
    
    # Process images in parallel
    with multiprocessing.Pool(processes=args.processes) as pool:
        pool.map(handle_file, tasks)
        
    logging.info(f"Completed stacking {len(tasks)} image pairs")


if __name__ == "__main__":
    main()
