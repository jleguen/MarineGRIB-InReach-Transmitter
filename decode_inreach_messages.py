#!/usr/bin/env python3
"""Decode split inReach message text back into a GRIB file.

Input format supports blocks like:
msg 1/5:
<base64 chunk>
end

The script concatenates chunk payloads, base64-decodes, zlib-decompresses,
and writes the resulting .grb file.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import re
import sys
import zlib
from pathlib import Path

MSG_HEADER_RE = re.compile(r"^\s*msg\s+(\d+)\s*/\s*(\d+)\s*:\s*$", re.IGNORECASE)
END_RE = re.compile(r"^\s*end\s*$", re.IGNORECASE)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild a GRIB file from split inReach message text"
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to text file containing split messages",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="decoded_output.grb",
        help="Output GRIB file path (default: decoded_output.grb)",
    )
    parser.add_argument(
        "--paste",
        action="store_true",
        help="Paste split messages directly in terminal (default when no input_file)",
    )
    parser.add_argument(
        "--from-file",
        action="store_true",
        help="Prompt for input/output file paths (interactive file mode)",
    )
    return parser.parse_args(argv)


def _default_android_dir() -> Path:
    candidates = [
        Path("/sdcard/Download"),
        Path("/storage/emulated/0/Download"),
        Path.cwd(),
    ]
    for path in candidates:
        if path.exists():
            return path
    return Path.cwd()


def _prompt_user_paths() -> tuple[Path, Path]:
    base_dir = _default_android_dir()
    print("No arguments provided. Interactive mode.")
    print(f"Tip: put your message file in {base_dir}")

    input_raw = input("Input text file path: ").strip()
    input_path = Path(input_raw).expanduser()

    default_output = str((base_dir / "rebuilt.grb").resolve())
    output_raw = input(f"Output GRIB path [{default_output}]: ").strip()
    output_path = Path(output_raw).expanduser() if output_raw else Path(default_output)

    return input_path, output_path


def _prompt_pasted_messages() -> str:
    print("Paste your split messages below.")
    print("When finished, type END on a new line and press Enter.")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def extract_base64_payload(text: str) -> str:
    """Extract and concatenate payload lines between msg/end wrappers.

    If msg headers are present, payload blocks are reordered by message index,
    so input order does not matter.
    """
    lines = text.splitlines()

    payload_parts: list[str] = []
    inside_block = False
    found_header = False
    current_index = None
    current_total = None
    current_lines: list[str] = []
    indexed_parts: list[tuple[int, int, str]] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        header_match = MSG_HEADER_RE.match(line)
        if header_match:
            found_header = True
            # Gracefully close previous block if malformed input omitted "end".
            if (
                inside_block
                and current_lines
                and current_index is not None
                and current_total
            ):
                indexed_parts.append(
                    (current_index, current_total, "".join(current_lines))
                )
            current_index = int(header_match.group(1))
            current_total = int(header_match.group(2))
            current_lines = []
            inside_block = True
            continue

        if END_RE.match(line):
            if (
                inside_block
                and current_lines
                and current_index is not None
                and current_total
            ):
                indexed_parts.append(
                    (current_index, current_total, "".join(current_lines))
                )
            inside_block = False
            current_index = None
            current_total = None
            current_lines = []
            continue

        if inside_block:
            current_lines.append(line)

    # Close trailing block if file ended without "end".
    if inside_block and current_lines and current_index is not None and current_total:
        indexed_parts.append((current_index, current_total, "".join(current_lines)))

    if found_header:
        if not indexed_parts:
            raise ValueError(
                "Message headers found, but no payload blocks were extracted"
            )

        totals = {total for _, total, _ in indexed_parts}
        if len(totals) != 1:
            raise ValueError(f"Inconsistent total counts in headers: {sorted(totals)}")
        expected_total = totals.pop()

        by_index: dict[int, str] = {}
        for index, _total, payload in indexed_parts:
            if index in by_index:
                raise ValueError(f"Duplicate message index found: {index}")
            by_index[index] = payload

        missing = [idx for idx in range(1, expected_total + 1) if idx not in by_index]
        if missing:
            raise ValueError(f"Missing message indices: {missing}")

        payload_parts = [by_index[idx] for idx in range(1, expected_total + 1)]

    # Fallback: if no explicit msg/end wrappers are present, try loose extraction.
    if not payload_parts and not found_header:
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if MSG_HEADER_RE.match(line) or END_RE.match(line):
                continue
            if line.startswith("--- Message") or line.startswith("==="):
                continue
            payload_parts.append(line)

    if not payload_parts:
        raise ValueError("No base64 payload found in input file")

    return "".join(payload_parts)


def decode_to_grib(payload: str) -> bytes:
    """Decode base64 payload then zlib-decompress to original GRIB bytes."""
    try:
        compressed = base64.b64decode(payload, validate=True)
    except binascii.Error as exc:
        raise ValueError(f"Invalid base64 payload: {exc}") from exc

    try:
        return zlib.decompress(compressed)
    except zlib.error as exc:
        raise ValueError(f"Could not zlib-decompress payload: {exc}") from exc


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    text: str

    default_paste_mode = not args.input_file and not args.from_file

    if args.paste or default_paste_mode:
        text = _prompt_pasted_messages()
        if not text.strip():
            print("Error: no pasted content provided", file=sys.stderr)
            return 1
        output_path = Path(args.output)
    elif args.input_file:
        input_path = Path(args.input_file)
        output_path = Path(args.output)
        if not input_path.exists():
            print(f"Error: input file not found: {input_path}", file=sys.stderr)
            return 1
        if not input_path.is_file():
            print(f"Error: input path is not a file: {input_path}", file=sys.stderr)
            return 1
        text = input_path.read_text(encoding="utf-8", errors="replace")
    else:
        input_path, output_path = _prompt_user_paths()
        if not input_path.exists():
            print(f"Error: input file not found: {input_path}", file=sys.stderr)
            return 1
        if not input_path.is_file():
            print(f"Error: input path is not a file: {input_path}", file=sys.stderr)
            return 1
        text = input_path.read_text(encoding="utf-8", errors="replace")

    try:
        payload = extract_base64_payload(text)
        grib_bytes = decode_to_grib(payload)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_path.write_bytes(grib_bytes)
    print(f"Wrote GRIB file: {output_path}")
    print(f"Output bytes: {len(grib_bytes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
