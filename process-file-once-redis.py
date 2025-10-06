#!/usr/bin/python3

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import redis
import subprocess
import sys
import time
from typing import List, Optional

KEY_NAME = "process_once"


def connect_redis(socket_path: str) -> redis.Redis:
    """Connect to Redis server and return client."""
    try:
        return redis.Redis(unix_socket_path=socket_path)
    except redis.RedisError as e:
        logging.error(f"Redis connection error: {e}")
        sys.exit(1)


def has_been_processed(redis_client: redis.Redis, key: str) -> bool:
    """Check if the file has already been processed with the given command."""
    try:
        return redis_client.sismember(KEY_NAME, key)
    except redis.RedisError as e:
        logging.error(f"Redis query error: {e}")
        return False


def record_processed(redis_client: redis.Redis, key: str) -> None:
    """Record that the file has been processed with the given command."""
    try:
        redis_client.sadd(KEY_NAME, key)
    except redis.RedisError as e:
        logging.error(f"Error recording processed file: {e}")


def execute_command(args: List[str]) -> int:
    """Execute the command and return the result code."""
    try:
        result = subprocess.run(args, check=False, capture_output=True)
        return result.returncode
    except Exception as e:
        logging.error(f"Error executing command {args}: {e}")
        return -1


def parse_args() -> tuple[str, List[str], str]:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process a file only once with a given command, using Redis for tracking"
    )
    parser.add_argument(
        "--redis-socket", 
        type=str, 
        default="/var/run/redis/redis-server.sock",
        help="Path to the Redis Unix socket"
    )
    parser.add_argument(
        "filename", 
        help="The file to process"
    )
    parser.add_argument(
        "command", 
        nargs=argparse.REMAINDER,
        help="The command to run on the file. Use {} as a placeholder for the filename."
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.error("Command is required")
        
    return args.filename, args.command, args.redis_socket


def main() -> None:
    """Main entry point for processing a file once using Redis for tracking."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    
    try:
        # Parse command line arguments
        if len(sys.argv) < 3:
            logging.error("Usage: process-file-once-redis.py <filename> <command...>")
            sys.exit(1)
            
        if "--redis-socket" in sys.argv:
            filename, cmd_args, redis_socket = parse_args()
        else:
            filename, cmd_args = sys.argv[1], sys.argv[2:]
            redis_socket = "/var/run/redis/redis-server.sock"
            
        # Connect to Redis
        redis_client = connect_redis(redis_socket)
        
        # Prepare command arguments
        args_string = b"\0".join(arg.encode("utf-8") for arg in cmd_args)
        filename = os.path.realpath(filename)
        cmd_args = [arg.replace("{}", filename) for arg in cmd_args]
        
        # Create unique key for this file+command
        key = f"{filename}:{args_string}"
        
        # Check if already processed
        if has_been_processed(redis_client, key):
            logging.debug(f"Skipping already processed file: {filename}")
            return
            
        # Execute the command
        res = execute_command(cmd_args)
        
        # Record the result
        if res == 0:
            record_processed(redis_client, key)
        else:
            logging.error(f"Command failed with return code {res}: {cmd_args}")
            
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
