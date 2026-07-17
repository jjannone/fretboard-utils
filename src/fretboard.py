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
      config_char = '0'  normal string, nut position (default)
                  = '|'  fretted only — explicit "no open, no capo" (unusual)
                  = 'X'  string muted/bypassed
                  = 'N'  spider capo at fret N (single digit, 1-9)
  - Column position in body == actual fret position on the neck
  - Digit shown = fret % 10; column is authoritative for actual fret
  - Adjacent frets squeeze together (e.g., '67', '90')
  - Plain ASCII '-' only (never em/en dash)
"""

import re
from contextlib import contextmanager

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

# Maximum semitone distance between adjacent fingered notes on one string.
# Default is a minor 3rd (3 semitones) — wider than this is hard to reach
# without shifting position. Scale generators use this as the default cap;
# arpeggios override it because chord tones are inherently sparser.
MAX_FINGER_STEP = 3

# A scale that contains NO minor 3rd anywhere (no two of its tones are 3
# semitones apart — e.g. the whole-tone scale, whose intervals are all even)
# has no m3 grouping to reach for, so its smallest "wide" 2-note option is a
# major 3rd. For such scales the finger-reach cap is raised one semitone to a
# major 3rd (4); every other scale keeps the m3 cap.
MAJOR_THIRD_STEP = 4


def _scale_has_minor_third(scale_name: str) -> bool:
    """True iff some pair of the scale's tones is a minor 3rd (3 semitones)
    apart, counted cyclically (so B→D across the octave counts)."""
    pcs = {i % 12 for i in SCALES[scale_name]}
    return any((p + 3) % 12 in pcs for p in pcs)


def effective_finger_step(scale_name: str) -> int:
    """Per-scale finger-reach cap: a major 3rd (4) for scales with no minor
    3rd anywhere, else the global MAX_FINGER_STEP (a minor 3rd)."""
    return MAJOR_THIRD_STEP if not _scale_has_minor_third(scale_name) else MAX_FINGER_STEP

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
    The highest non-zero digit config char across all lines is the higher
    spider-capo fret M; the body is then shifted so column k represents
    fret (k + M). When no capo is present, M = 0 and column == fret as before.
    """
    raw_lines = []
    for line in diagram.strip().split('\n'):
        line = line.rstrip()
        if not line:
            continue
        m = DIAGRAM_LINE_RE.match(line)
        if not m:
            continue
        raw_lines.append(m)

    # Pass 1: determine the higher-capo fret (display shift).
    shift = 0
    for m in raw_lines:
        cfg = m.group(2)
        if cfg.isdigit() and cfg != '0':
            shift = max(shift, int(cfg))

    # Pass 2: extract notes, mapping column k to fret (k + shift).
    notes = []
    for m in raw_lines:
        string_name = m.group(1)
        body = m.group(3)
        for i, ch in enumerate(body):
            if ch == '|':
                break
            if ch.isdigit():
                notes.append((string_name, i + shift, i))
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
                   fret_min: int = 3, fret_max: int = 22,
                   capo_fret: int = None):
    """All frets on this string that play a pitch in the scale.

    capo_fret: if given, only frets above the capo are searched. The capo
    tone itself is always ringing as a drone and is shown in the prefix,
    so it is not a candidate body note. capo_fret=0 (open string) is the
    exception: fret 0 is a valid body note.

    fret_min is also honored on capo'd strings: the effective floor is
    max(capo_fret + 1, fret_min). This lets a higher spider-capo bar set
    a global lower bound on body frets across all strings.
    """
    open_pc = OPEN_STRINGS[string_name]
    if capo_fret is not None:
        if capo_fret == 0:
            low = 0
        else:
            low = max(capo_fret + 1, fret_min)
        return [f for f in range(low, fret_max + 1)
                if (open_pc + f) % 12 in pitches]
    return [f for f in range(fret_min, fret_max + 1)
            if (open_pc + f) % 12 in pitches]


def _max_capo(string_configs: dict) -> int:
    """The highest capo fret in string_configs, or 0 if no capo."""
    if not string_configs:
        return 0
    return max((v for v in string_configs.values()
                if isinstance(v, int) and v > 0), default=0)


def _drone_pc(string_name: str, string_configs: dict):
    """Pitch class of the always-sounding drone on a string.

    - capo at fret N (val=N>0)   → (open + N) % 12
    - explicit open (val=0)      → open
    - default (no entry)         → open string drones at fret 0
    - 'X' / '|' / None           → no drone (string is muted, fretted-only,
                                    or excluded), returns None.
    """
    if string_configs and string_name in string_configs:
        val = string_configs[string_name]
        if val is None or val == 'X' or val == '|':
            return None
        if isinstance(val, int):
            return (OPEN_STRINGS[string_name] + val) % 12
    return OPEN_STRINGS[string_name] % 12


def _effective_fret_min(string_configs: dict, base_min: int = 3) -> int:
    """Lowest legal body fret on any string given the spider-capo bar(s).

    The highest capo bar physically blocks every string at and below its
    fret, so all body notes must sit at max_capo + 1 or higher. Clamped to
    the convention's base minimum (default 3) when no capo is present.
    """
    return max(base_min, _max_capo(string_configs) + 1)


def pick_pair(frets, target=None, min_stretch: int = 0, max_stretch: int = None,
              required_pc: int = None, string_pc: int = None, cap: int = None):
    """
    Pick a pair of in-scale frets where stretch is in [min_stretch, max_stretch].
    Primary sort: proximity of f1 to target.
    Tiebreak: prefer larger stretch (bolder interval).
    Falls back to min_stretch=0 if nothing qualifies.

    cap is the hard finger-reach limit (default MAX_FINGER_STEP). Callers pass a
    scale-derived cap via effective_finger_step() to allow a major 3rd on scales
    that contain no minor 3rd. max_stretch is silently clamped to cap. Pass None
    to use the cap directly.

    required_pc / string_pc: if both given, at least one of the two chosen frets
    must produce the pitch class `required_pc` on a string whose open pitch is
    `string_pc`. Used to force the root onto a specific string.
    """
    if cap is None:
        cap = MAX_FINGER_STEP
    if max_stretch is None or max_stretch > cap:
        max_stretch = cap
    if min_stretch > max_stretch:
        min_stretch = max_stretch
    candidates = []
    for i in range(len(frets)):
        for j in range(i + 1, len(frets)):
            f1, f2 = frets[i], frets[j]
            stretch = f2 - f1
            if stretch > max_stretch:
                break
            if stretch < min_stretch:
                continue
            if required_pc is not None and string_pc is not None:
                if (string_pc + f1) % 12 != required_pc and \
                   (string_pc + f2) % 12 != required_pc:
                    continue
            proximity = abs(f1 - target) if target is not None else 0
            candidates.append((proximity, -stretch, f1, f2))  # -stretch: prefer wider
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2], candidates[0][3]


def pick_triple(frets, target=None, min_span: int = 2, max_span: int = 6,
                max_step: int = None,
                required_pc: int = None, string_pc: int = None,
                required_first_pc: int = None, cap: int = None):
    """
    Pick 3 consecutive in-scale frets where (last - first) is in [min_span, max_span]
    AND each adjacent gap (b-a, c-b) is at most max_step.

    required_first_pc / string_pc: if both given, the FIRST fret in the triple
    must produce the pitch class `required_first_pc` on a string whose open
    pitch is `string_pc`. Used to enforce 3NPS scale-tone continuity across
    strings (each string starts on the next scale tone after the previous
    string's last).

    Primary sort: proximity of first fret to target.
    Tiebreak: prefer tighter span (compact box).

    max_step is hard-capped at MAX_FINGER_STEP — the module-wide finger-reach
    limit. Values above the cap are silently clamped. Pass None (default) to
    use the cap directly.
    """
    if cap is None:
        cap = MAX_FINGER_STEP
    if max_step is None or max_step > cap:
        max_step = cap
    candidates = []
    for i in range(len(frets) - 2):
        a, b, c = frets[i], frets[i + 1], frets[i + 2]
        if (b - a) > max_step or (c - b) > max_step:
            continue
        span = c - a
        if span > max_span:
            continue
        if span < min_span:
            continue
        if required_pc is not None and string_pc is not None:
            if not any((string_pc + f) % 12 == required_pc for f in (a, b, c)):
                continue
        if required_first_pc is not None and string_pc is not None:
            if (string_pc + a) % 12 != required_first_pc:
                continue
        proximity = abs(a - target) if target is not None else 0
        candidates.append((proximity, span, a, b, c))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2], candidates[0][3], candidates[0][4]


def pick_single(frets, target=None,
                required_pc: int = None, string_pc: int = None):
    """Pick one in-scale fret, preferring proximity to target.

    Used for 1-note-per-string patterns (e.g. arpeggios) where there's
    only one fingered note per string and no within-string reach to limit.
    """
    candidates = []
    for f in frets:
        if required_pc is not None and string_pc is not None:
            if (string_pc + f) % 12 != required_pc:
                continue
        proximity = abs(f - target) if target is not None else 0
        candidates.append((proximity, f))
    if not candidates:
        return None
    candidates.sort()
    return (candidates[0][1],)


# Map a semitone interval (0..11 from the root) to its scale-degree label.
DEGREE_LABEL = {
    0: '1',   1: '♭2',  2: '2',   3: '♭3',  4: '3',   5: '4',
    6: '♯4',  7: '5',   8: '♯5',  9: '6',  10: '♭7', 11: '7',
}


def scale_spelling(root_name: str, scale_name: str) -> list:
    """Return the note names of the scale, in degree order (1, 2, 3, ...)."""
    if root_name not in NOTE_NAMES:
        raise ValueError(f"Unknown root: {root_name}")
    if scale_name not in SCALES:
        raise ValueError(f"Unknown scale: {scale_name}")
    root = NOTE_NAMES.index(root_name)
    return [NOTE_NAMES[(root + i) % 12] for i in SCALES[scale_name]]


def scale_degree_labels(scale_name: str) -> list:
    """Return scale-degree labels (e.g. '1', '♭2', '3', '♯4', '♯5', '♭6', '7')."""
    return [DEGREE_LABEL.get(i, f'({i})') for i in SCALES[scale_name]]


_TRIAD_NAMES = {
    (4, 3): '',           # major
    (3, 4): 'm',          # minor
    (3, 3): 'dim',
    (4, 4): 'aug',
    (2, 5): 'sus2',
    (5, 2): 'sus4',
}

_SEVENTH_NAMES = {
    (4, 3, 4): 'maj7',
    (4, 3, 3): '7',
    (3, 4, 3): 'm7',
    (3, 4, 4): 'mMaj7',
    (3, 3, 4): 'm7♭5',    # half-dim
    (3, 3, 3): 'dim7',
    (4, 4, 3): 'aug-maj7',
    (4, 4, 2): 'aug7',
    (3, 3, 5): 'dim-maj7',
}


def chord_name(root_name: str, scale_name: str, degrees=(1, 3, 5)) -> str:
    """Return a short chord name like 'E aug', 'C maj7', 'G#sus4'.

    Built from the requested scale degrees of (root_name, scale_name). The
    suffix is matched against common triad / 7th-chord interval patterns;
    unrecognised stacks fall back to a degree-list label.
    """
    intervals = SCALES[scale_name]
    chord_pcs = sorted((intervals[(d - 1) % len(intervals)]) for d in degrees)
    gaps = tuple(b - a for a, b in zip(chord_pcs, chord_pcs[1:]))
    if len(gaps) == 2:
        suffix = _TRIAD_NAMES.get(gaps)
    elif len(gaps) == 3:
        suffix = _SEVENTH_NAMES.get(gaps)
    else:
        suffix = None
    if suffix is None:
        deg_str = '-'.join(DEGREE_LABEL.get(p, str(p)) for p in chord_pcs)
        return f"{root_name}({deg_str})"
    sep = '' if suffix in ('', 'm') else ' '
    return f"{root_name}{sep}{suffix}"


def capo_summary(string_configs: dict) -> str:
    """Describe capos and the drone notes they produce, e.g.:
       'capo 1 on A,G (→A♯,G♯); capo 4 on B (→D♯)'.
       Returns 'no capo' when there are no spider capos.
    """
    if not string_configs:
        return 'no capo'
    by_fret = {}
    for s, v in string_configs.items():
        if isinstance(v, int) and v > 0:
            by_fret.setdefault(v, []).append(s)
    if not by_fret:
        return 'no capo'
    parts = []
    for fret in sorted(by_fret):
        strings = by_fret[fret]
        notes = [NOTE_NAMES[(OPEN_STRINGS[s] + fret) % 12] for s in strings]
        # Replace ASCII '#' with '♯' for display
        notes = [n.replace('#', '♯') for n in notes]
        parts.append(f"capo {fret} on {','.join(strings)} (→{','.join(notes)})")
    return '; '.join(parts)


def drone_label(string_name: str, string_configs: dict,
                root_name: str, scale_name: str) -> str:
    """Return a label like 'G#(1)', 'D(♯4)', 'C#(4)' for the drone note on a
    string, annotated with its interval from the root.

    The role is the chromatic interval from the root, spelled via DEGREE_LABEL
    (1, ♭2, 2, ♭3, 3, 4, ♯4, 5, ♯5, 6, ♭7, 7). Because every semitone has a
    fixed label this works for any scale — including the 8-note diminished
    scales and the 12-note chromatic scale — with no ordinal-numeral overflow,
    and an out-of-scale drone simply reads as its own chromatic degree.
    For X (muted) strings, the implicit open-string drone is used.

    scale_name is retained for signature stability (the interval label does not
    depend on the scale).
    """
    drone = _drone_pc(string_name, string_configs)
    open_pc = OPEN_STRINGS[string_name]
    no_drone_config = {'X', '|'}
    is_no_drone = (string_configs and string_name in string_configs and
                   string_configs[string_name] in no_drone_config)
    if drone is None:
        if is_no_drone:
            drone = open_pc % 12
        else:
            return f"{NOTE_NAMES[open_pc]}(?)"
    note = NOTE_NAMES[drone]
    root = NOTE_NAMES.index(root_name)
    interval = (drone - root) % 12
    return f"{note}({DEGREE_LABEL[interval]})"


# Triad / 7th-chord signatures keyed by intervals from the chord root.
# These are the ONLY chord types `per_string_chord` recognises — 6th chords,
# add chords, slash chords, etc. are intentionally absent and fall through to
# the "?" (unknown) label. Distinction between dominant 7 and major 7 is kept
# explicit (`7` vs `Δ7`).
_CHORD_TYPE_NAMES = {
    # --- Triads (complete) ---
    (0, 4, 7): '',         # major
    (0, 3, 7): 'm',        # minor
    (0, 3, 6): 'dim',      # diminished
    (0, 4, 8): 'aug',      # augmented
    (0, 2, 7): 'sus2',
    (0, 5, 7): 'sus4',

    # --- Triad dyads (5th omitted but the 3rd makes the quality clear) ---
    (0, 4): '',            # major (no 5)
    (0, 3): 'm',           # minor (no 5)
    (0, 6): 'dim',         # diminished triad fragment (no 5 *and* no 3 is awkward
                           # but ♭5 alone usually implies dim context)
    (0, 8): 'aug',         # augmented fragment
    # Power chord (3rd omitted — quality ambiguous)
    (0, 7): '5',
    # Suspended dyads (the 5th carries the quality)
    (0, 2): 'sus2',
    (0, 5): 'sus4',

    # --- 7th-chord dyads (root + 7) ---
    (0, 11): 'Δ7',         # major-7 fragment
    (0, 10): '7',          # dominant-7 fragment

    # --- 7th chords with 5 omitted (3 + 7) ---
    (0, 4, 11): 'Δ7',
    (0, 4, 10): '7',
    (0, 3, 11): 'mΔ7',
    (0, 3, 10): 'm7',

    # --- 7th chords with 3 omitted (5 + 7) ---
    (0, 7, 11): 'Δ7',
    (0, 7, 10): '7',
    (0, 6, 10): 'm7♭5',    # half-dim fragment (no 3)
    (0, 8, 11): 'augΔ7',
    (0, 8, 10): 'aug7',

    # --- 7th chords (complete) ---
    (0, 4, 7, 11): 'Δ7',   # major 7
    (0, 4, 7, 10): '7',    # dominant 7
    (0, 3, 7, 11): 'mΔ7',  # minor-major 7
    (0, 3, 7, 10): 'm7',   # minor 7
    (0, 3, 6, 10): 'm7♭5', # half-diminished 7
    (0, 3, 6, 9):  'dim7', # fully-diminished 7
    (0, 4, 8, 11): 'augΔ7',# augmented-major 7
    (0, 4, 8, 10): 'aug7', # augmented dominant 7
}


def per_string_chord(string_name: str, body_frets: list,
                     string_configs: dict = None) -> str:
    """Return a chord label like 'EΔ7 (157)' for drone + body notes on a string.

    Recognises **triads and 7th chords only** (including their dyad fragments
    when the 5th is implied). Dominant 7s are labelled `7`; major 7s use `Δ7`.
    Anything outside this set — 6th chords, add9, slash chords, clusters —
    falls back to a `Drone?` label with the raw degree list. The user's rule:
    "triads and 7th chords" only.

    For X-muted strings the implicit open-string pitch is still treated as the
    notional root, since the player would otherwise hear it.
    """
    drone = _drone_pc(string_name, string_configs)
    is_muted = (string_configs and string_name in string_configs and
                string_configs[string_name] == 'X')
    if drone is None and is_muted:
        drone = OPEN_STRINGS[string_name] % 12
    if drone is None:
        return '—'

    open_pc = OPEN_STRINGS[string_name]
    body_pcs = [(open_pc + f) % 12 for f in body_frets]
    pcs = sorted(set([drone, *body_pcs]), key=lambda p: (p - drone) % 12)
    intervals = tuple((p - drone) % 12 for p in pcs)

    drone_name = NOTE_NAMES[drone]
    deg_str = ''.join(DEGREE_LABEL[iv] for iv in intervals)
    suffix = _CHORD_TYPE_NAMES.get(intervals)
    if suffix is None:
        return f"{drone_name}? ({deg_str})"
    return f"{drone_name}{suffix} ({deg_str})"


def decorate(diagram: str, root_name: str, scale_name: str,
             string_configs: dict = None, with_chords: bool = False) -> str:
    """Add per-line drone labels and (optionally) chord labels to a rendered diagram.

    Layout:
      `<DRONE(degree)_padded> <config> <body>|  <chord_label>`
    The left column is the drone note + scale-degree role. With with_chords=True
    the right column shows the chord formed by drone + body notes on each string.

    The returned string is for display only — it no longer parses with
    `parse_diagram` because the leading string letter is replaced. Always run
    `verify` (or any parse-based check) on the raw diagram BEFORE decorating.
    """
    drone_labels = {s: drone_label(s, string_configs, root_name, scale_name)
                    for s in STRING_ORDER_DISPLAY}
    label_width = max(len(lbl) for lbl in drone_labels.values()) + 2

    notes_by_string = {}
    if with_chords:
        for s, fret, _col in parse_diagram(diagram):
            notes_by_string.setdefault(s, []).append(fret)
        chord_labels = {s: per_string_chord(s, notes_by_string.get(s, []),
                                             string_configs)
                        for s in STRING_ORDER_DISPLAY}
        chord_width = max(len(c) for c in chord_labels.values())

    out_lines = []
    for line in diagram.split('\n'):
        if not line:
            continue
        if line[0] in OPEN_STRINGS:
            s = line[0]
            config = line[1]
            rest = line[2:]  # body + closing | (and any embedded label)
            new_line = f"{drone_labels[s]:<{label_width}}{config}{rest}"
            if with_chords:
                new_line += f"  {chord_labels[s]:<{chord_width}}"
            out_lines.append(new_line)
        else:
            out_lines.append(line)
    return '\n'.join(out_lines)


def chord_tones(root_name: str, scale_name: str,
                degrees=(1, 3, 5)) -> set:
    """Return pitch classes for a chord built from given 1-indexed scale degrees.

    Default degrees=(1, 3, 5) gives the diatonic triad on the scale's root —
    major in major-like scales, minor in minor-like scales, diminished in
    locrian, augmented in augmented, etc. degrees=(1, 3, 5, 7) adds the seventh.
    """
    if root_name not in NOTE_NAMES:
        raise ValueError(f"Unknown root: {root_name}")
    if scale_name not in SCALES:
        raise ValueError(f"Unknown scale: {scale_name}")
    root = NOTE_NAMES.index(root_name)
    intervals = SCALES[scale_name]
    out = set()
    for d in degrees:
        idx = (d - 1) % len(intervals)
        out.add((root + intervals[idx]) % 12)
    return out


# Named per-string stretch profiles.  Each maps string name -> (min, max) semitone span.
# Used with stretch_profile= in generate_2nps. Built from the active string order
# so they stay valid under use_tuning() (the keys must match the current strings).
def _build_stretch_profiles(order):
    return {
        # Uniform
        'tight':       {s: (0, 2) for s in order},
        'wide':        {s: (3, 5) for s in order},
        'free':        {s: (0, 5) for s in order},
        # Gradient across the neck
        'bass_tight':  {s: (0, 2) if i < 3 else (3, 5) for i, s in enumerate(order)},
        'bass_wide':   {s: (3, 5) if i < 3 else (0, 2) for i, s in enumerate(order)},
        'growing':     {s: (i, min(i + 2, 5)) for i, s in enumerate(order)},
        'shrinking':   {s: (max(0, 4 - i), max(2, 5 - i)) for i, s in enumerate(order)},
        # Alternating tight/wide by string
        'alternating': {s: (0, 2) if i % 2 == 0 else (3, 5) for i, s in enumerate(order)},
    }


STRETCH_PROFILES = _build_stretch_profiles(STRING_ORDER_LOW_TO_HIGH)


# Instrument tunings: (low-to-high string order, {string letter: open pitch class}).
# 'guitar' is the module default; 'bass_6' is a 6-string bass tuned BEADGC.
_TUNING_PRESETS = {
    'guitar': (['E', 'A', 'D', 'G', 'B', 'e'],
               {'E': 4, 'A': 9, 'D': 2, 'G': 7, 'B': 11, 'e': 4}),
    'bass_6': (['B', 'E', 'A', 'D', 'G', 'C'],
               {'B': 11, 'E': 4, 'A': 9, 'D': 2, 'G': 7, 'C': 0}),
    # All-fourths guitar: E A D G C F (replaces the G-B major third with a P4)
    'guitar_4ths': (['E', 'A', 'D', 'G', 'C', 'f'],
                    {'E': 4, 'A': 9, 'D': 2, 'G': 7, 'C': 0, 'f': 5}),
}


@contextmanager
def use_tuning(name: str):
    """Temporarily switch the active instrument tuning for generation/rendering.

    Rebinds the module-level tuning globals (OPEN_STRINGS, the two string
    orders, the diagram line regex, and STRETCH_PROFILES) for the duration of
    the with-block, then restores them. The module default is 6-string guitar,
    so existing callers are unaffected.

    Presets: 'guitar' (EADGBe) and 'bass_6' (BEADGC, low B to high C). Inside
    the block, the "root on the lowest string" constraint targets that tuning's
    lowest string (B for bass, E for guitar).
    """
    global OPEN_STRINGS, STRING_ORDER_LOW_TO_HIGH, STRING_ORDER_DISPLAY
    global DIAGRAM_LINE_RE, STRETCH_PROFILES
    if name not in _TUNING_PRESETS:
        raise ValueError(f"Unknown tuning {name!r}; known: {list(_TUNING_PRESETS)}")
    saved = (OPEN_STRINGS, STRING_ORDER_LOW_TO_HIGH, STRING_ORDER_DISPLAY,
             DIAGRAM_LINE_RE, STRETCH_PROFILES)
    order, opens = _TUNING_PRESETS[name]
    OPEN_STRINGS = dict(opens)
    STRING_ORDER_LOW_TO_HIGH = list(order)
    STRING_ORDER_DISPLAY = list(reversed(order))
    DIAGRAM_LINE_RE = re.compile(rf"^([{''.join(order)}])([|0-9Xx]?)(.*?)\|?$")
    STRETCH_PROFILES = _build_stretch_profiles(order)
    try:
        yield
    finally:
        (OPEN_STRINGS, STRING_ORDER_LOW_TO_HIGH, STRING_ORDER_DISPLAY,
         DIAGRAM_LINE_RE, STRETCH_PROFILES) = saved


def generate_2nps(root_name: str, scale_name: str, start_fret: int = 3,
                  min_stretch: int = 0, max_stretch: int = None,
                  direction: str = 'up', position_shift: float = 0,
                  string_configs: dict = None,
                  stretch_profile: dict = None,
                  pitches: set = None,
                  require_root_on_low_e: bool = False):
    """Generate a 2-note-per-string pattern.

    direction='up'         : classic ascending box — fret floor rises with prev pair.
    direction='free'       : each string targets start_fret + string_index *
                             position_shift, searching the full neck. Positive
                             position_shift moves up the neck; negative moves down.
    direction='down'       : descending diagonal — targets drop ~2 frets per string.
    direction='climb'      : gentle ascent — targets rise ~2 frets per string.
    direction='fast_climb' : steep ascent — targets rise ~5 frets per string,
                             sweeping up the neck (top strings clamp near the top).
    The 'down'/'climb'/'fast_climb' slopes are the per-string defaults used when
    position_shift is 0; pass a nonzero position_shift to override the slope.

    min_stretch / max_stretch: fret span of the chosen pair on each string.
    Set min_stretch=3 to force intervals of a minor 3rd or larger (up to P4 at 5).

    stretch_profile: optional dict mapping string name -> (min_stretch, max_stretch).
      Overrides min_stretch/max_stretch on a per-string basis.  Use STRETCH_PROFILES
      for named presets or supply your own dict, e.g. {'E': (0,2), 'A': (3,5), ...}.

    string_configs: optional dict mapping string name -> int, 'X', or None.
      None  = excluded (string skipped entirely, not rendered).
      'X'   = normal fretted string, rendered with 'X' prefix.
      0     = open string (fret 0 is a candidate note).
      N > 0 = spider capo at fret N (capo position is a candidate note;
              frets above the capo are also searched).
    Strings absent from string_configs are treated normally.

    pitches: optional pitch-class set override.  When given, used instead of the
      scale's pitch set (e.g. supply chord tones to generate arpeggios).
    require_root_on_low_e: if True, force the low E pair to contain the scale root.

    max_stretch defaults to MAX_FINGER_STEP (a minor 3rd). The highest spider-capo
    bar in string_configs sets a global floor — no body note may sit at or below
    that fret on any string.
    """
    cap = effective_finger_step(scale_name)
    if max_stretch is None:
        max_stretch = cap
    if pitches is None:
        pitches = scale_pitches(root_name, scale_name)
    root_pc = NOTE_NAMES.index(root_name)
    fret_floor = _effective_fret_min(string_configs)
    pattern = {}
    prev_low = max(start_fret, fret_floor)
    lowest = STRING_ORDER_LOW_TO_HIGH[0]

    # Directional modes built on the 'free' per-string-target mechanism. When
    # position_shift is left at 0, each named mode supplies its own slope:
    #   climb       — up ~2 frets per string  (gentle ascent)
    #   fast_climb  — up ~5 frets per string  (steep ascent, sweeps the neck)
    #   down        — down ~2 frets per string (descending diagonal)
    _DIRECTION_SHIFT = {'climb': 2.0, 'fast_climb': 5.0, 'down': -2.0}
    free_like = direction in ('free', 'climb', 'fast_climb', 'down')
    shift = position_shift
    if shift == 0 and direction in _DIRECTION_SHIFT:
        shift = _DIRECTION_SHIFT[direction]

    for idx, s in enumerate(STRING_ORDER_LOW_TO_HIGH):
        mn = min_stretch
        mx = max_stretch
        if stretch_profile and s in stretch_profile:
            mn, mx = stretch_profile[s]

        capo_fret = None
        if string_configs and s in string_configs:
            val = string_configs[s]
            if val is None:
                continue  # excluded string
            if val != 'X':
                capo_fret = val  # int: 0 = open, N = capo at fret N
            # 'X' falls through to normal fretted logic below

        if capo_fret is not None:
            target = (start_fret + idx * shift) if free_like else prev_low
            frets = frets_in_scale(s, pitches, fret_min=fret_floor, capo_fret=capo_fret)
        elif direction == 'up':
            target = prev_low
            frets = frets_in_scale(s, pitches, fret_min=max(fret_floor, prev_low - 1))
        else:  # free / climb / fast_climb / down
            target = start_fret + idx * shift
            frets = frets_in_scale(s, pitches, fret_min=fret_floor)

        # require_root_on_low_e applies only to the lowest string. If the capo
        # there already produces the root, the requirement is already met.
        req_pc = None
        if require_root_on_low_e and s == lowest:
            # Open-string drone counts too: if the string already drones the
            # root (open or capo'd to it), no body root is required.
            if _drone_pc(s, string_configs) != root_pc:
                req_pc = root_pc

        pair = pick_pair(frets, target=target, min_stretch=mn, max_stretch=mx,
                         required_pc=req_pc, string_pc=OPEN_STRINGS[s], cap=cap)
        if pair is None and mn > 0:
            pair = pick_pair(frets, target=target, min_stretch=0, max_stretch=mx,
                             required_pc=req_pc, string_pc=OPEN_STRINGS[s], cap=cap)
        if pair is None:
            frets_full = frets_in_scale(s, pitches,
                                        fret_min=fret_floor,
                                        capo_fret=capo_fret)
            pair = pick_pair(frets_full, target=target, min_stretch=0, max_stretch=mx,
                             required_pc=req_pc, string_pc=OPEN_STRINGS[s], cap=cap)
        if pair is None and req_pc is not None:
            # Last-resort: drop the root requirement so generation still succeeds.
            pair = pick_pair(frets, target=target, min_stretch=0, max_stretch=mx, cap=cap)
        if pair is None:
            return None

        pattern[s] = pair
        prev_low = pair[0]

    return pattern


def generate_3nps(root_name: str, scale_name: str, start_fret: int = 3,
                  min_span: int = 2, max_span: int = 6,
                  max_step: int = None,
                  position_shift: float = 0,
                  string_configs: dict = None,
                  pitches: set = None,
                  require_root_on_low_e: bool = False,
                  continuous: bool = True):
    """Generate a 3-note-per-string pattern at a single position.

    Each string gets three consecutive in-scale frets whose total span
    (last - first) is within [min_span, max_span], and where each adjacent
    gap is at most max_step (default MAX_FINGER_STEP = m3).
    With capo, the three fretted notes are above the capo; the capo drone
    is additional.

    start_fret: low-fret target for every string (treat as a "position").
    position_shift: per-string drift applied to start_fret (string_index * shift).
      Use 0 for a true single-position box.

    continuous: when True (default), each string starts on the next scale
    tone after the previous string's last note — the classical 3NPS shape
    that lays out 18 consecutive scale tones across the 6 strings without
    repeating any pitch. Falls back to a free pick when no continuous triple
    is reachable on a given string.

    The highest spider-capo bar sets a global floor on body frets across all
    strings; the bar physically blocks fretting at or below that fret.
    """
    cap = effective_finger_step(scale_name)
    if max_step is None:
        max_step = cap
    if pitches is None:
        pitches = scale_pitches(root_name, scale_name)
    root_pc = NOTE_NAMES.index(root_name)
    fret_floor = _effective_fret_min(string_configs)
    pattern = {}
    lowest = STRING_ORDER_LOW_TO_HIGH[0]

    # Scale pitch classes in ascending semitone order — used to compute
    # the "next scale tone" for continuity.
    scale_pcs_sorted = sorted(pitches)

    def next_scale_pc(pc):
        if pc not in scale_pcs_sorted:
            return None
        i = scale_pcs_sorted.index(pc)
        return scale_pcs_sorted[(i + 1) % len(scale_pcs_sorted)]

    last_pc = None  # pitch class of previous string's last (highest) body note

    for idx, s in enumerate(STRING_ORDER_LOW_TO_HIGH):
        capo_fret = None
        if string_configs and s in string_configs:
            val = string_configs[s]
            if val is None:
                continue
            if val != 'X':
                capo_fret = val

        target = max(start_fret + idx * position_shift, fret_floor)

        if capo_fret is not None:
            frets = frets_in_scale(s, pitches, fret_min=fret_floor, capo_fret=capo_fret)
        else:
            frets = frets_in_scale(s, pitches, fret_min=fret_floor)

        req_pc = None
        if require_root_on_low_e and s == lowest:
            # Open-string drone counts too: if the string already drones the
            # root (open or capo'd to it), no body root is required.
            if _drone_pc(s, string_configs) != root_pc:
                req_pc = root_pc

        req_first_pc = (next_scale_pc(last_pc) if continuous and last_pc is not None
                        else None)

        triple = pick_triple(frets, target=target,
                             min_span=min_span, max_span=max_span,
                             max_step=max_step,
                             required_pc=req_pc, string_pc=OPEN_STRINGS[s],
                             required_first_pc=req_first_pc, cap=cap)
        # Drop continuity constraint first if no fit
        if triple is None and req_first_pc is not None:
            triple = pick_triple(frets, target=target,
                                 min_span=min_span, max_span=max_span,
                                 max_step=max_step,
                                 required_pc=req_pc, string_pc=OPEN_STRINGS[s], cap=cap)
        if triple is None and req_pc is not None:
            triple = pick_triple(frets, target=target,
                                 min_span=min_span, max_span=max_span,
                                 max_step=max_step, cap=cap)
        if triple is None:
            # Relax span only; keep max_step honored as the ergonomics cap.
            triple = pick_triple(frets, target=target, min_span=0,
                                 max_span=2 * max_step, max_step=max_step, cap=cap)
        if triple is None:
            return None
        pattern[s] = triple
        # Track the pitch class of this string's highest note for the next iteration.
        last_pc = (OPEN_STRINGS[s] + triple[-1]) % 12

    return pattern


def generate_arpeggio(root_name: str, scale_name: str, start_fret: int = 3,
                      max_stretch: int = None, position_shift: float = 0,
                      string_configs: dict = None,
                      degrees=(1, 3, 5, 7),
                      require_root_on_low_e: bool = True):
    """Generate an arpeggio using chord tones, honoring MAX_FINGER_STEP.

    Default degrees=(1, 3, 5, 7) gives the diatonic 7th chord. Including the
    7th brings in a M2 or m2 between the 7th and root in most chord types,
    so 2-note-per-string pairs within m3 are usually available even when the
    base triad is augmented (as in E enigmatic, whose 1-3-5 has all-M3 gaps).

    Strategy:
      1. Pull from the full scale (not just one chord-tone set) so the picker
         has dense pair options near every position.
      2. Constrain drone→f1 (the lower body note) to ≥ m3 from the drone —
         this enforces actual arpeggio character. Without it the picker could
         pick a m2 above the drone, which would be a chromatic cluster, not
         an arpeggio.
      3. Among 2-note pairs within max_stretch (by middle-fret proximity to
         the target), prefer pairs that combine with the string's drone to
         form a recognised triad or 7th chord.
      4. Apply a **variety bonus**: pairs whose chord *type* (interval
         signature) hasn't appeared on a previous string get a strong boost,
         pairs whose exact chord *identity* (pitch-class set) is unused get
         a smaller boost. This pushes each string toward a different chord —
         major / minor / dim / sus / dom7-no3 / etc. — for harmonic variety.
      5. Fall back to a non-chord pair within max_stretch, then a single
         chord tone, when no pair fits.
    """
    if max_stretch is None:
        max_stretch = effective_finger_step(scale_name)
    pitches = scale_pitches(root_name, scale_name)
    root_pc = NOTE_NAMES.index(root_name)
    fret_floor = _effective_fret_min(string_configs)
    pattern = {}

    # State shared across strings: used chord types (interval signatures from
    # drone) and used chord identities (sorted pc tuples). These drive the
    # variety bonus — each string is nudged toward a fresh chord.
    used_types = set()
    used_chord_ids = set()

    # Allowed drone→f1 interval range (semitones). m3..♭6 inclusive —
    # broad enough to cover all standard triad/7th roots/3rds/5ths.
    _ARP_DRONE_TO_F1 = frozenset({3, 4, 5, 6, 7, 8})

    def best_notes(frets, target, req_pc, string_pc, drone_pc):
        """Pair-first picker with chord-forming preference and variety bonus."""
        chord_pairs = []  # (score, a, b, intervals, chord_id)
        other_pairs = []  # (score, a, b)
        for i in range(len(frets)):
            for j in range(i + 1, len(frets)):
                a, b = frets[i], frets[j]
                if b - a > max_stretch:
                    break
                if req_pc is not None:
                    if not any((string_pc + f) % 12 == req_pc for f in (a, b)):
                        continue
                f1_pc = (string_pc + a) % 12
                f2_pc = (string_pc + b) % 12
                drone_to_f1 = (f1_pc - drone_pc) % 12
                # Drone→f1 must be m3..♭6 — gives the pair real arpeggio
                # character rather than a chromatic cluster.
                if drone_to_f1 not in _ARP_DRONE_TO_F1:
                    continue
                full_pcs = sorted({drone_pc, f1_pc, f2_pc},
                                   key=lambda p: (p - drone_pc) % 12)
                intervals = tuple((p - drone_pc) % 12 for p in full_pcs)
                chord_id = tuple(full_pcs)
                forms_chord = intervals in _CHORD_TYPE_NAMES
                middle = (a + b) / 2
                middle_prox = abs(middle - target)
                # Variety bonus: subtract from score so unused types win on
                # ties. Type bonus dominates identity bonus (3 > 1.5).
                variety_bonus = 0.0
                if forms_chord:
                    if intervals not in used_types:
                        variety_bonus += 3.0
                    if chord_id not in used_chord_ids:
                        variety_bonus += 1.5
                score = middle_prox - variety_bonus
                if forms_chord:
                    chord_pairs.append((score, a, b, intervals, chord_id))
                else:
                    other_pairs.append((score, a, b))

        chord_pairs.sort()
        other_pairs.sort()

        # The variety-bonus is in score; we accept chord pairs up to
        # 2*max_stretch from the target, before bonus is applied.
        def _chord_within_threshold(item):
            return abs((item[1] + item[2]) / 2 - target) <= 2 * max_stretch

        best_chord = chord_pairs[0] if chord_pairs and _chord_within_threshold(chord_pairs[0]) else None
        best_other = other_pairs[0] if other_pairs and other_pairs[0][0] <= max_stretch else None

        chosen = None
        if best_chord is not None:
            chord_middle_prox = abs((best_chord[1] + best_chord[2]) / 2 - target)
            # Non-chord pair only wins if it is much closer than the
            # chord-forming pair (more than max_stretch better).
            if best_other is not None and best_other[0] < chord_middle_prox - max_stretch:
                chosen = (best_other[1], best_other[2])
            else:
                chosen = (best_chord[1], best_chord[2])
                # Record for the variety bonus on future strings.
                used_types.add(best_chord[3])
                used_chord_ids.add(best_chord[4])
        elif best_other is not None:
            chosen = (best_other[1], best_other[2])
        else:
            single = pick_single(frets, target=target,
                                 required_pc=req_pc, string_pc=string_pc)
            if single is not None:
                chosen = single
            elif chord_pairs:
                chosen = (chord_pairs[0][1], chord_pairs[0][2])
                used_types.add(chord_pairs[0][3])
                used_chord_ids.add(chord_pairs[0][4])
            elif other_pairs:
                chosen = (other_pairs[0][1], other_pairs[0][2])
        return chosen

    lowest = STRING_ORDER_LOW_TO_HIGH[0]
    for idx, s in enumerate(STRING_ORDER_LOW_TO_HIGH):
        capo_fret = None
        if string_configs and s in string_configs:
            val = string_configs[s]
            if val is None:
                continue
            if val != 'X':
                capo_fret = val

        target = max(start_fret + idx * position_shift, fret_floor)

        if capo_fret is not None:
            frets = frets_in_scale(s, pitches, fret_min=fret_floor, capo_fret=capo_fret)
        else:
            frets = frets_in_scale(s, pitches, fret_min=fret_floor)

        req_pc = None
        drone = _drone_pc(s, string_configs)
        if require_root_on_low_e and s == lowest:
            # Open-string drone counts too: if the string already drones the
            # root, no body root is required.
            if drone != root_pc:
                req_pc = root_pc
        # If the string is X-muted, treat the open pitch as the notional
        # drone so per_string_chord and our chord-forming check agree.
        if drone is None:
            drone = OPEN_STRINGS[s] % 12

        notes = best_notes(frets, target, req_pc, OPEN_STRINGS[s], drone)
        if notes is None and req_pc is not None:
            # Last resort: drop the root requirement.
            notes = best_notes(frets, target, None, OPEN_STRINGS[s], drone)
        if notes is None:
            return None
        pattern[s] = notes

    return pattern


def render(pattern: dict, label: str = "", width: int = 20,
           string_configs: dict = None) -> str:
    """Render a {string: tuple_of_frets} pattern as a fretboard-faithful diagram.

    Every fret is rendered as a single digit equal to fret % 10.

    When string_configs contains a spider capo at fret M > 0, the highest
    such M sets a display shift: body[0] is the bar at fret M, and column k
    of the body represents fret (k + M). Without a capo, M = 0 and the
    original "column == fret" mapping holds.

    string_configs: if given, drives the config char in each prefix.
      None -> 'X' with all-dash body (excluded, not generated)
      'X'  -> 'X' prefix (string muted/bypassed)
      '|'  -> '|' prefix (fretted only, no open, no capo — unusual)
      0    -> '0' (nut position — same as default)
      N    -> str(N) (capo at fret N)
    Strings absent from string_configs use '0' (normal, nut position).
    """
    shift = _max_capo(string_configs)

    non_empty = [p for p in pattern.values() if p]
    if non_empty:
        max_fret = max(max(p) for p in non_empty)
        needed = (max_fret - shift) + 4
        if width < needed:
            width = needed

    lines = []
    for s in STRING_ORDER_DISPLAY:
        if string_configs and s in string_configs and string_configs[s] is None:
            chars = ['-'] * width
            chars[0] = ' '
            lines.append(f"{s}X" + ''.join(chars) + "|")
            continue

        config_char = '0'
        if string_configs and s in string_configs:
            val = string_configs[s]
            config_char = val if val in ('X', '|') else str(val)

        frets = pattern[s]
        chars = ['-'] * width
        chars[0] = ' '
        for f in frets:
            col = f - shift
            chars[col] = str(f % 10)
        lines.append(f"{s}{config_char}" + ''.join(chars) + "|")

    out = '\n'.join(lines)
    if label:
        out += f"  {label}"
    return out


def _validate_capo_count(string_configs: dict, max_capos: int = 2):
    if not string_configs:
        return
    capo_frets = {v for v in string_configs.values()
                  if isinstance(v, int) and v > 0}
    if len(capo_frets) > max_capos:
        raise ValueError(
            f"Up to {max_capos} spider capo fret(s) supported; "
            f"got {sorted(capo_frets)}")


def all_diagram_frets_in_range(diagram: str, string_configs: dict = None) -> bool:
    """True iff every parsed body note has fret > max_capo (i.e. above the bar)."""
    floor = _effective_fret_min(string_configs, base_min=0)
    for _s, fret, _col in parse_diagram(diagram):
        if fret < floor:
            return False
    return True


def generate_and_render(root_name: str, scale_name: str,
                        label: str = None, start_fret: int = 3,
                        min_stretch: int = 0, max_stretch: int = 5,
                        direction: str = 'up', position_shift: float = 0,
                        string_configs: dict = None,
                        stretch_profile: dict = None,
                        require_root_on_low_e: bool = False,
                        width: int = 18) -> str:
    """One-shot: generate a verified 2NPS diagram or raise on failure.

    Up to 2 distinct spider-capo frets are allowed in string_configs.
    """
    _validate_capo_count(string_configs)
    pattern = generate_2nps(root_name, scale_name, start_fret=start_fret,
                            min_stretch=min_stretch, max_stretch=max_stretch,
                            direction=direction, position_shift=position_shift,
                            string_configs=string_configs,
                            stretch_profile=stretch_profile,
                            require_root_on_low_e=require_root_on_low_e)
    if pattern is None:
        raise RuntimeError(f"Could not generate {root_name} {scale_name}")
    if label is None:
        label = f"{root_name} {scale_name.replace('_', ' ').title()}"
    diagram = render(pattern, label, width=width, string_configs=string_configs)
    if not verify(diagram, root_name, scale_name, label):
        raise RuntimeError(f"Generated diagram failed verification: {label}")
    return diagram


def generate_3nps_and_render(root_name: str, scale_name: str,
                              label: str = None, start_fret: int = 3,
                              min_span: int = 2, max_span: int = 5,
                              position_shift: float = 0,
                              string_configs: dict = None,
                              require_root_on_low_e: bool = False,
                              width: int = 20) -> str:
    """One-shot: generate a verified 3NPS diagram or raise on failure."""
    _validate_capo_count(string_configs)
    pattern = generate_3nps(root_name, scale_name, start_fret=start_fret,
                            min_span=min_span, max_span=max_span,
                            position_shift=position_shift,
                            string_configs=string_configs,
                            require_root_on_low_e=require_root_on_low_e)
    if pattern is None:
        raise RuntimeError(f"Could not generate 3NPS {root_name} {scale_name}")
    if label is None:
        label = f"{root_name} {scale_name.replace('_', ' ').title()} 3NPS pos {start_fret}"
    diagram = render(pattern, label, width=width, string_configs=string_configs)
    if not verify(diagram, root_name, scale_name, label):
        raise RuntimeError(f"3NPS diagram failed verification: {label}")
    return diagram


def generate_arpeggio_and_render(root_name: str, scale_name: str,
                                  label: str = None, start_fret: int = 3,
                                  position_shift: float = 0,
                                  degrees=(1, 3, 5, 7),
                                  string_configs: dict = None,
                                  width: int = 20) -> str:
    """One-shot: generate a verified arpeggio diagram (chord tones only)."""
    _validate_capo_count(string_configs)
    pattern = generate_arpeggio(root_name, scale_name, start_fret=start_fret,
                                position_shift=position_shift,
                                degrees=degrees,
                                string_configs=string_configs,
                                require_root_on_low_e=True)
    if pattern is None:
        raise RuntimeError(f"Could not generate arpeggio for {root_name} {scale_name}")
    if label is None:
        deg_str = '-'.join(str(d) for d in degrees)
        label = f"{root_name} {scale_name.replace('_', ' ').title()} arp {deg_str}"
    diagram = render(pattern, label, width=width, string_configs=string_configs)
    if not verify(diagram, root_name, scale_name, label):
        raise RuntimeError(f"Arpeggio diagram failed verification: {label}")
    return diagram


class _FullSetResult(dict):
    """Dict subclass returned by generate_full_set. Carries metadata
    (root_name, scale_name, string_configs) on the instance so render_full_set
    can decorate without extra arguments. Behaves like a plain dict for
    `[key]` access and `.values()` iteration — tests that walk the sections
    won't see the metadata."""
    pass


def generate_full_set(root_name: str, scale_name: str,
                      string_configs: dict = None,
                      second_capo_fret: int = None,
                      start_fret: int = 3,
                      width: int = 22) -> dict:
    """Generate a "full set" of practice diagrams in one call.

    Layout (returned dict; see render_full_set for the printed grid):
      row 1 — three 2NPS variations: tight (all close-spaced seconds),
              wide (3rds/4ths), and a mixed/alternating shape.
      row 2 — three 3NPS scale positions, ascending up the neck starting
              from just above the capo.
      row 3 — two arpeggios at low and high positions.

    Every diagram has the scale root forced onto the low E string.

    second_capo_fret: when given, any string in string_configs whose value is
      'X' is converted to a spider capo at this fret. This is the "use the 2nd
      capo to remove X strings" feature.

    Returns: {
        'two_note':   [(label, diagram), (label, diagram), (label, diagram)],
        'three_note': [(label, diagram), (label, diagram), (label, diagram)],
        'arpeggio':   [(label, diagram), (label, diagram)],
    }
    Each diagram is rendered WITHOUT an embedded label; the label is supplied
    separately so render_full_set can centre it under each column.
    """
    cfg = dict(string_configs) if string_configs else {}
    if second_capo_fret is not None:
        if not (isinstance(second_capo_fret, int) and second_capo_fret > 0):
            raise ValueError(f"second_capo_fret must be a positive int; got {second_capo_fret!r}")
        for s, v in list(cfg.items()):
            if v == 'X':
                cfg[s] = second_capo_fret
    cfg = cfg if cfg else None
    _validate_capo_count(cfg)

    capo_frets = [v for v in (cfg or {}).values()
                  if isinstance(v, int) and v > 0]
    base = (max(capo_frets) + 1) if capo_frets else max(start_fret, 3)
    base = max(base, 3)

    def make_2nps(start, mn, mx, profile, direction, shift):
        pat = generate_2nps(root_name, scale_name, start_fret=start,
                            min_stretch=mn, max_stretch=mx,
                            direction=direction, position_shift=shift,
                            string_configs=cfg, stretch_profile=profile,
                            require_root_on_low_e=True)
        if pat is None:
            raise RuntimeError(f"Could not generate 2NPS at fret {start}")
        diagram = render(pat, label="", width=width, string_configs=cfg)
        if not verify(diagram, root_name, scale_name):
            raise RuntimeError(f"2NPS verification failed at fret {start}")
        return diagram

    def make_3nps(start):
        pat = generate_3nps(root_name, scale_name, start_fret=start,
                            string_configs=cfg,
                            require_root_on_low_e=True)
        if pat is None:
            raise RuntimeError(f"Could not generate 3NPS at fret {start}")
        diagram = render(pat, label="", width=width, string_configs=cfg)
        if not verify(diagram, root_name, scale_name):
            raise RuntimeError(f"3NPS verification failed at fret {start}")
        return diagram

    def make_arp(start, shift, degrees=(1, 3, 5, 7)):
        pat = generate_arpeggio(root_name, scale_name, start_fret=start,
                                position_shift=shift, string_configs=cfg,
                                degrees=degrees,
                                require_root_on_low_e=True)
        if pat is None:
            raise RuntimeError(f"Could not generate arpeggio at fret {start}")
        diagram = render(pat, label="", width=width, string_configs=cfg)
        if not verify(diagram, root_name, scale_name):
            raise RuntimeError(f"Arpeggio verification failed at fret {start}")
        return diagram

    # Six 2NPS variants. The first three vary stretch (tight/wide/alternating);
    # the last three vary neck angle (descending / climbing / fast climbing).
    # All stay within the scale's finger-reach cap (a minor 3rd, or a major 3rd
    # for scales with no minor 3rd such as whole-tone).
    cap = effective_finger_step(scale_name)
    two_note = [
        ('tight (m2)',
         make_2nps(base, 0, 2, STRETCH_PROFILES['tight'], 'up', 0)),
        ('wide',
         make_2nps(base, cap, cap, None, 'free', 0)),
        ('alternating',
         make_2nps(base + 2, 0, cap, STRETCH_PROFILES['alternating'], 'free', 0)),
        ('descending',
         make_2nps(base + 9, 0, cap, None, 'down', 0)),
        ('climbing',
         make_2nps(base, 0, cap, None, 'climb', 0)),
        ('fast climbing',
         make_2nps(base, 0, cap, None, 'fast_climb', 0)),
    ]

    three_note = [
        (f'3NPS pos {base}',     make_3nps(base)),
        (f'3NPS pos {base + 3}', make_3nps(base + 3)),
        (f'3NPS pos {base + 5}', make_3nps(base + 5)),
    ]

    # Two arpeggio voicings at different neck positions. Both use the
    # diatonic 7th chord (1-3-5-7); the picker chooses the closest chord-tone
    # pair OR single per string, so each arp stays compact instead of jumping
    # frets to satisfy a 2NPS goal.
    arpeggio = [
        ('arp low',   make_arp(base, 0, degrees=(1, 3, 5, 7))),
        ('arp high',  make_arp(base + 5, 0, degrees=(1, 3, 5, 7))),
    ]

    result = _FullSetResult({'two_note': two_note,
                             'three_note': three_note,
                             'arpeggio': arpeggio})
    # Stash metadata so render_full_set can decorate without extra args.
    result.root_name = root_name
    result.scale_name = scale_name
    result.string_configs = cfg
    return result


def render_full_set(full_set: dict, gap: int = 4) -> str:
    """Arrange a generate_full_set() result as a 3-row grid with labels.

    Each row is rendered as one block: the diagrams side-by-side, then a
    centred label row beneath. A blank line separates rows.

    When the full_set carries metadata (root_name, scale_name, string_configs)
    — as set by generate_full_set — every diagram gets the standard
    `Note(degree)  config body|` left-column prefix, and arpeggio diagrams
    additionally get a `chord_name (degrees)` right-column suffix. Plain dict
    inputs without metadata are laid out without decoration.
    """
    root = getattr(full_set, 'root_name', None)
    scale = getattr(full_set, 'scale_name', None)
    cfg = getattr(full_set, 'string_configs', None)
    decorate_enabled = root is not None and scale is not None

    def maybe_decorate(diagram, with_chords):
        if not decorate_enabled:
            return diagram
        return decorate(diagram, root, scale, cfg, with_chords=with_chords)

    def render_row(items, with_chords=False):
        decorated = [(lbl, maybe_decorate(d, with_chords)) for lbl, d in items]
        line_groups = [d.split('\n') for _, d in decorated]
        labels = [lbl for lbl, _ in decorated]
        max_h = max(len(g) for g in line_groups)
        widths = [max(len(line) for line in g) for g in line_groups]
        for g in line_groups:
            while len(g) < max_h:
                g.append('')
        out = []
        for i in range(max_h):
            out.append((' ' * gap).join(
                g[i].ljust(w) for g, w in zip(line_groups, widths)))
        out.append((' ' * gap).join(
            lbl.center(w) for lbl, w in zip(labels, widths)))
        return '\n'.join(out)

    sections = []
    for key in ('two_note', 'three_note', 'arpeggio'):
        if full_set.get(key):
            sections.append(render_row(full_set[key],
                                       with_chords=(key == 'arpeggio')))
    return '\n\n'.join(sections)


def render_single_string(root_name: str, scale_name: str, string: str,
                         fret_min: int = 7, fret_max: int = 19) -> str:
    """Show all in-scale frets on one string using the standard 6-string tab format.

    All other strings are muted (X) so the target string's notes read cleanly
    against the normal string grid.  The diagram is decorated with drone labels
    and verified before returning.
    """
    if string not in OPEN_STRINGS:
        raise ValueError(f"Unknown string {string!r}; known: {list(OPEN_STRINGS)}")
    pitches = scale_pitches(root_name, scale_name)
    in_scale = tuple(f for f in range(fret_min, fret_max + 1)
                     if pitch_at(string, f) in pitches)
    if not in_scale:
        raise ValueError(
            f"No {root_name} {scale_name} tones on {string} string "
            f"between frets {fret_min} and {fret_max}"
        )
    string_configs = {s: 'X' for s in OPEN_STRINGS}
    string_configs[string] = '|'
    pattern = {s: () for s in OPEN_STRINGS}
    pattern[string] = in_scale
    scale_label = scale_name.replace('_', ' ').title()
    label = f'{root_name} {scale_label} — {string} string'
    diagram = render(pattern, label, string_configs=string_configs)
    return decorate(diagram, root_name, scale_name, string_configs)


def render_dual_string(root_name: str, scale_name: str,
                       string_lo: str, string_hi: str,
                       fret_min: int = 7, fret_max: int = 19) -> str:
    """Show in-scale frets on two strings using the standard 6-string tab format.

    All other strings are muted (X).  Each of the two active strings shows
    every in-scale fret in [fret_min, fret_max].  The diagram is decorated
    with drone labels and verified before returning.
    """
    for s in (string_lo, string_hi):
        if s not in OPEN_STRINGS:
            raise ValueError(f"Unknown string {s!r}; known: {list(OPEN_STRINGS)}")
    pitches = scale_pitches(root_name, scale_name)

    def in_scale_frets(s):
        return tuple(f for f in range(fret_min, fret_max + 1)
                     if pitch_at(s, f) in pitches)

    string_configs = {s: 'X' for s in OPEN_STRINGS}
    string_configs[string_lo] = '|'
    string_configs[string_hi] = '|'
    pattern = {s: () for s in OPEN_STRINGS}
    pattern[string_lo] = in_scale_frets(string_lo)
    pattern[string_hi] = in_scale_frets(string_hi)
    scale_label = scale_name.replace('_', ' ').title()
    label = f'{root_name} {scale_label} — {string_lo}+{string_hi} strings'
    diagram = render(pattern, label, string_configs=string_configs)
    return decorate(diagram, root_name, scale_name, string_configs)


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
