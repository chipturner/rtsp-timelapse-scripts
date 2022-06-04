#!/usr/bin/python3

import os
import pathlib
import redis
import sqlite3
import subprocess
import sys
import time

KEY_NAME = "process_once"


def main() -> None:
    r = redis.Redis(unix_socket_path="/var/run/redis/redis-server.sock")
    filename, args = sys.argv[1], sys.argv[2:]
    args_string = b"\0".join(arg.encode("utf-8") for arg in args)
    filename = os.path.realpath(filename)
    for idx in range(len(args)):
        args[idx] = args[idx].replace("{}", filename)

    key = f"{filename}:{args_string}"
    res = r.sismember(KEY_NAME, key)
    if not res:
        res = -1
        try:
            res = subprocess.call(args)
        except Exception as ex:
            pass
        if res == 0:
            st = os.stat(filename)
            r.sadd(KEY_NAME, key)
        else:
            print(f"Call of {args} failed with return code {res}")


if __name__ == "__main__":
    main()
