#!/usr/bin/env python3
"""
fretgen — command-line interface for generating fretboard diagrams.

Usage:
  python -m fretgen C whole_tone
  python -m fretgen G half_whole_dim --start 5
  python -m fretgen --list   # list available scales
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fretboard import SCALES, NOTE_NAMES, generate_and_render


def main():
    p = argparse.ArgumentParser(description='Generate verified fretboard diagrams.')
    p.add_argument('root', nargs='?', help='Root note (e.g., C, F#, Bb)')
    p.add_argument('scale', nargs='?', help='Scale name (e.g., whole_tone, locrian_nat2)')
    p.add_argument('--start', type=int, default=3, help='Starting fret (default 3)')
    p.add_argument('--list', action='store_true', help='List available scales')
    p.add_argument('--all', action='store_true', help='Generate all scales for given root')
    args = p.parse_args()

    if args.list:
        print("Available scales:")
        for name in sorted(SCALES):
            print(f"  {name}")
        return

    if not args.root:
        p.print_help()
        return

    # Normalize root (Bb -> A#, etc.)
    root = args.root.replace('b', '#')  # crude but works for common cases
    if root not in NOTE_NAMES:
        # Try flat-to-sharp conversion
        flat_map = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}
        root = flat_map.get(args.root, args.root)
    if root not in NOTE_NAMES:
        print(f"Error: unknown root '{args.root}'. Use {NOTE_NAMES}", file=sys.stderr)
        sys.exit(1)

    if args.all:
        for scale_name in sorted(SCALES):
            try:
                print(generate_and_render(root, scale_name, start_fret=args.start))
                print()
            except Exception as e:
                print(f"  [skipped {scale_name}: {e}]")
        return

    if not args.scale:
        print("Error: scale name required (or use --all)", file=sys.stderr)
        sys.exit(1)

    if args.scale not in SCALES:
        print(f"Error: unknown scale '{args.scale}'. Use --list to see options.", file=sys.stderr)
        sys.exit(1)

    print(generate_and_render(root, args.scale, start_fret=args.start))


if __name__ == '__main__':
    main()
