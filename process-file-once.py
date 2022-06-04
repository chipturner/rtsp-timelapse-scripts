#!/usr/bin/python3

import os
import pathlib
import sqlite3
import subprocess
import sys
import time


def main() -> None:
    conn = sqlite3.connect(pathlib.Path("~/.process-file-once.db").expanduser())
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

    filename, args = sys.argv[1], sys.argv[2:]
    args_string = b"\0".join(arg.encode("utf-8") for arg in args)
    filename = os.path.realpath(filename)
    for idx in range(len(args)):
        args[idx] = args[idx].replace("{}", filename)

    r = conn.execute(
        "SELECT cmd, device, inode, last_processed FROM files WHERE path = ? AND cmd = ?",
        (filename, args_string),
    )
    row = r.fetchone()
    if row is None:
        res = -1
        try:
            res = subprocess.call(args)
        except Exception as ex:
            pass
        if res == 0:
            st = os.stat(filename)
            conn.execute(
                "INSERT INTO files (path, cmd, device, inode, last_processed) VALUES (?, ?, ?, ?, ?)",
                (filename, args_string, st.st_dev, st.st_ino, time.time()),
            )
            conn.commit()
        else:
            print(f"Call of {args} failed with return code {res}")


if __name__ == "__main__":
    main()
