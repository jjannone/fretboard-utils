# fretboard-utils

Tools for generating and verifying **fretboard-faithful ASCII diagrams** for guitar
scales and patterns. Built to catch the kinds of errors LLMs (and humans) make
when transcribing scales by hand — especially around the G→B major-3rd offset.

## What's a "fretboard-faithful" diagram?

It's a stripped-down ASCII tab where **column position equals actual fret
position on the neck**. There's no rhythm, no time — just a position diagram:

```
e|----4-6-----------|
B|---3-5------------|
G|---3-5------------|
D|----4-6-----------|
A|---3-5------------|
E|----4-6-----------|  C Whole-Tone
```

Conventions:

- 6 lines, high `e` on top, low `E` on bottom
- Each line prefixed with the string letter + `|`
- Column position maps to actual fret — fret 5 is in column 5
- Adjacent frets squeeze together: `67`, `78`
- Non-adjacent frets use plain ASCII dashes between them, where the number of
  dashes reflects the gap: `5-7` (2-fret gap), `3--6` (3-fret gap), `3---7` (4-fret)
- Plain ASCII hyphen-minus `-` only — never em dash `—` or en dash `–`
- Lines padded to align at the closing `|`
- Patterns transposed so the lowest fret is ≥ 3 (no open strings)
- Two-digit frets rendered as `fret % 10` (10 → `0`, 11 → `1`, 12 → `2`, …); column position is authoritative

## Why this exists

Transcribing scale shapes by hand is error-prone, especially because the guitar's
B string is tuned a major 3rd above the G string instead of a perfect 4th like
every other adjacent pair. That offset means a fingering pattern that looks
geometrically symmetric on the lower five strings *won't* be symmetric across
the G→B boundary, and the same fret on B vs G produces different scale degrees.

This library does the pitch-class math for you and verifies every note against
the scale's pitch set.

## Install

No dependencies beyond the Python standard library. Python 3.8+.

```sh
git clone <your-repo-url>
cd fretboard-utils
python3 tests/test_fretboard.py   # run tests
```

## Usage

### As a library

```python
from fretboard import generate_and_render, verify, scale_pitches

# Generate a verified 2-note-per-string diagram
print(generate_and_render('C', 'whole_tone'))

# Verify your own diagram
diagram = """e|----4-6----|
B|---3-5-----|
G|---3-5-----|
D|----4-6----|
A|---3-5-----|
E|----4-6----|"""
assert verify(diagram, 'C', 'whole_tone')
```

### From the command line

```sh
# List available scales
python examples/fretgen.py --list

# Generate one scale
python examples/fretgen.py C hungarian_minor

# Generate all scales for a root
python examples/fretgen.py C --all
```

## Available scales

Diatonic modes, harmonic/melodic minor and their modes, symmetrical scales
(whole-tone, diminished, augmented, chromatic), and exotic scales (Hungarian
minor, Neapolitan, double harmonic, Persian, enigmatic). See `src/fretboard.py`
for the full list and intervals.

## Extending

To add a new scale, edit `SCALES` in `src/fretboard.py`:

```python
SCALES['my_scale'] = [0, 2, 3, 6, 8, 10]   # intervals from root in semitones
```

Then run the tests — `test_generate_and_verify_all_scales` will pick it up
automatically.

## Limitations

The auto-generator picks the closest available pair on each string. It produces
**accurate** diagrams but doesn't always produce **idiomatic** ones — a
human player might prefer different fret choices for ergonomics, melodic
contour, or to emphasize specific intervals. The output is a starting point,
not a fingering recommendation.

## License

MIT
