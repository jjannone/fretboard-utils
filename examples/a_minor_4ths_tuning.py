"""
Interesting scales over A minor — guitar in all-fourths tuning (E A D G C F).
No open strings; all patterns start around fret 7.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fretboard import (
    use_tuning, generate_full_set, render_full_set,
    scale_spelling, scale_degree_labels, capo_summary,
    generate_and_render, generate_3nps_and_render, generate_arpeggio_and_render,
    decorate, OPEN_STRINGS,
)

ROOT = 'A'

# Scales that are interesting over A minor (each has a different flavour)
SCALES = [
    ('natural_minor',     'A Natural Minor — the home base'),
    ('dorian',            'A Dorian — raised ♭6→6, jazzier minor'),
    ('phrygian',          'A Phrygian — Spanish / flamenco flavour'),
    ('harmonic_minor',    'A Harmonic Minor — classical drama (raised 7th)'),
    ('melodic_minor',     'A Melodic Minor — jazz minor (raised 6th & 7th)'),
    ('altered',           'A Altered (7th mode of Bb melodic minor) — maximum tension over A7'),
    ('half_whole_dim',    'A Half-Whole Diminished — dominant/symmetric tension'),
    ('phrygian_dominant', 'A Phrygian Dominant — harmonic minor mode, exotic'),
    ('minor_pentatonic',  'A Minor Pentatonic — blues core'),
    ('blues_minor',       'A Blues — pentatonic + ♭5 blue note'),
]

# Spider capo: one capo on the low strings to block open sound while allowing
# fretted notes above fret 7.  Capo 7 on E,A,D gives drones A♭, E♭, A♭ under
# the body.  We use capo=7 on the bottom three strings and X on the top three
# so every note is purely fretted (start_fret=8 puts us above the bar).
# Actually: the user said "no open strings, boxes start on 7th fret" — we
# interpret this as: start_fret=7, mute all strings (no open/capo drones),
# so string_configs = all 'X'.  That produces clean fretted-only tabs.

STRING_CONFIGS = {'E': 'X', 'A': 'X', 'D': 'X', 'G': 'X', 'C': 'X', 'f': 'X'}

def header(scale_name, label):
    spelling  = scale_spelling(ROOT, scale_name)
    degrees   = scale_degree_labels(scale_name)
    capo_str  = capo_summary(STRING_CONFIGS)
    notes_str = '  '.join(f'{n}({d})' for n, d in zip(spelling, degrees))
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"  Notes : {notes_str}")
    print(f"  Capo  : {capo_str}")
    print(f"{'='*70}")

with use_tuning('guitar_4ths'):
    for scale_name, label in SCALES:
        header(scale_name, label)

        # 2NPS box at fret 7
        try:
            tab2 = generate_and_render(
                ROOT, scale_name,
                start_fret=7,
                string_configs=STRING_CONFIGS,
                require_root_on_low_e=False,
            )
            print("\n[2NPS box, fret 7]")
            print(tab2)
        except Exception as e:
            print(f"  (2NPS skipped: {e})")

        # 3NPS box at fret 7
        try:
            tab3 = generate_3nps_and_render(
                ROOT, scale_name,
                start_fret=7,
                string_configs=STRING_CONFIGS,
                require_root_on_low_e=False,
            )
            print("\n[3NPS box, fret 7]")
            print(tab3)
        except Exception as e:
            print(f"  (3NPS skipped: {e})")

        # Arpeggio at fret 7
        try:
            taba = generate_arpeggio_and_render(
                ROOT, scale_name,
                start_fret=7,
                string_configs=STRING_CONFIGS,
            )
            print("\n[Arpeggio, fret 7]")
            print(taba)
        except Exception as e:
            print(f"  (Arpeggio skipped: {e})")

print("\nDone.")
