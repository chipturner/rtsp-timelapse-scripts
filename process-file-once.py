#!/usr/bin/python3

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import sqlite3
import subprocess
import sys
import time
from typing import List, Optional


def setup_database(db_path: pathlib.Path) -> sqlite3.Connection:
    """Set up and return a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("pragma journal_mode = WAL")
        conn.execute("pragma synchronous = normal")
        conn.execute("pragma mmap_size = 30000000000")
        conn.execute("pragma page_size = 32768")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                path BLOB NOT NULL,
                cmd BLOB NOT NULL,
                device INT NOT NULL,
                inode INT NOT NULL,
                last_processed INT NOT NULL,
                PRIMARY KEY(path, cmd)
            )
            """,
        )
        conn.commit()
        return conn
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        sys.exit(1)


def has_been_processed(conn: sqlite3.Connection, filename: str, args_string: bytes) -> bool:
    """Check if the file has already been processed with the given command."""
    try:
        cursor = conn.execute(
            "SELECT cmd, device, inode, last_processed FROM files WHERE path = ? AND cmd = ?",
            (filename, args_string),
        )
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logging.error(f"Query error: {e}")
        return False


def record_processed(conn: sqlite3.Connection, filename: str, args_string: bytes) -> None:
    """Record that the file has been processed with the given command."""
    try:
        st = os.stat(filename)
        conn.execute(
            "INSERT INTO files (path, cmd, device, inode, last_processed) VALUES (?, ?, ?, ?, ?)",
            (filename, args_string, st.st_dev, st.st_ino, time.time()),
        )
        conn.commit()
    except (OSError, sqlite3.Error) as e:
        logging.error(f"Error recording processed file: {e}")


def execute_command(args: List[str]) -> int:
    """Execute the command and return the result code."""
    try:
        result = subprocess.run(args, check=False, capture_output=True)
        return result.returncode
    except Exception as e:
        logging.error(f"Error executing command {args}: {e}")
        return -1


def parse_args() -> tuple[str, List[str], pathlib.Path]:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process a file only once with a given command"
    )
    parser.add_argument(
        "--db-path", 
        type=str, 
        default="~/.process-file-once.db",
        help="Path to the database file"
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
        
    return args.filename, args.command, pathlib.Path(args.db_path).expanduser()


def main() -> None:
    """Main entry point."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    
    try:
        # Parse command line arguments
        if len(sys.argv) < 3:
            logging.error("Usage: process-file-once.py <filename> <command...>")
            sys.exit(1)
            
        if "--db-path" in sys.argv:
            filename, cmd_args, db_path = parse_args()
        else:
            filename, cmd_args = sys.argv[1], sys.argv[2:]
            db_path = pathlib.Path("~/.process-file-once.db").expanduser()
            
        # Connect to the database
        conn = setup_database(db_path)
        
        # Prepare command arguments
        args_string = b"\0".join(arg.encode("utf-8") for arg in cmd_args)
        filename = os.path.realpath(filename)
        cmd_args = [arg.replace("{}", filename) for arg in cmd_args]
        
        # Check if already processed
        if has_been_processed(conn, filename, args_string):
            logging.debug(f"Skipping already processed file: {filename}")
            return
            
        # Execute the command
        res = execute_command(cmd_args)
        
        # Record the result
        if res == 0:
            record_processed(conn, filename, args_string)
        else:
            logging.error(f"Command failed with return code {res}: {cmd_args}")
            
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    main()
