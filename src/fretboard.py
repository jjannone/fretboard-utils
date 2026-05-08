"""
fretboard.py — core library for fretboard-faithful ASCII diagrams.

Provides:
  - Scale definitions (intervals from root in semitones)
  - Pitch-class math accounting for the G→B major-3rd offset
  - Diagram parser
  - Diagram verifier
  - 2NPS diagram generator
  - Renderer in fretboard-faithful ASCII style

Diagram convention:
  - 6 lines, high e on top, low E on bottom
  - Each line prefixed with string letter + '|'
  - Column position == actual fret position on the neck
  - Adjacent frets squeeze together (e.g., '67', '78')
  - Non-adjacent frets use plain ASCII dashes between them
  - Plain ASCII '-' only (never em/en dash)
  - Patterns transposed so lowest fret >= 3
"""

import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Open string pitch classes (0=C, 1=C#, ..., 11=B)
OPEN_STRINGS = {
    'E': 4,   # low E
    'A': 9,
    'D': 2,
    'G': 7,
    'B': 11,
    'e': 4,   # high e
}

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

STRING_ORDER_LOW_TO_HIGH = ['E', 'A', 'D', 'G', 'B', 'e']
STRING_ORDER_DISPLAY = ['e', 'B', 'G', 'D', 'A', 'E']  # high to low for rendering

# Scale interval patterns (semitones from root)
SCALES = {
    # Diatonic and modes
    'major':              [0, 2, 4, 5, 7, 9, 11],
    'natural_minor':      [0, 2, 3, 5, 7, 8, 10],
    'dorian':             [0, 2, 3, 5, 7, 9, 10],
    'phrygian':           [0, 1, 3, 5, 7, 8, 10],
    'lydian':             [0, 2, 4, 6, 7, 9, 11],
    'mixolydian':         [0, 2, 4, 5, 7, 9, 10],
    'locrian':            [0, 1, 3, 5, 6, 8, 10],
    # Harmonic & melodic minor
    'harmonic_minor':     [0, 2, 3, 5, 7, 8, 11],
    'melodic_minor':      [0, 2, 3, 5, 7, 9, 11],
    # Modes of melodic minor
    'lydian_dominant':    [0, 2, 4, 6, 7, 9, 10],   # 4th mode
    'locrian_nat2':       [0, 2, 3, 5, 6, 8, 10],   # 6th mode
    'altered':            [0, 1, 3, 4, 6, 8, 10],   # 7th mode (super-locrian)
    # Modes of harmonic minor
    'phrygian_dominant':  [0, 1, 4, 5, 7, 8, 10],   # 5th mode
    # Symmetrical
    'whole_tone':         [0, 2, 4, 6, 8, 10],
    'half_whole_dim':     [0, 1, 3, 4, 6, 7, 9, 10],
    'whole_half_dim':     [0, 2, 3, 5, 6, 8, 9, 11],
    'augmented':          [0, 3, 4, 7, 8, 11],
    'chromatic':          list(range(12)),
    # Exotic
    'hungarian_minor':    [0, 2, 3, 6, 7, 8, 11],
    'neapolitan_minor':   [0, 1, 3, 5, 7, 8, 11],
    'neapolitan_major':   [0, 1, 3, 5, 7, 9, 11],
    'double_harmonic':    [0, 1, 4, 5, 7, 8, 11],   # Byzantine / Hijaz
    'persian':            [0, 1, 4, 5, 6, 8, 11],
    'enigmatic':          [0, 1, 4, 6, 8, 10, 11],
    # Pentatonic
    'major_pentatonic':   [0, 2, 4, 7, 9],
    'minor_pentatonic':   [0, 3, 5, 7, 10],
    'blues_minor':        [0, 3, 5, 6, 7, 10],
}


# ---------------------------------------------------------------------------
# Pitch math
# ---------------------------------------------------------------------------

def scale_pitches(root_name: str, scale_name: str) -> set:
    """Return set of pitch classes (0-11) in the scale."""
    if scale_name not in SCALES:
        raise ValueError(f"Unknown scale: {scale_name}. Known: {list(SCALES)}")
    if root_name not in NOTE_NAMES:
        raise ValueError(f"Unknown root: {root_name}. Use one of {NOTE_NAMES}")
    root = NOTE_NAMES.index(root_name)
    return {(root + i) % 12 for i in SCALES[scale_name]}


def pitch_at(string_name: str, fret: int) -> int:
    """Return pitch class (0-11) at the given string and fret."""
    return (OPEN_STRINGS[string_name] + fret) % 12


def note_name(string_name: str, fret: int) -> str:
    """Return pitch name (e.g., 'F#') at the given string and fret."""
    return NOTE_NAMES[pitch_at(string_name, fret)]


# ---------------------------------------------------------------------------
# Diagram parsing & rendering
# ---------------------------------------------------------------------------

DIAGRAM_LINE_RE = re.compile(r'^([EADGBe])(\|?)(.*?)\|?$')


def parse_diagram(diagram: str):
    """
    Parse a diagram into list of (string_name, fret, column) tuples.

    Convention:
      - Each digit is a fret value (single-digit: 0-9)
      - Adjacent digits like '67' = fret 6 + fret 7 (two notes)
      - Two-digit frets (10-24) must be wrapped in parens: '(10)', '(12)'
        because '10' is ambiguous with fret-1 + fret-0.
    """
    notes = []
    for line in diagram.strip().split('\n'):
        line = line.rstrip()
        if not line:
            continue
        m = DIAGRAM_LINE_RE.match(line)
        if not m:
            continue
        string_name = m.group(1)
        rest = m.group(2) + m.group(3)
        i = 0
        while i < len(rest):
            ch = rest[i]
            if ch == '(':
                # multi-digit fret in parens, e.g. (10), (12)
                end = rest.find(')', i)
                if end > i:
                    fret_str = rest[i+1:end]
                    if fret_str.isdigit():
                        notes.append((string_name, int(fret_str), i))
                    i = end + 1
                    continue
                else:
                    i += 1
                    continue
            if ch.isdigit():
                notes.append((string_name, int(ch), i))
            i += 1
    return notes


def verify(diagram: str, root_name: str, scale_name: str,
           label: str = "", verbose: bool = False) -> bool:
    """Check that every note in the diagram belongs to the named scale."""
    pitches = scale_pitches(root_name, scale_name)
    notes = parse_diagram(diagram)
    bad = []
    results = []
    for s, f, _col in notes:
        pc = pitch_at(s, f)
        ok = pc in pitches
        results.append((s, f, NOTE_NAMES[pc], ok))
        if not ok:
            bad.append((s, f, NOTE_NAMES[pc]))
    if verbose:
        print(f"=== {label or scale_name} (root={root_name}) ===")
        print(f"  Scale: {sorted(NOTE_NAMES[p] for p in pitches)}")
        for s, f, n, ok in results:
            print(f"    {s}{f} = {n}  [{'OK' if ok else 'BAD'}]")
        if bad:
            print(f"  >>> {len(bad)} OUT-OF-SCALE: {bad}")
        else:
            print(f"  >>> ALL {len(results)} IN SCALE")
    return len(bad) == 0


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def frets_in_scale(string_name: str, pitches: set,
                   fret_min: int = 3, fret_max: int = 15):
    """All frets on this string (within range) that play a pitch in the scale."""
    open_pc = OPEN_STRINGS[string_name]
    return [f for f in range(fret_min, fret_max + 1)
            if (open_pc + f) % 12 in pitches]


def pick_pair(frets, prev_low=None, max_stretch: int = 4):
    """
    Pick a pair of consecutive in-scale frets.
    Prefers smaller stretch and proximity to prev_low.
    """
    candidates = []
    for i in range(len(frets) - 1):
        f1, f2 = frets[i], frets[i + 1]
        stretch = f2 - f1
        if stretch <= max_stretch:
            score = stretch
            if prev_low is not None:
                score += abs(f1 - prev_low) * 0.5
            candidates.append((score, f1, f2))
    if not candidates:
        return None
    candidates.sort()
    return (candidates[0][1], candidates[0][2])


def generate_2nps(root_name: str, scale_name: str, start_fret: int = 3):
    """Generate a 2-note-per-string pattern starting around start_fret."""
    pitches = scale_pitches(root_name, scale_name)
    pattern = {}
    prev_low = start_fret
    for s in STRING_ORDER_LOW_TO_HIGH:
        frets = frets_in_scale(s, pitches, fret_min=max(3, start_fret - 1))
        pair = pick_pair(frets, prev_low=prev_low)
        if pair is None:
            frets = frets_in_scale(s, pitches, fret_min=3)
            pair = pick_pair(frets, prev_low=prev_low)
        if pair is None:
            return None
        pattern[s] = pair
        prev_low = pair[0]
    return pattern


def render(pattern: dict, label: str = "", width: int = 20) -> str:
    """Render a {string: (f1, f2)} pattern as a fretboard-faithful diagram.

    Two-digit frets (10+) are wrapped in parens: (10), (12), etc.
    Width should be at least max_fret + 4 to fit padding.
    """
    # Auto-size width if needed
    max_fret = max(max(p) for p in pattern.values())
    needed = max_fret + 4
    if width < needed:
        width = needed

    def fret_token(f: int) -> str:
        return f"({f})" if f >= 10 else str(f)

    lines = []
    for s in STRING_ORDER_DISPLAY:
        f1, f2 = pattern[s]
        chars = ['-'] * width
        t1 = fret_token(f1)
        t2 = fret_token(f2)
        # Place t1 at column f1, t2 at column f2
        # If f2 == f1 + 1 and both single-digit, squeeze them adjacent
        if f2 == f1 + 1 and len(t1) == 1 and len(t2) == 1:
            chars[f1] = t1
            chars[f1 + 1] = t2
        else:
            # Place each token starting at its fret column
            for j, c in enumerate(t1):
                if f1 + j < width:
                    chars[f1 + j] = c
            for j, c in enumerate(t2):
                if f2 + j < width:
                    chars[f2 + j] = c
        lines.append(f"{s}|" + ''.join(chars) + "|")
    out = '\n'.join(lines)
    if label:
        out += f"  {label}"
    return out


def generate_and_render(root_name: str, scale_name: str,
                        label: str = None, start_fret: int = 3,
                        width: int = 18) -> str:
    """One-shot: generate a verified 2NPS diagram or raise on failure."""
    pattern = generate_2nps(root_name, scale_name, start_fret=start_fret)
    if pattern is None:
        raise RuntimeError(f"Could not generate {root_name} {scale_name}")
    if label is None:
        label = f"{root_name} {scale_name.replace('_', ' ').title()}"
    diagram = render(pattern, label, width=width)
    if not verify(diagram, root_name, scale_name, label):
        raise RuntimeError(f"Generated diagram failed verification: {label}")
    return diagram
