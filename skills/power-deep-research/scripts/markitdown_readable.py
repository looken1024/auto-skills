#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from markitdown import MarkItDown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a URL or local file into markdown using markitdown."
    )
    parser.add_argument(
        "source",
        help="A local path or an http/https URL.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write markdown to this file instead of stdout.",
    )
    parser.add_argument(
        "--no-title",
        action="store_true",
        help="Do not prepend a title header.",
    )
    return parser.parse_args()


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def derive_title(source: str) -> str:
    if is_url(source):
        return source.rstrip("/").split("/")[-1] or source
    return Path(source).name


def convert_source(source: str) -> str:
    converter = MarkItDown()
    if is_url(source):
        result = converter.convert_url(source)
    else:
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Source does not exist: {path}")
        result = converter.convert_local(path)
    return getattr(result, "text_content", "").strip()


def main() -> int:
    args = parse_args()
    markdown = convert_source(args.source)
    if not markdown:
        raise RuntimeError("markitdown returned empty content")

    if not args.no_title:
        title = derive_title(args.source)
        markdown = f"# {title}\n\n{markdown}"

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(output_path.resolve())
        return 0

    sys.stdout.write(markdown)
    if not markdown.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"markitdown_readable error: {exc}", file=sys.stderr)
        raise SystemExit(1)
