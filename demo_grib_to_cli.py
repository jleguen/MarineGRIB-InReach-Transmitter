#!/usr/bin/env python3
"""Demo: encode a GRIB file and print inReach-style split messages to CLI.

This script performs the same local transformations as the service pipeline:
1) Read GRIB file bytes
2) Compress with zlib
3) Base64 encode
4) Split into inReach-sized chunks and format as message frames

No network calls are made.
"""

from __future__ import annotations

import argparse
import base64
import sys
import zlib
from pathlib import Path


DEFAULT_SPLIT_LENGTH = 120


def encode_grib_file(path: Path) -> str:
    """Read GRIB bytes, zlib-compress, and base64-encode."""
    grib_binary = path.read_bytes()
    compressed_grib = zlib.compress(grib_binary)
    return base64.b64encode(compressed_grib).decode("utf-8")


def split_message(payload: str, split_length: int) -> list[str]:
    """Split payload into inReach-style framed messages."""
    if split_length <= 0:
        raise ValueError("split_length must be > 0")

    total_splits = (len(payload) + split_length - 1) // split_length
    chunks = [payload[i : i + split_length] for i in range(0, len(payload), split_length)]

    return [
        f"msg {index + 1}/{total_splits}:\n{chunk}\nend"
        for index, chunk in enumerate(chunks)
    ]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Encode and split a GRIB file for inReach-style messaging (CLI demo, no sending)."
    )
    parser.add_argument("grib_path", help="Path to .grb file")
    parser.add_argument(
        "--split-length",
        type=int,
        default=DEFAULT_SPLIT_LENGTH,
        help=f"Maximum payload chars per message chunk (default: {DEFAULT_SPLIT_LENGTH})",
    )
    parser.add_argument(
        "--show-payload",
        action="store_true",
        help="Also print the full base64 payload before split messages",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    grib_path = Path(args.grib_path)

    if not grib_path.exists():
        print(f"Error: file does not exist: {grib_path}", file=sys.stderr)
        return 1
    if not grib_path.is_file():
        print(f"Error: not a file: {grib_path}", file=sys.stderr)
        return 1

    encoded_payload = encode_grib_file(grib_path)
    chunks = split_message(encoded_payload, args.split_length)

    original_size = grib_path.stat().st_size
    compressed_size = len(zlib.compress(grib_path.read_bytes()))

    print("=== GRIB Encode/Split Demo ===")
    print(f"File: {grib_path}")
    print(f"Original bytes: {original_size}")
    print(f"Compressed bytes (zlib): {compressed_size}")
    print(f"Base64 chars: {len(encoded_payload)}")
    print(f"Split length: {args.split_length}")
    print(f"Message count: {len(chunks)}")

    if args.show_payload:
        print("\n=== Base64 Payload ===")
        print(encoded_payload)

    print("\n=== inReach-style Messages ===")
    for idx, chunk in enumerate(chunks, start=1):
        print(f"\n--- Message {idx}/{len(chunks)} ---")
        print(chunk)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
