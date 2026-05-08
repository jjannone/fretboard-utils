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
  - Each line: {string_letter}{config_char}{body}|
      config_char = '|'  normal string, fretted only (backward-compatible)
                  = 'X'  normal string, fretted only (explicit annotation)
                  = '0'  open string (fret 0 is playable)
                  = 'N'  spider capo at fret N (single digit, 1-9)
  - Column position in body == actual fret position on the neck
  - Digit shown = fret % 10; column is authoritative for actual fret
  - Adjacent frets squeeze together (e.g., '67', '90')
  - Plain ASCII '-' only (never em/en dash)
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

DIAGRAM_LINE_RE = re.compile(r'^([EADGBe])([|0-9Xx]?)(.*?)\|?$')


def parse_diagram(diagram: str):
    """
    Parse a diagram into list of (string_name, fret, column) tuples.

    Line format: {letter}{config_char}{body}|
      config_char: '|' normal, digit = capo fret,
                  '0' = open string, 'X'/'x' = normal fretted (no open).
    Column index in body is authoritative for fret value (fret = column).
    All strings with a body are parsed regardless of config_char.
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
        body = m.group(3)
        for i, ch in enumerate(body):
            if ch.isdigit():
                notes.append((string_name, i, i))
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
                   fret_min: int = 3, fret_max: int = 15,
                   capo_fret: int = None):
    """All frets on this string that play a pitch in the scale.

    capo_fret: if given, only frets strictly above the capo are searched
    (capo_fret+1 to fret_max). The capo tone itself is always ringing as a
    drone and is shown in the prefix, so it is not a candidate body note.
    capo_fret=0 (open string) is the exception: fret 0 is a valid body note.
    """
    open_pc = OPEN_STRINGS[string_name]
    if capo_fret is not None:
        low = 0 if capo_fret == 0 else capo_fret + 1
        return [f for f in range(low, fret_max + 1)
                if (open_pc + f) % 12 in pitches]
    return [f for f in range(fret_min, fret_max + 1)
            if (open_pc + f) % 12 in pitches]


def pick_pair(frets, target=None, min_stretch: int = 0, max_stretch: int = 5):
    """
    Pick a pair of in-scale frets where stretch is in [min_stretch, max_stretch].
    Primary sort: proximity of f1 to target.
    Tiebreak: prefer larger stretch (bolder interval).
    Falls back to min_stretch=0 if nothing qualifies.
    """
    candidates = []
    for i in range(len(frets)):
        for j in range(i + 1, len(frets)):
            f1, f2 = frets[i], frets[j]
            stretch = f2 - f1
            if stretch > max_stretch:
                break
            if stretch < min_stretch:
                continue
            proximity = abs(f1 - target) if target is not None else 0
            candidates.append((proximity, -stretch, f1, f2))  # -stretch: prefer wider
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2], candidates[0][3]


def generate_2nps(root_name: str, scale_name: str, start_fret: int = 3,
                  min_stretch: int = 0, max_stretch: int = 5,
                  direction: str = 'up', position_shift: float = 0,
                  string_configs: dict = None):
    """Generate a 2-note-per-string pattern.

    direction='up'  : classic ascending box — fret floor rises with prev pair.
    direction='free': each string targets start_fret + string_index * position_shift,
                      searching the full neck. Positive position_shift moves up the
                      neck (higher frets); negative moves down. A position_shift of
                      ~1.5 spans ~8 frets across all 6 strings.

    min_stretch / max_stretch: fret span of the chosen pair on each string.
    Set min_stretch=3 to force intervals of a minor 3rd or larger (up to P4 at 5).

    string_configs: optional dict mapping string name -> int, 'X', or None.
      None  = excluded (string skipped entirely, not rendered).
      'X'   = normal fretted string, rendered with 'X' prefix.
      0     = open string (fret 0 is a candidate note).
      N > 0 = spider capo at fret N (capo position is a candidate note;
              frets above the capo are also searched).
    Strings absent from string_configs are treated normally.
    """
    pitches = scale_pitches(root_name, scale_name)
    pattern = {}
    prev_low = start_fret

    for idx, s in enumerate(STRING_ORDER_LOW_TO_HIGH):
        capo_fret = None
        if string_configs and s in string_configs:
            val = string_configs[s]
            if val is None:
                continue  # excluded string
            if val != 'X':
                capo_fret = val  # int: 0 = open, N = capo at fret N
            # 'X' falls through to normal fretted logic below

        if capo_fret is not None:
            target = start_fret + idx * position_shift if direction == 'free' else prev_low
            frets = frets_in_scale(s, pitches, capo_fret=capo_fret)
        elif direction == 'up':
            target = prev_low
            frets = frets_in_scale(s, pitches, fret_min=max(3, prev_low - 1))
        else:
            target = start_fret + idx * position_shift
            frets = frets_in_scale(s, pitches, fret_min=3)

        pair = pick_pair(frets, target=target, min_stretch=min_stretch, max_stretch=max_stretch)
        if pair is None and min_stretch > 0:
            pair = pick_pair(frets, target=target, min_stretch=0, max_stretch=max_stretch)
        if pair is None:
            frets_full = frets_in_scale(s, pitches,
                                        fret_min=3 if capo_fret is None else capo_fret,
                                        capo_fret=capo_fret)
            pair = pick_pair(frets_full, target=target, min_stretch=0, max_stretch=max_stretch)
        if pair is None:
            return None

        pattern[s] = pair
        prev_low = pair[0]

    return pattern


def render(pattern: dict, label: str = "", width: int = 20,
           string_configs: dict = None) -> str:
    """Render a {string: (f1, f2)} pattern as a fretboard-faithful diagram.

    Every fret is rendered as a single digit equal to fret % 10.
    Column position is authoritative for the actual fret.

    string_configs: if given, drives the config char in each prefix.
      None -> 'X' with all-dash body (excluded, not generated)
      'X'  -> 'X' prefix, normal fretted body
      0    -> '0' (open string)
      N    -> str(N) (capo at fret N)
    Strings absent from string_configs use '|' (normal).
    """
    if pattern:
        max_fret = max(max(p) for p in pattern.values())
        needed = max_fret + 4
        if width < needed:
            width = needed

    lines = []
    for s in STRING_ORDER_DISPLAY:
        if string_configs and s in string_configs and string_configs[s] is None:
            chars = ['-'] * width
            chars[0] = ' '
            lines.append(f"{s}X" + ''.join(chars) + "|")
            continue

        config_char = '|'
        if string_configs and s in string_configs:
            val = string_configs[s]
            config_char = 'X' if val == 'X' else str(val)

        f1, f2 = pattern[s]
        chars = ['-'] * width
        chars[0] = ' '
        chars[f1] = str(f1 % 10)
        chars[f2] = str(f2 % 10)
        lines.append(f"{s}{config_char}" + ''.join(chars) + "|")

    out = '\n'.join(lines)
    if label:
        out += f"  {label}"
    return out


def generate_and_render(root_name: str, scale_name: str,
                        label: str = None, start_fret: int = 3,
                        min_stretch: int = 0, max_stretch: int = 5,
                        direction: str = 'up', position_shift: float = 0,
                        string_configs: dict = None,
                        width: int = 18) -> str:
    """One-shot: generate a verified 2NPS diagram or raise on failure."""
    if string_configs:
        capo_frets = {v for v in string_configs.values()
                      if isinstance(v, int) and v > 0}
        if len(capo_frets) > 1:
            raise ValueError(
                f"Spider capo can only be on one fret; got {sorted(capo_frets)}")
    pattern = generate_2nps(root_name, scale_name, start_fret=start_fret,
                            min_stretch=min_stretch, max_stretch=max_stretch,
                            direction=direction, position_shift=position_shift,
                            string_configs=string_configs)
    if pattern is None:
        raise RuntimeError(f"Could not generate {root_name} {scale_name}")
    if label is None:
        label = f"{root_name} {scale_name.replace('_', ' ').title()}"
    diagram = render(pattern, label, width=width, string_configs=string_configs)
    if not verify(diagram, root_name, scale_name, label):
        raise RuntimeError(f"Generated diagram failed verification: {label}")
    return diagram


def side_by_side(left: str, left_label: str,
                 right: str, right_label: str,
                 gap: int = 4) -> str:
    """Render two diagrams side by side with labels centered below each."""
    l_lines = left.split('\n')
    r_lines = right.split('\n')
    l_w = max(len(line) for line in l_lines)
    r_w = max(len(line) for line in r_lines)
    n = max(len(l_lines), len(r_lines))
    l_lines += [''] * (n - len(l_lines))
    r_lines += [''] * (n - len(r_lines))
    rows = [l.ljust(l_w) + ' ' * gap + r for l, r in zip(l_lines, r_lines)]
    rows.append(left_label.center(l_w) + ' ' * gap + right_label.center(r_w))
    return '\n'.join(rows)
